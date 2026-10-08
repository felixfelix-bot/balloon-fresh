#!/usr/bin/env python3
"""cvm_verdict_publisher.py — RX-side VERDICT publisher (ADR §2.5) with the
real Nostr transport.

``cvm_sync.py`` (P1) shipped the verdict *shape* behind an injected ``bus``
seam (``VerdictPublisher.publish_verdict``). This module supplies the missing
production half: it turns ``range_check.py`` output into ONE gift-wrapped
NIP-59 kind-1059 event per completed stop/config scan, on the same channel and
with the same transport rules as the ARMED/GO handshake
(``docs/ADR-range-sync-cvm.md`` §2.3/§2.5):

  * **config-end granularity** — exactly one verdict message per completed
    config scan (one per stop), NEVER per packet, regardless of packet count.
    The per-config OK/THIN/MISS breakdown + counts travel INSIDE that single
    message.
  * **inline resend JSON** — the ``resend-<stop>.json`` file content is
    inlined verbatim (deep copy) into the message body, so the peer can act
    on the selective re-send without a second channel.
  * **session linkage** — ``session_id`` + ``stop`` correlate every verdict
    back to the ARMED session from phase 1; ``validate_session_link()``
    refuses a verdict whose linkage does not match the pinned ``armed.json``.
  * **transport reused, not re-implemented** — ``NostrTxTransport`` (and the
    env-only key loading, client!=server assertion, and relay failover set)
    comes from ``cvm_armed_publisher.py``, which itself mirrors
    ``cvm_board_server.py`` (``nostr_sdk ClientBuilder``, ``NostrSigner.keys``,
    ``gift_wrap``). The inner envelope is kind 25910; the outer event is the
    NIP-59 kind-1059 wrap — a plaintext kind-30315 tally is never constructed
    (RF recon leak, ADR §Context), and ``KIND_GIFT_WRAP`` is imported from
    ``cvm_sync`` (ADR-033 single wrap path).
  * **keys via env vars only** — ``CVM_RX_NSEC``/``CVM_RX_HEX``
    (+ ``CVM_CLIENT_*`` alias) and ``CVM_SERVER_NSEC``/``CVM_SERVER_HEX``;
    the CLI parser exposes NO key-bearing option and ``assert_keys_differ()``
    aborts startup when client == server.
  * **the verdict one-liner reuses the analysis formatter** — the summary is
    ``range_check.verdict_line()`` itself, so the wire text and the operator's
    terminal can never drift.

Message shape (inner event content, JSON):

    { "type": "VERDICT", "session_id": "2609130435a3f", "stop": "50m",
      "summary": "50m s2609130435a3f: GAPS c1:THIN 3/10 c2:MISS (1/3 clean)",
      "per_config": [ {"idx":0,"label":"cfg-0","n_pkts":10,"counted":10,
                       "status":"OK"}, ... ],
      "resend_json": { "name": "resend-50m-...", "configs": [ ... ] } | null,
      "log_gap": false, "stat_count": 9,
      "created_at": 1789148009, "author": "<hex pubkey>" }

Usage (RX machine, keys in env):

    export CVM_RX_NSEC=nsec1...          # RX publishing (client) key
    export CVM_SERVER_NSEC=nsec1...      # board server key (must differ)
    export CVM_TX_NPUB=npub1...
    # range_check output (a list, or {"results": [...], "resend_json": {...}})
    python3 range_check.py --dist 50m --session 2609130435a3f --json > out.json
    python3 cvm_verdict_publisher.py --session-id 2609130435a3f --stop 50m \
        --results out.json --resend configs/resend/resend-50m-2609130435a3f.json \
        --armed logs/s2609130435a3f-go<epoch>/armed.json

Run:  python3 -m pytest test_cvm_verdict_publisher.py -v
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
import sys
import time
from typing import Any, Mapping, Optional, Sequence

# Sibling imports (cvm_sync, cvm_armed_publisher, range_check) — same
# convention as the other tools/ modules.
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import cvm_sync as cvm  # noqa: E402,F401  (message layer, P1)
import range_check as rc  # noqa: E402  (the ONE verdict-line formatter)
from cvm_sync import KIND_GIFT_WRAP  # noqa: E402  (ADR-033: single wrap path)
from cvm_armed_publisher import (  # noqa: E402
    ENV_TX_NPUB,
    KIND_CVM_RPC,
    EnvKeyError,
    KeyCollisionError,
    NostrTxTransport,
    PlaintextKindError,
    assert_keys_differ,
    failover_relays,
    load_and_check_keys,
    load_env_secrets,
    validate_session_id,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VERDICT_TYPE = "VERDICT"

#: Per-config verdict enum — OK / THIN / MISS ONLY (range_check semantics).
VERDICT_STATUSES = ("OK", "THIN", "MISS")

#: Fields every verdict message must carry.
VERDICT_REQUIRED = (
    "type", "session_id", "stop", "summary", "per_config", "resend_json",
    "created_at",
)

#: Fields that correlate a verdict back to the phase-1 ARMED session.
LINK_FIELDS = ("session_id", "stop")

#: Message types that must never be published (plaintext RF-recon leak).
FORBIDDEN_PLAINTEXT_TYPES = ("TALLY",)

# The wrap kind is owned by cvm_sync; a second definition here would fork the
# ADR-033 single-path pin (test_giftwrap_single_path.py).
if KIND_GIFT_WRAP != 1059:  # pragma: no cover - import-time contract check
    raise RuntimeError("cvm_sync.KIND_GIFT_WRAP drifted from 1059: {!r}"
                       .format(KIND_GIFT_WRAP))


class VerdictError(ValueError):
    """A verdict payload/linkage problem (usage-class, exit code 2)."""


# ---------------------------------------------------------------------------
# Payload construction + validation
# ---------------------------------------------------------------------------

def _nonneg_int(name: str, value: Any) -> int:
    """Coerce ``value`` to a non-negative int or raise VerdictError."""
    if isinstance(value, bool) or value is None:
        raise VerdictError("{} must be a non-negative int, got {!r}"
                           .format(name, value))
    try:
        out = int(value)
    except (TypeError, ValueError):
        raise VerdictError("{} must be a non-negative int, got {!r}"
                           .format(name, value))
    if out < 0:
        raise VerdictError("{} must be >= 0, got {}".format(name, out))
    return out


def normalize_per_config(results: Sequence[Mapping[str, Any]]) -> list:
    """Normalize range_check per-config rows to the wire shape.

    Pinned key set (matches ``cvm_sync.VerdictPublisher``): idx, label,
    n_pkts, counted, status. Unknown statuses are refused.
    """
    if isinstance(results, (str, bytes)) or not isinstance(results, Sequence):
        raise VerdictError("per-config results must be a list")
    out = []
    for row in results:
        if not isinstance(row, Mapping):
            raise VerdictError("per-config row must be an object, got {!r}"
                               .format(type(row).__name__))
        status = row.get("status")
        if status not in VERDICT_STATUSES:
            raise VerdictError(
                "unknown config status {!r} (expected one of {})".format(
                    status, ", ".join(VERDICT_STATUSES)))
        out.append({
            "idx": _nonneg_int("idx", row.get("idx")),
            "label": str(row.get("label", "?")),
            "n_pkts": _nonneg_int("n_pkts", row.get("n_pkts")),
            "counted": _nonneg_int("counted", row.get("counted")),
            "status": status,
        })
    return out


def build_verdict(session_id: str, stop: str,
                  results: Sequence[Mapping[str, Any]],
                  resend_json: Optional[Mapping[str, Any]] = None,
                  stat_count: int = 0,
                  created_at: Optional[int] = None,
                  author: Optional[str] = None) -> dict:
    """Build ONE VERDICT message dict (never per-packet).

    An empty ``results`` list is the LOGGING GAP variant: zero STAT rows for
    the session (rx logger problem, not RF) — no resend file exists, so
    ``resend_json`` is normally None there.
    """
    if not validate_session_id(session_id):
        raise VerdictError("bad session_id {!r} (expected %y%m%d%H%M + 3-hex "
                           "nonce from the ARMED session)".format(session_id))
    if not stop or str(stop) == "?":
        raise VerdictError("verdict needs a real stop id, got {!r}".format(stop))
    per_config = normalize_per_config(results)
    log_gap = len(per_config) == 0
    kind = "PASS" if (per_config and all(
        c["status"] == "OK" for c in per_config)) else "GAPS"
    if log_gap:
        summary = rc.verdict_line(stop, session_id, [], "LOGGING_GAP")
    else:
        summary = rc.verdict_line(stop, session_id, per_config, kind)
    return {
        "type": VERDICT_TYPE,
        "session_id": str(session_id),
        "stop": str(stop),
        "summary": summary,
        "per_config": per_config,
        # Inlined VERBATIM (deep copy) so the peer never has to re-read a file.
        "resend_json": copy.deepcopy(resend_json) if resend_json is not None
        else None,
        "log_gap": log_gap,
        "stat_count": _nonneg_int("stat_count", stat_count),
        "created_at": int(created_at if created_at is not None else time.time()),
        "author": author or "",
    }


def validate_verdict(msg: Any) -> tuple:
    """Validate a VERDICT message. Returns ``(ok, reason)``."""
    if not isinstance(msg, Mapping):
        return False, "verdict must be an object"
    if msg.get("type") != VERDICT_TYPE:
        return False, "not a VERDICT message (type={!r})".format(msg.get("type"))
    for field in VERDICT_REQUIRED:
        if field not in msg:
            return False, "missing required field: {}".format(field)
    if not validate_session_id(msg.get("session_id")):
        return False, "bad session_id: {!r}".format(msg.get("session_id"))
    if not msg.get("stop") or str(msg.get("stop")) == "?":
        return False, "verdict carries no real stop id"
    per_config = msg.get("per_config")
    if not isinstance(per_config, list):
        return False, "per_config must be a list"
    if msg.get("log_gap") and per_config:
        return False, "log_gap verdict must not carry per_config rows"
    for i, row in enumerate(per_config):
        if not isinstance(row, Mapping):
            return False, "per_config[{}] must be an object".format(i)
        if row.get("status") not in VERDICT_STATUSES:
            return False, "per_config[{}] status {!r} not in {}".format(
                i, row.get("status"), VERDICT_STATUSES)
        for field in ("idx", "n_pkts", "counted"):
            try:
                _nonneg_int(field, row.get(field))
            except VerdictError as exc:
                return False, "per_config[{}]: {}".format(i, exc)
    resend = msg.get("resend_json")
    if resend is not None and not isinstance(resend, Mapping):
        return False, "resend_json must be an inline object or null"
    return True, ""


def validate_session_link(verdict: Mapping[str, Any],
                          armed: Mapping[str, Any]) -> tuple:
    """Check a verdict's ``session_id``/``stop`` against an ARMED message.

    Returns ``(ok, reason)``. This is what keeps a verdict attributable to the
    ARMED session of phase 1 — a mismatched linkage must never be published.
    """
    for name, src in (("verdict", verdict), ("ARMED", armed)):
        if not isinstance(src, Mapping):
            return False, "{} must be an object".format(name)
    armed_sid = armed.get("session_id")
    verdict_sid = verdict.get("session_id")
    if not armed_sid or not verdict_sid:
        return False, "missing session_id on verdict or ARMED message"
    if str(verdict_sid) != str(armed_sid):
        return False, "session_id mismatch: verdict {} != ARMED {}".format(
            verdict_sid, armed_sid)
    armed_stop = armed.get("stop")
    verdict_stop = verdict.get("stop")
    if not armed_stop or not verdict_stop:
        return False, "missing stop on verdict or ARMED message"
    if str(verdict_stop) != str(armed_stop):
        return False, "stop mismatch: verdict {} != ARMED {}".format(
            verdict_stop, armed_stop)
    return True, ""


# ---------------------------------------------------------------------------
# Publisher — config-end granularity, one message per completed config scan
# ---------------------------------------------------------------------------

class RxVerdictPublisher:
    """Publishes exactly ONE verdict per completed config scan (stop).

    ``session_id``/``stop`` are bound at construction from the phase-1 ARMED
    session, and every message repeats them as the linkage fields.
    """

    def __init__(self, bus, session_id: str, stop: str, author: str = ""):
        if not validate_session_id(session_id):
            raise ValueError("bad session_id {!r} (expected %y%m%d%H%M + "
                             "3-hex nonce)".format(session_id))
        if not stop or str(stop) == "?":
            raise ValueError("verdict needs a real --stop (got {!r})"
                             .format(stop))
        self.bus = bus
        self.session_id = str(session_id)
        self.stop = str(stop)
        self.author = author or ""
        self.published = []

    @property
    def published_count(self) -> int:
        """Number of verdict messages published (config-end calls made)."""
        return len(self.published)

    def build(self, results, resend_json=None, stat_count: int = 0,
              created_at: Optional[int] = None) -> dict:
        """Build the single verdict payload for a completed config scan."""
        return build_verdict(self.session_id, self.stop, results,
                             resend_json=resend_json, stat_count=stat_count,
                             created_at=created_at, author=self.author)

    async def publish(self, msg: dict) -> dict:
        """Publish a pre-built verdict (the ONLY send path)."""
        if msg.get("type") in FORBIDDEN_PLAINTEXT_TYPES:
            raise PlaintextKindError(
                "refusing to publish a plaintext {} frame".format(msg["type"]))
        ok, reason = validate_verdict(msg)
        if not ok:
            raise VerdictError("refusing to publish an invalid VERDICT: {}"
                               .format(reason))
        await self.bus.publish(msg)
        self.published.append(msg)
        return msg

    async def publish_config_end(self, results, resend_json=None,
                                 stat_count: int = 0,
                                 created_at: Optional[int] = None) -> dict:
        """One verdict per completed config scan — never per packet.

        Called once when a stop's capture is done; the per-config breakdown
        for every config of that stop rides inside this single message, so the
        wire message count is independent of the packet count.
        """
        return await self.publish(self.build(results,
                                             resend_json=resend_json,
                                             stat_count=stat_count,
                                             created_at=created_at))

    # Alias: the ADR calls this "the verdict publisher"; same single-message
    # semantics.
    publish_verdict = publish_config_end


# ---------------------------------------------------------------------------
# Input ingestion
# ---------------------------------------------------------------------------

def load_results(path: str) -> tuple:
    """Load range_check output. Returns ``(results, meta)``.

    Accepts a bare list of per-config rows, or an object with
    ``results``/``per_config`` plus optional ``resend_json``/``stat_count``/
    ``session_id``/``stop`` metadata. ``-`` reads stdin.
    """
    if path == "-":
        raw = sys.stdin.read()
    else:
        with open(path) as fh:
            raw = fh.read()
    data = json.loads(raw)
    if isinstance(data, list):
        return data, {}
    if isinstance(data, dict):
        results = data.get("results", data.get("per_config"))
        if results is None:
            raise VerdictError("results JSON object needs a 'results' or "
                               "'per_config' list")
        meta = {k: v for k, v in data.items()
                if k not in ("results", "per_config")}
        return results, meta
    raise VerdictError("results JSON must be a list or an object")


def npub_to_hex(nostr_sdk, npub: str) -> str:
    """Accept an npub or a raw 64-hex pubkey; return hex."""
    if str(npub).startswith("npub1"):
        return nostr_sdk.PublicKey.parse(npub).to_hex()
    return npub


# ---------------------------------------------------------------------------
# CLI + process wiring
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """CLI parser — NON-key options only (ADR §2.3: keys via env, never CLI)."""
    ap = argparse.ArgumentParser(
        description="RX-side VERDICT publisher (NIP-59 kind-1059) — one "
                    "verdict per completed config scan, keys from env vars only",
        epilog="Keys come from env vars only: CVM_RX_NSEC / CVM_RX_HEX "
               "(+ CVM_CLIENT_* alias) and CVM_SERVER_NSEC / CVM_SERVER_HEX "
               "(client and server keys must differ). TX recipient: "
               "CVM_TX_NPUB.")
    ap.add_argument("--session-id", dest="session_id", required=True,
                    help="ARMED session id from phase 1 (linkage field)")
    ap.add_argument("--stop", required=True, help="stop id (e.g. 50m)")
    ap.add_argument("--results", required=True,
                    help="range_check per-config results JSON (path or '-')")
    ap.add_argument("--resend", default=None,
                    help="resend-<stop>.json to inline verbatim into the body")
    ap.add_argument("--armed", default=None,
                    help="armed.json to cross-check the session linkage")
    ap.add_argument("--stat-count", dest="stat_count", type=int, default=None,
                    help="STAT rows for the session (LOGGING GAP detection)")
    ap.add_argument("--author", default="", help="author pubkey hex (optional)")
    ap.add_argument("--tx-npub", dest="tx_npub",
                    default=os.environ.get(ENV_TX_NPUB),
                    help="TX npub to wrap the verdict for (env: {})"
                    .format(ENV_TX_NPUB))
    ap.add_argument("--relays", default="",
                    help="extra relays (comma-separated; dead ones filtered)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the verdict payload and exit without publishing")
    return ap


async def run(args, env: Optional[Mapping[str, str]] = None, bus=None) -> int:
    """Wire the publisher: env keys -> gift-wrap bus -> one verdict per stop."""
    # Keys: env only + client != server (asserted before anything is sent).
    client_keys, _server_keys = load_and_check_keys(env)

    if not args.tx_npub:
        raise EnvKeyError("missing TX npub: pass --tx-npub or set {}"
                          .format(ENV_TX_NPUB))

    results, meta = load_results(args.results)
    resend = None
    if args.resend:
        with open(args.resend) as fh:
            resend = json.load(fh)
    elif meta.get("resend_json") is not None:
        resend = meta["resend_json"]
    stat_count = args.stat_count if args.stat_count is not None \
        else int(meta.get("stat_count") or 0)

    if args.armed:
        with open(args.armed) as fh:
            armed = json.load(fh)
        ok, reason = validate_session_link(
            {"session_id": args.session_id, "stop": args.stop}, armed)
        if not ok:
            raise VerdictError("verdict/ARMED linkage failed: {}".format(reason))

    if args.dry_run:
        print(json.dumps(build_verdict(args.session_id, args.stop, results,
                                       resend_json=resend,
                                       stat_count=stat_count,
                                       author=args.author), indent=2))
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
                print("[rx-verdict] relay add failed {}: {}".format(url, exc),
                      file=sys.stderr)
        await client.connect()
        bus = NostrTxTransport(
            nostr_sdk, signer=signer, client=client,
            tx_pubkey_hex=npub_to_hex(nostr_sdk, args.tx_npub),
            author_pubkey_hex=client_keys.public_key().to_hex())

    publisher = RxVerdictPublisher(bus, args.session_id, args.stop,
                                   author=args.author)
    msg = await publisher.publish_config_end(results, resend_json=resend,
                                             stat_count=stat_count)
    print("[rx-verdict] published {} verdict(s) session={} stop={} "
          "configs={} log_gap={} relays={}".format(
              publisher.published_count, msg["session_id"], msg["stop"],
              len(msg["per_config"]), msg["log_gap"], len(failover_relays())),
          flush=True)
    return 0


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return asyncio.run(run(args))
    except (EnvKeyError, KeyCollisionError, PlaintextKindError, VerdictError,
            OSError, ValueError) as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
