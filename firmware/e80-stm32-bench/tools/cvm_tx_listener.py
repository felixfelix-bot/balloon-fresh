#!/usr/bin/env python3
"""cvm_tx_listener.py — TX-side ARMED listener with freshness watchdog.

Phase-3 wiring for the TX half of the CVM range-sync handshake
(`docs/ADR-range-sync-cvm.md` §2.2/§2.3/§2.4). ``cvm_sync.py`` (P1 message
layer, already merged) ships the ARMED schema plus a bare ``ArmedSubscriber``;
this module supplies the production TX listener the ADR asks for:

  * subscribe **broad** to kind-1059 gift wraps — no restrictive server-side
    ``#p`` filter (established unreliable in ``cvm_board_server.py``) — and
    enforce the **client-side npub allowlist** on receipt; non-allowlisted
    authors are dropped
  * ARMED payload validation against the ADR schema
    (``session_id``, ``stop``, ``t_ready_utc``, ``preset_hash``, ``seq``);
    ``session_id`` must be ``%y%m%d%H%M`` (10 digits) + 3 lowercase-hex nonce
  * events authored by SELF are ignored
  * freshness watchdog: reject any ARMED whose ``created_at`` skews more than
    ``MAX_CREATED_AT_SKEW`` (60 s) from the local clock; ABORT the session when
    no fresh ARMED arrives within ``STALE_ABORT`` (30 s) of the last one (or of
    start-up), logging a clear abort reason
  * relay failover set: ``nostr.mom``, ``relay.primal.net``, ``nos.lol``,
    ``relay2.contextvm.org``, ``relay.nostr.band`` — ``relay.contextvm.org`` is
    DEAD (verified 2026-08-23) and is filtered out even if supplied
  * keys read from **env vars only, never CLI args** (ADR §2.3); the client key
    **must differ** from the server key — asserted at startup

Transport reuses the ``cvm_board_server.py`` ``HandleNotification`` pattern:
broad ``kind=1059`` subscribe, ``p``-tag check client-side, then
``nostr_sdk.UnwrappedGift.from_gift_wrap`` + JSON inner content. ``KIND_GIFT_WRAP``
is imported from ``cvm_sync`` (ADR-033 single canonical def).

The module imports cleanly WITHOUT ``nostr_sdk`` installed: the SDK is only
touched inside the transport / key-loading functions, so the pure logic
(session id, payload schema, watchdog, env parsing, relay set, allowlist) is
unit-testable in a bare Python image.

Usage (TX machine, keys in env):

    export CVM_TX_NSEC=nsec1...        # TX (client) key
    export CVM_SERVER_NSEC=nsec1...    # board server key (must differ)
    export CVM_RX_NPUB=npub1...        # RX publisher -> the allowlist
    python3 cvm_tx_listener.py --stop 50m

Run:  python3 -m pytest test_cvm_tx_listener.py -v
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from typing import Callable, Mapping, Optional

# Sibling imports (cvm_sync) — same convention as the other tools/ modules.
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import cvm_sync as cvm  # noqa: E402
from cvm_sync import ARMED_REQUIRED, KIND_GIFT_WRAP  # noqa: E402
import keymaterial  # noqa: E402  (card t_4c98fbe7: THE env-only key source)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: RX is the sole session authority: strftime %y%m%d%H%M + 3 lowercase-hex
#: nonce. The strftime directives arrive fully expanded (plain digits), never
#: as '%' or URL-unsafe residue, because the id is used in log dir names.
SESSION_ID_RE = re.compile(r"^\d{10}[0-9a-f]{3}$")

#: Freshness-watchdog bounds (seconds). Single canonical definition lives in
#: cvm_sync (P1 message layer); re-exported here so the TX listener's threshold
#: can never drift from the ADR.
MAX_CREATED_AT_SKEW = cvm.MAX_CREATED_AT_SKEW   # reject ARMED skew > 60 s
STALE_ABORT = cvm.STALE_ABORT                   # abort when stale > 30 s

#: Inner (gift-wrapped) content kind — the CVM JSON-RPC envelope used by
#: ``cvm_board_server.py``. NOT a public/plaintext kind.
KIND_CVM_RPC = 25910

#: Env var names — the ONLY place key material may come from.
ENV_CLIENT_NSEC = "CVM_TX_NSEC"
ENV_CLIENT_HEX = "CVM_TX_HEX"
ENV_CLIENT_ALIAS_NSEC = "CVM_CLIENT_NSEC"
ENV_CLIENT_ALIAS_HEX = "CVM_CLIENT_HEX"
ENV_SERVER_NSEC = "CVM_SERVER_NSEC"
ENV_SERVER_HEX = "CVM_SERVER_HEX"
ENV_RX_NPUB = "CVM_RX_NPUB"

#: Relay failover set (ADR §2.2). relay.contextvm.org is DEAD — never add it.
FAILOVER_RELAYS = [
    "wss://nostr.mom",
    "wss://relay.primal.net",
    "wss://nos.lol",
    "wss://relay2.contextvm.org",
    "wss://relay.nostr.band",
]
DEAD_RELAYS = ("wss://relay.contextvm.org",)

#: Exactly the fields build_armed() carries (schema pinned by the ADR).
ARMED_FIELDS = ("type",) + tuple(ARMED_REQUIRED) + ("author",)


# Card t_4c98fbe7: the ONE key-error taxonomy lives in ``keymaterial.py``.
# Aliases, not new classes — see the note in cvm_armed_publisher.py.
EnvKeyError = keymaterial.MissingKeyError
KeyCollisionError = keymaterial.KeyCollisionError


# ---------------------------------------------------------------------------
# Session id + ARMED payload validation (client-side, on receipt)
# ---------------------------------------------------------------------------

def validate_session_id(session_id) -> bool:
    """True iff `session_id` is %y%m%d%H%M (10 digits) + 3 lowercase-hex."""
    return bool(isinstance(session_id, str)
                and SESSION_ID_RE.match(session_id))


def _as_int(value):
    """int(value) or None when it is not a clean integer."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_armed(msg, now: Optional[float] = None,
                allowed_npubs: Optional[set] = None,
                self_pubkey: Optional[str] = None) -> tuple:
    """Parse + validate an ARMED message. Returns ``(ok, reason)``.

    Rejects: non-ARMED / non-dict payloads, missing required fields, a malformed
    ``session_id``, non-integer ``t_ready_utc``/``seq``, an event authored by
    SELF, a non-allowlisted author (when an allowlist is given), and a
    ``created_at`` skew greater than ``MAX_CREATED_AT_SKEW`` (> 60 s).
    """
    now = now if now is not None else time.time()
    if not isinstance(msg, dict) or msg.get("type") != "ARMED":
        return False, "not an ARMED message"
    for field in ARMED_REQUIRED:
        if field not in msg:
            return False, "missing required field: {}".format(field)

    session_id = msg.get("session_id")
    if not validate_session_id(session_id):
        return False, "bad session_id: {!r}".format(session_id)
    if not isinstance(msg.get("stop"), str) or not msg.get("stop"):
        return False, "bad stop: {!r}".format(msg.get("stop"))
    if _as_int(msg.get("t_ready_utc")) is None:
        return False, "bad t_ready_utc: {!r}".format(msg.get("t_ready_utc"))
    if _as_int(msg.get("seq")) is None:
        return False, "bad seq: {!r}".format(msg.get("seq"))

    author = msg.get("author", "")
    if self_pubkey and author and author == self_pubkey:
        return False, "event from self — ignored"
    if allowed_npubs is not None and author not in allowed_npubs:
        return False, "author not in allowlist: {}".format(str(author)[:16])

    created = msg.get("created_at")
    if created is not None:
        created_i = _as_int(created)
        if created_i is None:
            return False, "bad created_at: {!r}".format(created)
        skew = abs(int(now) - created_i)
        if skew > MAX_CREATED_AT_SKEW:
            return False, "created_at skew {}s > {}s".format(
                skew, MAX_CREATED_AT_SKEW)
    return True, ""


