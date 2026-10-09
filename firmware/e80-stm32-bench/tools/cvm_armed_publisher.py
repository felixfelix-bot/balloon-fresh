#!/usr/bin/env python3
"""cvm_armed_publisher.py — RX-side ARMED publisher with real Nostr transport.

Phase-3 wiring for the CVM range-sync handshake (docs/ADR-range-sync-cvm.md
§2.3). ``cvm_sync.py`` (P1) ships the *message layer* — ``generate_session_id``,
``build_armed``, ``ArmedPublisher.rebroadcast_loop`` — but deliberately leaves
the relay pool as an injected ``bus`` seam. This module supplies the missing
production bus:

  * keys read from **env vars only, never CLI args** (ADR §2.3)
  * the client key **must differ** from the server key — asserted at startup
  * ARMED is published as a **NIP-59 kind-1059 gift-wrapped** event addressed
    to the TX npub; a plaintext kind-30315 tally is NEVER emitted (RF recon
    leak, ADR §Context)
  * relay failover set: the exact five-host set defined ONCE below as
    :data:`FAILOVER_RELAYS` — ``relay.contextvm.org`` is DEAD
    (verified 2026-08-23) and is filtered out even if supplied
  * re-broadcast every 10-15 s until a GO event from TX is observed on the
    subscription, then stop
  * replays are idempotent: identical session fields, ``seq`` increments

Transport reuses ~75% of ``cvm_board_server.py``'s pattern verbatim:
``nostr_sdk.ClientBuilder().signer(NostrSigner.keys(...))``, ``add_relay``,
broad ``kind=1059`` subscribe (the ``#p`` filter is unreliable on some relays,
so the p-tag check is client-side), ``nostr_sdk.UnsignedEvent.from_json`` +
``nostr_sdk.gift_wrap`` + ``client.send_event``.

The module imports cleanly WITHOUT ``nostr_sdk`` installed: the SDK is only
touched inside the transport / key-loading functions, so the pure logic
(session id, payload schema, env parsing, relay set, loop wiring, dedupe) is
unit-testable in a bare Python image.

Usage (RX machine, keys in env):

    export CVM_RX_NSEC=nsec1...          # RX publishing (client) key
    export CVM_SERVER_NSEC=nsec1...      # board server key (must differ)
    export CVM_TX_NPUB=npub1...
    python3 cvm_armed_publisher.py --stop 50m \
        --configs configs/per-stop/stop-50m.json

Run:  python3 -m pytest test_cvm_armed_publisher.py -v
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import random
import re
import sys
import time
from typing import Any, Awaitable, Callable, Mapping, Optional

# Sibling imports (cvm_sync, e80_bench_ctl…) — same convention as the other
# tools/ modules.
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import cvm_sync as cvm  # noqa: E402
from cvm_sync import KIND_GIFT_WRAP, ARMED_REQUIRED  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: RX is the sole session authority: strftime %y%m%d%H%M + 3 lowercase-hex
#: nonce. The strftime directives arrive fully expanded — no '%' or URL-unsafe
#: residue survives into the session id (it is used in log dir names).
SESSION_ID_RE = re.compile(r"^\d{10}[0-9a-f]{3}$")

#: Inner (gift-wrapped) content kind — the CVM JSON-RPC envelope used by
#: cvm_board_server.py. NOT a public/plaintext kind.
KIND_CVM_RPC = 25910

#: Env var names — the ONLY place key material may come from.
ENV_CLIENT_NSEC = "CVM_RX_NSEC"
ENV_CLIENT_HEX = "CVM_RX_HEX"
ENV_CLIENT_ALIAS_NSEC = "CVM_CLIENT_NSEC"
ENV_CLIENT_ALIAS_HEX = "CVM_CLIENT_HEX"
ENV_SERVER_NSEC = "CVM_SERVER_NSEC"
ENV_SERVER_HEX = "CVM_SERVER_HEX"
ENV_TX_NPUB = "CVM_TX_NPUB"

#: THE single authoritative relay set for the Nostr NIP-59 **kind-1059
#: gift-wrap publishing path** (this module's transport, ``relay_failover``'s
#: fan-out, and every failover test): five BARE hostnames.
#:
#: The ordering is SIGNIFICANT and intentional — it is the failover preference
#: order — so do NOT add, remove, reorder, lowercase, strip or otherwise
#: normalise any entry (card t_7c9268b7). ``relay.contextvm.org`` is DEAD
#: (verified 2026-08-23) — never add it.
FAILOVER_RELAYS = [
    "nostr.mom",
    "relay.primal.net",
    "nos.lol",
    "relay2.contextvm.org",
    "relay.nostr.band",
]

#: The same set as ``wss://`` relay URLs, DERIVED (never hand-maintained) from
#: :data:`FAILOVER_RELAYS` so the host and URL views can never drift apart.
FAILOVER_RELAY_URLS = ["wss://" + host for host in FAILOVER_RELAYS]

DEAD_RELAYS = ("wss://relay.contextvm.org",)

#: Exactly the fields build_armed() carries (schema pinned by the ADR).
ARMED_FIELDS = ("type",) + tuple(ARMED_REQUIRED) + ("created_at", "author")


class EnvKeyError(RuntimeError):
    """A required key env var is absent (ADR §2.3: env only, never CLI)."""


class KeyCollisionError(RuntimeError):
    """Client and server keys are identical — refuses to start."""


class PlaintextKindError(RuntimeError):
    """A forbidden plaintext event kind was requested/constructed."""


# ---------------------------------------------------------------------------
# Session id + ARMED payload (RX sole authority)
# ---------------------------------------------------------------------------

def validate_session_id(session_id: str) -> bool:
    """True iff `session_id` is %y%m%d%H%M + 3 lowercase-hex nonce."""
    return bool(isinstance(session_id, str)
                and SESSION_ID_RE.match(session_id))


def generate_session_id(now: Optional[int] = None) -> str:
    """RX sole authority session id, validated against the wire contract."""
    sid = cvm.generate_session_id(now)
    if not validate_session_id(sid):
        raise ValueError("cvm_sync.generate_session_id produced illegal "
                         "session id: {!r}".format(sid))
    return sid


def build_armed_payload(session_id: str, stop: str, t_ready_utc: int,
                        preset_hash: str, seq: int,
                        created_at: Optional[int] = None,
                        author: Optional[str] = None) -> dict:
    """ARMED payload (session_id, stop, t_ready_utc, preset_hash, seq)."""
    if not validate_session_id(session_id):
        raise ValueError("bad session_id: {!r}".format(session_id))
    return cvm.build_armed(session_id, stop, t_ready_utc, preset_hash, seq,
                           created_at=created_at, author=author)


def arm_session(stop: str, t_ready_utc: int, preset_hash: str,
                now: Optional[int] = None, author: Optional[str] = None,
                session_id: Optional[str] = None) -> tuple:
    """Arm a session: RX invents the id, then builds seq=1 ARMED.

    Returns ``(session_id, armed_msg)``. The id is never taken from TX.
    """
    sid = session_id or generate_session_id(now)
    if not validate_session_id(sid):
        raise ValueError("bad --session-id: {!r}".format(sid))
    msg = build_armed_payload(sid, stop, t_ready_utc, preset_hash, 1,
                              author=author)
    return sid, msg


def preset_hash_for(path: Optional[str]) -> str:
    """Short content hash of a preset file (KNOW the preset you armed on)."""
    if not path:
        return ""
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:12]
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# Env-only key material + client/server separation
# ---------------------------------------------------------------------------

def _first_env(env: Mapping[str, str], *names: str) -> Optional[str]:
    for n in names:
        val = env.get(n)
        if val:
            return val.strip()
    return None


def load_env_secrets(env: Optional[Mapping[str, str]] = None) -> dict:
    """Read client + server key material from env vars ONLY.

    Returns ``{"client": <str>, "server": <str>}`` (nsec or 64-hex).
    Raises EnvKeyError when either side is missing — there is deliberately no
    CLI fallback.
    """
    env = os.environ if env is None else env
    client = _first_env(env, ENV_CLIENT_NSEC, ENV_CLIENT_HEX,
                        ENV_CLIENT_ALIAS_NSEC, ENV_CLIENT_ALIAS_HEX)
    server = _first_env(env, ENV_SERVER_NSEC, ENV_SERVER_HEX)
    if not client:
        raise EnvKeyError(
            "missing RX client key: set {} or {} (env only, never a CLI arg)"
            .format(ENV_CLIENT_NSEC, ENV_CLIENT_HEX))
    if not server:
        raise EnvKeyError(
            "missing board server key: set {} or {} (needed for the "
            "client!=server assertion)".format(ENV_SERVER_NSEC, ENV_SERVER_HEX))
    return {"client": client, "server": server}


def assert_keys_differ(client_pub_hex: str, server_pub_hex: str) -> None:
    """ADR §2.3: the client key MUST differ from the server key.

    A shared key makes the client unwrap its own gift wraps and self-deliver
    on the subscription — refuses to start instead.
    """
    if not client_pub_hex or not server_pub_hex:
        raise KeyCollisionError("missing pubkey for the key-difference check")
    if client_pub_hex.lower() == server_pub_hex.lower():
        raise KeyCollisionError(
            "client key == server key ({}…) — refusing to start: the RX "
            "publisher and the board server must use distinct keys"
            .format(client_pub_hex[:16]))


def load_keys(secret: str):
    """Parse an nsec/hex secret into nostr_sdk.Keys (lazy SDK import)."""
    import nostr_sdk
    return nostr_sdk.Keys.parse(secret)


def load_and_check_keys(env: Optional[Mapping[str, str]] = None) -> tuple:
    """Load both keys from env and enforce the separation invariant.

    Returns ``(client_keys, server_keys)``.
    """
    secrets = load_env_secrets(env)
    client_keys = load_keys(secrets["client"])
    server_keys = load_keys(secrets["server"])
    assert_keys_differ(client_keys.public_key().to_hex(),
                       server_keys.public_key().to_hex())
    return client_keys, server_keys


# ---------------------------------------------------------------------------
# Relay failover set
# ---------------------------------------------------------------------------

def failover_relays(extra: Optional[list] = None) -> list:
    """Ordered relay set + optional extras, dead relays filtered, deduped.

    Iterates the DERIVED URL view (:data:`FAILOVER_RELAY_URLS`), never the
    bare-host constant, so the return value stays a ``wss://`` URL list.
    """
    out = []
    for url in list(FAILOVER_RELAY_URLS) + list(extra or []):
        if not url:
            continue
        url = url.strip()
        if not url or url in DEAD_RELAYS or url in out:
            continue
        out.append(url)
    return out


# ---------------------------------------------------------------------------
# Gift-wrap transport (reuses the cvm_board_server.py pattern)
# ---------------------------------------------------------------------------

def build_inner_event(msg: dict, tx_pubkey_hex: str,
                      author_pubkey_hex: Optional[str] = None,
                      created_at: Optional[int] = None) -> dict:
    """Inner (private) event carrying the ARMED JSON — kind 25910, p=TX npub.

    The ARMED payload only ever travels as the *content of a gift-wrapped*
    event. Nothing here (or anywhere in this module) constructs kind 30315.
    """
    return {
        "pubkey": author_pubkey_hex or "",
        "kind": KIND_CVM_RPC,
        "tags": [["p", tx_pubkey_hex]],
        "content": json.dumps(msg, separators=(",", ":"), sort_keys=True),
        "created_at": int(created_at if created_at is not None else time.time()),
    }


class NostrTxTransport:
    """Gift-wrap publish + kind-1059 subscribe to the TX npub.

    Injected handles (``nostr`` module, ``signer``, ``client``) keep the wrap
    seam unit-testable; the real wiring builds them in :func:`run`.
    """

    def __init__(self, nostr, signer, client, tx_pubkey_hex: str,
                 tx_pubkey: Any = None, author_pubkey_hex: str = "",
                 log: Callable = print):
        self.nostr = nostr
        self.signer = signer
        self.client = client
        self.tx_pubkey_hex = tx_pubkey_hex
        self._tx_pk = tx_pubkey
        self.author_pubkey_hex = author_pubkey_hex
        self.log = log
        self._handler: Optional[Callable] = None

    async def publish(self, msg: dict) -> None:
        """Gift-wrap ``msg`` (kind-1059 outer) addressed to the TX npub.

        This is the ONLY path to the wire; the ARMED payload never leaves as
        a plaintext event (no public tally kind is ever constructed).
        """
        if msg.get("type") == "TALLY":
            raise PlaintextKindError("refusing to publish a plaintext tally")
        inner = build_inner_event(msg, self.tx_pubkey_hex,
                                  author_pubkey_hex=self.author_pubkey_hex)
        unsigned = self.nostr.UnsignedEvent.from_json(json.dumps(inner))
        # The ONLY path to the wire: NIP-59 wrap (outer kind 1059).
        wrapped = await self.nostr.gift_wrap(self.signer,
                                             self._tx_pubkey(), unsigned)
        await self.client.send_event(wrapped)

    async def subscribe(self, handler: Callable) -> None:
        """Broad kind-1059 subscription; p-tag filtered client-side."""
        self._handler = handler
        flt = self.nostr.Filter().kinds([self.nostr.Kind(KIND_GIFT_WRAP)])
        await self.client.subscribe(flt, None)

    async def handle_gift_wrap(self, event) -> None:
        """Unwrap an incoming kind-1059 event and feed the inner message.

        Mirrors cvm_board_server._handle_request: p-tag == our TX peer, then
        ``UnwrappedGift.from_gift_wrap``, then hand the JSON content to the
        subscriber (the GO detector).
        """
        p_tag = _extract_p_tag(event)
        if p_tag is None or p_tag != self.tx_pubkey_hex:
            return
        unwrapped = await self.nostr.UnwrappedGift.from_gift_wrap(
            self.signer, event)
        inner = unwrapped.rumor()
        if self._handler is None:
            return
        try:
            msg = json.loads(inner.content())
        except (ValueError, TypeError):
            return
        await self._handler(msg)

    async def close(self) -> None:
        try:
            await self.client.shutdown()
        except Exception as exc:  # pragma: no cover - best-effort shutdown
            self.log("[rx-armed] shutdown: {}".format(exc))

    def _tx_pubkey(self):
        if self._tx_pk is None:
            self._tx_pk = self.nostr.PublicKey.parse(self.tx_pubkey_hex)
        return self._tx_pk


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


# ---------------------------------------------------------------------------
# Repeat-until-GO loop + idempotent replay helpers
# ---------------------------------------------------------------------------

def is_go_event(event: dict, session_id: str) -> bool:
    """True iff ``event`` is a GO from TX on OUR session (never a replay)."""
    if not isinstance(event, dict) or event.get("type") != "GO":
        return False
    return event.get("session_id") == session_id


def make_go_handler(publisher, session_id: str) -> Callable:
    """Build the subscription handler that stops the loop on TX's GO."""
    async def _handler(event: dict) -> None:
        if is_go_event(event, session_id):
            publisher.observe_go()
    return _handler


