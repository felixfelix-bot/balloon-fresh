#!/usr/bin/env python3
"""cvm_sync.py — CVM range-sync message layer (Phase 1, ADR-range-sync-cvm.md).

Replaces the manual T0+SESSION relay over Signal with a message-derived T0
carried by an ARMED message, and adds a verdict publisher that wraps
range_check.py output into the same channel.

Transport: gift-wrapped NIP-59 kind-1059 stored wrappers (durable + private),
reusing the cvm_board_server.py pattern (nostr_sdk ClientBuilder,
NostrSigner.keys, gift_wrap, HandleNotification, relay failover set). Keys
come from env vars, never CLI args. Client/server keys MUST differ.

This module is pure-Python and testable without Nostr: the relay pool is an
injected `bus` object with `async subscribe(handler)` and
`async publish(event_dict)`. The real Nostr wiring (gift wrap / unwrap /
relay failover) lives in cvm_board_server.py / cvm_campaign.py and is reused
by the publisher/subscriber when a real bus is provided.

Message shapes (inner event content, JSON):

    ARMED:
      { "type": "ARMED", "session_id": "2608301440a3f", "stop": "50m",
        "t_ready_utc": 1788096000, "preset_hash": "abc123", "seq": 1,
        "created_at": 1788096000, "author": "<hex pubkey>" }

    STARTED (anti split-brain — TX announces its start ON THE RX'S session):
      { "type": "STARTED", "session_id": "2608301440a3f", "stop": "50m",
        "t_ready_utc": 1788096000, "t0": 1788096030,
        "preset_hash": "abc123", "role": "tx", "seq": 1,
        "created_at": 1788096000, "author": "<hex pubkey>" }

    VERDICT:
      { "type": "VERDICT", "session_id": "...", "stop": "50m",
        "summary": "50m s2608301440a3f: GAPS c1:MISS c2:THIN 3/10 (1/3 clean)",
        "per_config": [ {"idx":0,"label":"...","n_pkts":10,"counted":10,
                         "status":"OK"}, ... ],
        "resend_json": { ... } | null }

RX is the SOLE session authority: session_id = %y%m%d%H%M + 3-hex nonce.
T0 = t_ready_utc + 30s margin. ARMED re-broadcast every 10-15s until GO.
TX freshness watchdog: reject created_at skew > 60s, abort if stale > 30s.

Split-brain guard: a TX that starts MANUALLY (legacy --t0 path) must echo a
LIVE RX session id and announce itself with a STARTED message, so a TX start
on an invented session id is visible immediately instead of surfacing later
as a false MISS/LOGGING GAP in the analysis.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import secrets
import time
import urllib.parse
from typing import Any, Awaitable, Callable, Optional

# Default working relays (verified 2026-08-23; relay.contextvm.org is DEAD).
DEFAULT_RELAYS = [
    "wss://relay.primal.net",
    "wss://nostr.mom",
    "wss://nos.lol",
    "wss://relay2.contextvm.org",
    "wss://relay.nostr.band",
]

# Gift-wrap kind (NIP-59 outer wrap) — same as cvm_board_server.py.
KIND_GIFT_WRAP = 1059

# T0 = t_ready_utc + T0_MARGIN seconds.
T0_MARGIN = 30.0

# Freshness watchdog bounds (seconds).
MAX_CREATED_AT_SKEW = 60.0   # reject ARMED whose created_at skew > 60s
STALE_ABORT = 30.0           # abort if last good ARMED stale > 30s

# ARMED re-broadcast interval bounds (seconds).
ARMED_MIN_INTERVAL = 10.0
ARMED_MAX_INTERVAL = 15.0

# Required ARMED fields (validate_armed). ``created_at`` is REQUIRED: an ARMED
# that omits it must never skip the freshness window (Gate-2.5 R1).
ARMED_REQUIRED = ("session_id", "stop", "t_ready_utc", "preset_hash", "seq",
                  "created_at")


# ---------------------------------------------------------------------------
# Session id + ARMED message (pure functions)
# ---------------------------------------------------------------------------

def _session_nonce() -> str:
    """3 lowercase-hex nonce from the CSPRNG (4096 space).

    ``secrets.randbelow`` — never ``random``: the session id disambiguates two
    arms in the same minute and must be unpredictable to a third party.
    """
    return "{:03x}".format(secrets.randbelow(0x1000))


def generate_session_id(now: Optional[int] = None) -> str:
    """RX sole authority: %y%m%d%H%M + 3-hex nonce.

    e.g. 2608301440a3f. The 3-hex nonce (4096 space) disambiguates two arms
    in the same minute and comes from ``secrets`` (CSPRNG), matching the
    authoritative ``cvm_armed_publisher.generate_session_id`` contract.

    The timestamp is percent-encoded with an empty safe set: strftime
    directives arrive fully expanded (plain digits), so the id carries no '%'
    or URL-unsafe residue — it is used verbatim in log dir names.
    """
    now = int(now if now is not None else time.time())
    ts = urllib.parse.quote(time.strftime("%y%m%d%H%M", time.gmtime(now)),
                            safe="")
    return ts + _session_nonce()


def build_armed(session_id: str, stop: str, t_ready_utc: int,
                preset_hash: str, seq: int,
                created_at: Optional[int] = None,
                author: Optional[str] = None) -> dict:
    """Build an ARMED message dict (JSON-serializable inner content)."""
    return {
        "type": "ARMED",
        "session_id": session_id,
        "stop": stop,
        "t_ready_utc": int(t_ready_utc),
        "preset_hash": preset_hash,
        "seq": int(seq),
        "created_at": int(created_at if created_at is not None else time.time()),
        "author": author or "",
    }


def build_started(session_id: str, stop: str,
                  t_ready_utc: Optional[int] = None,
                  t0: Optional[int] = None, preset_hash: str = "",
                  role: str = "tx", seq: int = 1,
                  created_at: Optional[int] = None,
                  author: Optional[str] = None) -> dict:
    """Build a STARTED message dict (JSON-serializable inner content).

    Anti split-brain: a TX start announces itself on the SAME session id
    the RX armed (`session_id` is echoed, never invented), carrying the T0
    it is actually running against. `t_ready_utc` / `t0` are None when the
    caller has no ARMED-derived anchor (a legacy manual start knows only
    its own --t0, so t_ready_utc = t0 - T0_MARGIN).
    """
    return {
        "type": "STARTED",
        "session_id": session_id,
        "stop": stop,
        "t_ready_utc": int(t_ready_utc) if t_ready_utc is not None else None,
        "t0": int(t0) if t0 is not None else None,
        "preset_hash": preset_hash,
        "role": role,
        "seq": int(seq),
        "created_at": int(created_at if created_at is not None else time.time()),
        "author": author or "",
    }


def compute_t0(armed: dict) -> int:
    """T0 = t_ready_utc + T0_MARGIN (message-derived, not clock boundary)."""
    return int(armed["t_ready_utc"]) + int(T0_MARGIN)


def validate_armed(msg: dict, now: Optional[int] = None,
                   allowed_npubs: Optional[set] = None) -> tuple:
    """Validate an ARMED message. Returns (ok, reason).

    Self-contained strict policy (deliberately does NOT import
    ``cvm_tx_listener`` — that module is a sibling deliverable and importing it
    would create a merge-order dependency):

    1. **structure** — a dict whose ``type`` is ``ARMED`` and which carries
       every ``ARMED_REQUIRED`` field. ``created_at`` is one of them, so an
       ARMED that omits it is rejected instead of silently bypassing the
       freshness window.
    2. **authorization FIRST** — when ``allowed_npubs`` is given the author is
       checked *before* any ``created_at`` parsing, so a hostile payload is
       rejected on identity and can never reach the arithmetic
       (crash-before-authz).
    3. **freshness** — ``created_at`` must be a strict ``int`` (bool / str /
       float / anything else is rejected with a reason, never cast via
       ``int()``) and its skew from ``now`` must be
       ``<= MAX_CREATED_AT_SKEW``.

    Never raises on hostile input: every rejection path returns ``(False,
    reason)``.
    """
    now = int(now if now is not None else time.time())
    if not isinstance(msg, dict) or msg.get("type") != "ARMED":
        return False, "not an ARMED message"
    for f in ARMED_REQUIRED:
        if f not in msg:
            return False, "missing required field: {}".format(f)
    # (2) authz before any parsing of the attacker-controlled payload
    if allowed_npubs is not None:
        author = msg.get("author", "")
        if author not in allowed_npubs:
            return False, "author not in allowlist: {}".format(str(author)[:16])
    # (3) freshness — strict int typing, no coercion of hostile input
    created = msg.get("created_at")
    if isinstance(created, bool) or not isinstance(created, int):
        return False, "bad created_at: {!r}".format(created)
    skew = abs(now - created)
    if skew > MAX_CREATED_AT_SKEW:
        return False, "created_at skew {}s > {}s".format(
            skew, MAX_CREATED_AT_SKEW)
    return True, ""


# ---------------------------------------------------------------------------
# ARMED publisher (RX side) — re-broadcast loop
# ---------------------------------------------------------------------------

class ArmedPublisher:
    """RX-side ARMED publisher.

    Publishes ARMED to the bus, re-broadcasting every 10-15s until GO is
    observed. Re-broadcasts are idempotent (same session_id; seq increments).
    """

    def __init__(self, bus, session_id: str, stop: str, t_ready_utc: int,
                 preset_hash: str, author: Optional[str] = None,
                 min_interval: float = ARMED_MIN_INTERVAL,
                 max_interval: float = ARMED_MAX_INTERVAL):
        self.bus = bus
        self.session_id = session_id
        self.stop = stop
        self.t_ready_utc = int(t_ready_utc)
        self.preset_hash = preset_hash
        self.author = author or ""
        self.min_interval = min_interval
        self.max_interval = max_interval
        self._seq = 0
        self.go_observed = False

    async def publish(self) -> dict:
        """Publish one ARMED message (seq increments). Returns the message."""
        self._seq += 1
        msg = build_armed(self.session_id, self.stop, self.t_ready_utc,
                          self.preset_hash, self._seq, author=self.author)
        await self.bus.publish(msg)
        return msg

    def observe_go(self):
        """Mark GO observed — the re-broadcast loop stops."""
        self.go_observed = True

    async def rebroadcast_loop(self, min_interval: Optional[float] = None,
                               max_interval: Optional[float] = None,
                               go_check: Optional[Callable] = None):
        """Re-broadcast ARMED every [min,max]s until GO observed.

        go_check: optional async callable invoked each tick; if it sets
        go_observed (or returns truthy), the loop exits. Defaults to polling
        self.go_observed.
        """
        lo = min_interval if min_interval is not None else self.min_interval
        hi = max_interval if max_interval is not None else self.max_interval
        while not self.go_observed:
            await self.publish()
            if go_check is not None:
                await go_check()
            if self.go_observed:
                break
            await asyncio.sleep(random.uniform(lo, hi))


# ---------------------------------------------------------------------------
# ARMED subscriber (TX side) — freshness watchdog
# ---------------------------------------------------------------------------

class ArmedSubscriber:
    """TX-side ARMED subscriber.

    Subscribes broad to the bus, filters by npub allowlist + freshness
    (created_at skew > 60s rejected). Tracks the last good ARMED and exposes
    check_stale() to abort when it goes stale > 30s.
    """

    def __init__(self, bus, allowed_npubs: Optional[set] = None,
                 max_skew: float = MAX_CREATED_AT_SKEW,
                 stale_abort: float = STALE_ABORT,
                 now_fn: Optional[Callable] = None):
        self.bus = bus
        self.allowed_npubs = set(allowed_npubs) if allowed_npubs else None
        self.max_skew = max_skew
        self.stale_abort = stale_abort
        self.now_fn = now_fn or time.time
        self.last_armed: Optional[dict] = None
        self.last_armed_at: Optional[float] = None
        self._handler_task = None

    async def start(self):
        """Subscribe to the bus and begin processing ARMED messages."""
        await self.bus.subscribe(self._on_event)

    async def _on_event(self, event: dict):
        ok, _reason = validate_armed(event, now=self.now_fn(),
                                     allowed_npubs=self.allowed_npubs)
        if not ok:
            return
        self.last_armed = event
        self.last_armed_at = self.now_fn()

    def check_stale(self, now: Optional[float] = None) -> bool:
        """True if the last good ARMED is stale > stale_abort seconds."""
        if self.last_armed_at is None:
            return False
        now = now if now is not None else self.now_fn()
        return (now - self.last_armed_at) > self.stale_abort


# ---------------------------------------------------------------------------
# Verdict publisher — wrap range_check output, config-end granularity
# ---------------------------------------------------------------------------

class VerdictPublisher:
    """Publishes a VERDICT message wrapping range_check.py output.

    Config-end granularity (NOT per-packet): one VERDICT per stop, carrying
    the per-config OK/THIN/MISS list + counts + inline resend-<stop>.json.
    """

    def __init__(self, bus):
        self.bus = bus

    @staticmethod
    def _summary(dist: str, session_id: str, results: list) -> str:
        """One-line summary naming the gaps (mirrors range_check.verdict_line)."""
        clean = sum(1 for r in results if r["status"] == "OK")
        total = len(results)
        gaps = [r for r in results if r["status"] != "OK"]
        if not gaps:
            return "{} s{}: PASS ({}/{})".format(dist, session_id, clean, total)
        parts = []
        for r in gaps:
            if r["status"] == "THIN":
                parts.append("c{}:THIN {}/{}".format(
                    r["idx"], r["counted"], r["n_pkts"]))
            else:
                parts.append("c{}:MISS".format(r["idx"]))
        return "{} s{}: GAPS {} ({}/{})".format(
            dist, session_id, " ".join(parts), clean, total)

    async def publish_verdict(self, dist: str, session_id: str,
                              results: list, resend_json: Optional[dict],
                              created_at: Optional[int] = None) -> dict:
        """Publish a VERDICT message. Returns the message dict."""
        per_config = [{
            "idx": int(r["idx"]),
            "label": r.get("label", "?"),
            "n_pkts": int(r["n_pkts"]),
            "counted": int(r["counted"]),
            "status": r["status"],
        } for r in results]
        msg = {
            "type": "VERDICT",
            "session_id": session_id,
            "stop": dist,
            "summary": self._summary(dist, session_id, results),
            "per_config": per_config,
            "resend_json": resend_json,
            "created_at": int(created_at if created_at is not None
                              else time.time()),
        }
        await self.bus.publish(msg)
        return msg