# ---------------------------------------------------------------------------
# Env-only key material + client/server separation
# ---------------------------------------------------------------------------

def _first_env(env: Mapping[str, str], *names: str) -> Optional[str]:
    for name in names:
        val = env.get(name)
        if val:
            return val.strip()
    return None


def load_env_secrets(env: Optional[Mapping[str, str]] = None) -> dict:
    """Read TX + server key material from env vars ONLY.

    Returns ``{"client": <str>, "server": <str>}`` (nsec or 64-hex). Raises
    ``EnvKeyError`` when either side is missing — there is deliberately no CLI
    fallback.
    """
    env = os.environ if env is None else env
    client = _first_env(env, ENV_CLIENT_NSEC, ENV_CLIENT_HEX,
                        ENV_CLIENT_ALIAS_NSEC, ENV_CLIENT_ALIAS_HEX)
    server = _first_env(env, ENV_SERVER_NSEC, ENV_SERVER_HEX)
    if not client:
        raise EnvKeyError(
            "missing TX client key: set {} or {} (env only, never a CLI arg)"
            .format(ENV_CLIENT_NSEC, ENV_CLIENT_HEX))
    if not server:
        raise EnvKeyError(
            "missing board server key: set {} or {} (needed for the "
            "client!=server assertion)".format(ENV_SERVER_NSEC, ENV_SERVER_HEX))
    return {"client": client, "server": server}