def is_replay(seen: dict, incoming: dict) -> bool:
    """True iff ``incoming`` is a replay/downgrade of an already-seen frame.

    Same session and a non-advancing ``seq`` → safe to drop (idempotent
    re-broadcast: identical session fields, seq increments).
    """
    if not isinstance(seen, dict) or not isinstance(incoming, dict):
        return False
    if seen.get("session_id") != incoming.get("session_id"):
        return False
    try:
        return int(incoming.get("seq", 0)) <= int(seen.get("seq", 0))
    except (TypeError, ValueError):
        return False


class RxArmedPublisher(cvm.ArmedPublisher):
    """ARMED re-broadcaster with an injectable sleep (testability + bounds)."""

    async def rebroadcast_loop(self, min_interval: Optional[float] = None,
                               max_interval: Optional[float] = None,
                               go_check: Optional[Callable] = None,
                               sleep: Optional[Callable] = None,
                               max_ticks: Optional[int] = None) -> int:
        """Publish ARMED every [min,max]s until GO is observed.

        Returns the number of publishes. Idempotent: every frame carries the
        same session fields, ``seq`` increments (1,2,3,…).
        """
        lo = min_interval if min_interval is not None else self.min_interval
        hi = max_interval if max_interval is not None else self.max_interval
        sleep = sleep or asyncio.sleep
        ticks = 0
        while not self.go_observed:
            await self.publish()
            ticks += 1
            if go_check is not None:
                await go_check()
            if self.go_observed:
                break
            if max_ticks is not None and ticks >= max_ticks:
                break
            await sleep(random.uniform(lo, hi))
        return ticks