def assert_keys_differ(client_pub_hex: str, server_pub_hex: str) -> None:
    """ADR §2.3: the client key MUST differ from the server key."""
    if not client_pub_hex or not server_pub_hex:
        raise KeyCollisionError("missing pubkey for the key-difference check")
    if client_pub_hex.lower() == server_pub_hex.lower():
        raise KeyCollisionError(
            "client key == server key ({}…) — refusing to start: the TX "
            "listener and the board server must use distinct keys"
            .format(client_pub_hex[:16]))


#: The single env-only accessor (card t_4c98fbe7): this is an alias of
#: ``keymaterial.load_keys``, not a second implementation.
load_keys = keymaterial.load_keys


def load_and_check_keys(env: Optional[Mapping[str, str]] = None) -> tuple:
    """Load both keys from the environment and enforce the separation invariant.

    Thin wrapper over :func:`keymaterial.load_keys` (the sole env-only source).
    """
    km = keymaterial.load_keys(
        client_names=keymaterial.TX_CLIENT_NSEC_NAMES,
        client_hex_names=keymaterial.TX_CLIENT_HEX_NAMES)
    import nostr_sdk
    return (nostr_sdk.Keys.parse(km.client_secret),
            nostr_sdk.Keys.parse(km.server_secret))


# ---------------------------------------------------------------------------
# Relay failover set
# ---------------------------------------------------------------------------

def failover_relays(extra: Optional[list] = None) -> list:
    """Ordered relay set + optional extras, dead relays filtered, deduped."""
    out = []
    for url in list(FAILOVER_RELAYS) + list(extra or []):
        if not url:
            continue
        url = url.strip()
        if not url or url in DEAD_RELAYS or url in out:
            continue
        out.append(url)
    return out


# ---------------------------------------------------------------------------
# TX-side ARMED listener (broad subscribe + allowlist + freshness watchdog)
# ---------------------------------------------------------------------------