def build_publisher(bus, session_id: str, stop: str, t_ready_utc: int,
                    preset_hash: str, author: str = "") -> RxArmedPublisher:
    """RX-side publisher bound to the wire contract."""
    if not validate_session_id(session_id):
        raise ValueError("bad session_id: {!r}".format(session_id))
    return RxArmedPublisher(bus, session_id, stop, t_ready_utc, preset_hash,
                            author=author)


# ---------------------------------------------------------------------------
# CLI + process wiring
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """CLI parser — NON-key options only (ADR §2.3: keys via env, never CLI)."""
    ap = argparse.ArgumentParser(
        description="RX-side ARMED publisher (NIP-59 kind-1059) — keys come "
                    "from env vars only")
    ap.add_argument("--stop", required=True,
                    help="stop id (e.g. 50m) — required in GO mode")
    ap.add_argument("--configs", default=None,
                    help="per-stop preset file (hashed into preset_hash)")
    ap.add_argument("--preset-hash", dest="preset_hash", default=None,
                    help="explicit preset fingerprint (default: hash --configs)")
    ap.add_argument("--tx-npub", dest="tx_npub",
                    default=os.environ.get(ENV_TX_NPUB),
                    help="TX npub to wrap ARMED for (env: {})".format(ENV_TX_NPUB))
    ap.add_argument("--relays", default="",
                    help="extra relays (comma-separated; dead ones filtered)")
    ap.add_argument("--session-id", dest="session_id", default=None,
                    help="pin the session id (default: RX-generated)")
    ap.add_argument("--t-ready-utc", dest="t_ready_utc", type=int, default=None,
                    help="t_ready epoch (default: now + 30s)")
    ap.add_argument("--max-ticks", dest="max_ticks", type=int, default=None,
                    help="stop after N publishes even without GO (0 = never)")
    ap.add_argument("--dry-run", action="store_true",
                    help="validate env/keys/session and exit without publishing")
    return ap


async def run(args, env: Optional[Mapping[str, str]] = None,
              bus=None, sleep: Optional[Callable] = None) -> int:
    """Wire the publisher: env keys → gift-wrap bus → repeat until GO."""
    # Keys: env only + client != server (asserted before anything is sent).
    client_keys, _server_keys = load_and_check_keys(env)

    if not args.tx_npub:
        raise EnvKeyError("missing TX npub: pass --tx-npub or set {}"
                          .format(ENV_TX_NPUB))

    preset_hash = args.preset_hash or preset_hash_for(args.configs)
    t_ready = args.t_ready_utc if args.t_ready_utc is not None \
        else int(time.time()) + int(cvm.T0_MARGIN)
    session_id, _armed = arm_session(
        stop=args.stop, t_ready_utc=t_ready, preset_hash=preset_hash,
        session_id=args.session_id)

    if args.dry_run:
        return 0

    if bus is None:
        import nostr_sdk
        signer = nostr_sdk.NostrSigner.keys(client_keys)
        client = nostr_sdk.ClientBuilder().signer(signer).build()
        for url in failover_relays(args.relays.split(",") if args.relays
                                   else None):
            try:
                await client.add_relay(nostr_sdk.RelayUrl.parse(url))
            except Exception as exc:
                print("[rx-armed] relay add failed {}: {}".format(url, exc),
                      file=sys.stderr)
        await client.connect()
        bus = NostrTxTransport(
            nostr_sdk, signer=signer, client=client,
            tx_pubkey_hex=_npub_to_hex(nostr_sdk, args.tx_npub),
            author_pubkey_hex=client_keys.public_key().to_hex())

    publisher = build_publisher(bus, session_id=session_id, stop=args.stop,
                                t_ready_utc=t_ready, preset_hash=preset_hash,
                                author=getattr(args, "session_author", "") or "")
    await bus.subscribe(make_go_handler(publisher, session_id))
    print("[rx-armed] session={} stop={} relays={}".format(
        session_id, args.stop, len(failover_relays())), flush=True)
    ticks = await publisher.rebroadcast_loop(sleep=sleep,
                                             max_ticks=args.max_ticks)
    print("[rx-armed] {} publishes, go_observed={}".format(
        ticks, publisher.go_observed), flush=True)
    return 0


def _npub_to_hex(nostr_sdk, npub: str) -> str:
    if npub.startswith("npub1"):
        return nostr_sdk.PublicKey.parse(npub).to_hex()
    return npub


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.session_author = ""
    try:
        asyncio.run(run(args))
    except (EnvKeyError, KeyCollisionError, PlaintextKindError) as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