class TxArmedListener:
    """TX-side ARMED listener.

    Subscribes broad to the bus and keeps the most recent ARMED that passes
    ``parse_armed`` (allowlist + self + schema + skew). Exposes ``check_stale``
    / ``tick`` so the caller can ABORT the session when the handshake goes
    quiet for more than ``STALE_ABORT`` seconds.
    """

    def __init__(self, bus, allowed_npubs: Optional[set] = None,
                 self_pubkey: Optional[str] = None,
                 max_skew: float = MAX_CREATED_AT_SKEW,
                 stale_abort: float = STALE_ABORT,
                 now_fn: Optional[Callable] = None,
                 log: Callable = print):
        self.bus = bus
        self.allowed_npubs = set(allowed_npubs) if allowed_npubs else None
        self.self_pubkey = self_pubkey
        self.max_skew = max_skew
        self.stale_abort = stale_abort
        self.now_fn = now_fn or time.time
        self.log = log
        self.started_at = self.now_fn()
        self.last_armed: Optional[dict] = None
        self.last_armed_at: Optional[float] = None
        self.aborted = False
        self.abort_reason = ""
        self.dropped = []          # reasons for rejected events (observability)
        self._handler_task = None

    async def start(self):
        """Subscribe broad to the bus and begin filtering ARMED messages."""
        await self.bus.subscribe(self._on_event)

    async def _on_event(self, event) -> None:
        ok, reason = parse_armed(event, now=self.now_fn(),
                                 allowed_npubs=self.allowed_npubs,
                                 self_pubkey=self.self_pubkey)
        if not ok:
            self.dropped.append(reason)
            return
        self.last_armed = event
        self.last_armed_at = self.now_fn()

    def check_stale(self, now: Optional[float] = None) -> bool:
        """True if the last good ARMED is stale more than ``stale_abort`` s."""
        if self.last_armed_at is None:
            return False
        now = now if now is not None else self.now_fn()
        return (now - self.last_armed_at) > self.stale_abort

    def abort(self, reason: str) -> None:
        """Record + log the abort reason (idempotent)."""
        if self.aborted:
            return
        self.aborted = True
        self.abort_reason = reason
        self.log("[tx-armed] ABORT: {}".format(reason))

    def tick(self, now: Optional[float] = None) -> bool:
        """Run one watchdog step. Returns True once the session has aborted.

        Aborts (a) when the last good ARMED is stale > ``STALE_ABORT`` s, or
        (b) when NO ARMED has ever arrived within ``STALE_ABORT`` s of start.
        """
        if self.aborted:
            return True
        now = now if now is not None else self.now_fn()
        if self.check_stale(now):
            age = now - self.last_armed_at
            self.abort("stale ARMED: no fresh ARMED for {:.1f}s > {}s "
                       "(last session_id={})".format(
                           age, self.stale_abort,
                           (self.last_armed or {}).get("session_id", "?")))
            return True
        if self.last_armed_at is None and (now - self.started_at) > self.stale_abort:
            self.abort("no ARMED received within {}s of start".format(
                self.stale_abort))
            return True
        return False

    async def watch(self, sleep: Optional[Callable] = None,
                    poll_interval: float = 1.0,
                    max_ticks: Optional[int] = None,
                    timeout: Optional[float] = None) -> str:
        """Poll ``tick`` until the session aborts (or a bound is hit).

        Returns the abort reason ("" when the loop exited without aborting).
        """
        sleep = sleep or asyncio.sleep
        ticks = 0
        while not self.aborted:
            if max_ticks is not None and ticks >= max_ticks:
                break
            await sleep(poll_interval)
            ticks += 1
            if self.tick():
                break
            if timeout is not None and (self.now_fn() - self.started_at) >= timeout:
                break
        return self.abort_reason


# ---------------------------------------------------------------------------
# Gift-wrap transport (reuses the cvm_board_server.py HandleNotification path)
# ---------------------------------------------------------------------------

def _extract_p_tag(event) -> Optional[str]:
    """First 'p' tag value from a nostr_sdk Event (same as cvm_board_server)."""
    try:
        for tag in event.tags().to_vec():
            v = tag.as_vec()
            if v and v[0] == "p" and len(v) >= 2:
                return v[1]
    except Exception:
        pass
    return None


class NostrRxTransport:
    """Broad kind-1059 subscribe + client-side unwrap of RX's ARMED wraps.

    Injected handles (``nostr`` module, ``signer``, ``client``) keep the wrap
    seam unit-testable; the real wiring builds them in :func:`run`.
    """

    def __init__(self, nostr, signer, client, client_pubkey_hex: str,
                 log: Callable = print):
        self.nostr = nostr
        self.signer = signer
        self.client = client
        self.client_pubkey_hex = client_pubkey_hex
        self.log = log
        self._handler: Optional[Callable] = None

    async def subscribe(self, handler) -> None:
        """BROAD kind-1059 subscription — the ``#p`` check is client-side."""
        self._handler = handler
        flt = self.nostr.Filter().kinds([self.nostr.Kind(KIND_GIFT_WRAP)])
        await self.client.subscribe(flt, None)

    async def handle_gift_wrap(self, event) -> None:
        """Unwrap an incoming kind-1059 event and feed the inner ARMED msg.

        Mirrors ``cvm_board_server._handle_request``: p-tag == our own key,
        ``UnwrappedGift.from_gift_wrap``, JSON content. The **unwrapped rumor
        author** is stamped onto the message — that is what the client-side npub
        allowlist checks (the outer wrap author is ephemeral).
        """
        p_tag = _extract_p_tag(event)
        if p_tag is None or p_tag != self.client_pubkey_hex:
            return  # not addressed to us
        unwrapped = await self.nostr.UnwrappedGift.from_gift_wrap(
            self.signer, event)
        inner = unwrapped.rumor()
        try:
            msg = json.loads(inner.content())
        except (ValueError, TypeError):
            return
        if not isinstance(msg, dict):
            return
        try:
            msg["author"] = inner.author().to_hex()
        except Exception:
            msg.setdefault("author", "")
        if self._handler is not None:
            await self._handler(msg)

    async def close(self) -> None:
        try:
            await self.client.shutdown()
        except Exception as exc:  # pragma: no cover - best-effort shutdown
            self.log("[tx-armed] shutdown: {}".format(exc))


class TxHandleNotification:
    """HandleNotification adapter for ``nostr_sdk.Client.handle_notifications``.

    Signature matches the uniffi trait: ``async def handle(relay_url,
    subscription_id, event)``; non-event messages are ignored.
    """

    def __init__(self, transport, log: Callable = print):
        self.transport = transport
        self.log = log

    async def handle(self, relay_url, subscription_id, event):
        try:
            await self.transport.handle_gift_wrap(event)
        except Exception as exc:
            self.log("[tx-armed] handle err: {}: {}".format(
                type(exc).__name__, exc))

    async def handle_msg(self, relay_url, msg):
        return None


# ---------------------------------------------------------------------------
# CLI + process wiring
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """CLI parser — NON-key options only (ADR §2.3: keys via env, never CLI)."""
    ap = argparse.ArgumentParser(
        description="TX-side ARMED listener (NIP-59 kind-1059) with freshness "
                    "watchdog — keys come from env vars only")
    ap.add_argument("--stop", required=True,
                    help="stop id (e.g. 50m) — required in GO mode")
    ap.add_argument("--rx-npub", dest="rx_npub",
                    default=os.environ.get(ENV_RX_NPUB),
                    help="RX publisher npub to allowlist (env: {})".format(
                        ENV_RX_NPUB))
    ap.add_argument("--relays", default="",
                    help="extra relays (comma-separated; dead ones filtered)")
    ap.add_argument("--poll-interval", dest="poll_interval", type=float,
                    default=1.0, help="watchdog poll period in seconds")
    ap.add_argument("--timeout", type=float, default=None,
                    help="give up after N seconds without a fresh ARMED")
    ap.add_argument("--max-ticks", dest="max_ticks", type=int, default=None,
                    help="stop after N watchdog polls (0 = never)")
    ap.add_argument("--dry-run", action="store_true",
                    help="validate env/keys/allowlist and exit without listening")
    return ap


def _npub_to_hex(nostr_sdk, npub: str) -> str:
    if isinstance(npub, str) and npub.startswith("npub1"):
        return nostr_sdk.PublicKey.parse(npub).to_hex()
    return npub


async def run(args, env: Optional[Mapping[str, str]] = None,
              bus=None, sleep: Optional[Callable] = None) -> int:
    """Wire the listener: env keys → broad subscribe → watchdog until abort."""
    # Keys: env only + client != server (asserted before anything is received).
    client_keys, _server_keys = load_and_check_keys(env)
    self_hex = client_keys.public_key().to_hex()

    envmap = os.environ if env is None else env
    rx_npub = args.rx_npub or envmap.get(ENV_RX_NPUB)
    if not rx_npub:
        raise EnvKeyError("missing RX npub: pass --rx-npub or set {}"
                          .format(ENV_RX_NPUB))

    if args.dry_run:
        print("[tx-armed] dry-run ok: stop={} self={}… keys differ".format(
            args.stop, self_hex[:16]), flush=True)
        return 0

    if bus is None:
        import nostr_sdk
        rx_hex = _npub_to_hex(nostr_sdk, rx_npub)
        signer = nostr_sdk.NostrSigner.keys(client_keys)
        client = nostr_sdk.ClientBuilder().signer(signer).build()
        for url in failover_relays(args.relays.split(",") if args.relays
                                   else None):
            try:
                await client.add_relay(nostr_sdk.RelayUrl.parse(url))
            except Exception as exc:
                print("[tx-armed] relay add failed {}: {}".format(url, exc),
                      file=sys.stderr)
        await client.connect()
        bus = NostrRxTransport(nostr_sdk, signer=signer, client=client,
                               client_pubkey_hex=self_hex)
    else:
        rx_hex = rx_npub

    listener = TxArmedListener(bus, allowed_npubs={rx_hex},
                               self_pubkey=self_hex)
    await listener.start()
    print("[tx-armed] listening stop={} allowlist={} relays={}".format(
        args.stop, rx_hex[:16], len(failover_relays())), flush=True)
    await listener.watch(sleep=sleep, poll_interval=args.poll_interval,
                         max_ticks=args.max_ticks, timeout=args.timeout)
    if listener.aborted:
        print("[tx-armed] session aborted: {}".format(listener.abort_reason),
              flush=True)
        return 1
    return 0


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(run(args))
    except (EnvKeyError, KeyCollisionError) as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
