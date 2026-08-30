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

    VERDICT:
      { "type": "VERDICT", "session_id": "...", "stop": "50m",
        "summary": "50m s2608301440a3f: GAPS c1:MISS c2:THIN 3/10 (1/3 clean)",
        "per_config": [ {"idx":0,"label":"...","n_pkts":10,"counted":10,
                         "status":"OK"}, ... ],
        "resend_json": { ... } | null }

RX is the SOLE session authority: session_id = %y%m%d%H%M + 3-hex nonce.
T0 = t_ready_utc + 30s margin. ARMED re-broadcast every 10-15s until GO.
TX freshness watchdog: reject created_at skew > 60s, abort if stale > 30s.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import time
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

# Required ARMED fields (validate_armed).
ARMED_REQUIRED = ("session_id", "stop", "t_ready_utc", "preset_hash", "seq")


# ---------------------------------------------------------------------------
# Session id + ARMED message (pure functions)
# ---------------------------------------------------------------------------

def generate_session_id(now: Optional[int] = None) -> str:
    """RX sole authority: %y%m%d%H%M + 3-hex nonce.

    e.g. 2608301440a3f. The 3-hex nonce (4096 space) disambiguates two arms
    in the same minute.
    """
    now = int(now if now is not None else time.time())
    ts = time.strftime("%y%m%d%H%M", time.gmtime(now))
    nonce = "{:03x}".format(random.randrange(0x1000))
    return ts + nonce


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


def compute_t0(armed: dict) -> int:
    """T0 = t_ready_utc + T0_MARGIN (message-derived, not clock boundary)."""
    return int(armed["t_ready_utc"]) + int(T0_MARGIN)


def validate_armed(msg: dict, now: Optional[int] = None,
                   allowed_npubs: Optional[set] = None) -> tuple:
    """Validate an ARMED message. Returns (ok, reason).

    Rejects: missing required fields, created_at skew > 60s, non-allowlisted
    author npub (when an allowlist is given).
    """
    now = int(now if now is not None else time.time())
    if not isinstance(msg, dict) or msg.get("type") != "ARMED":
        return False, "not an ARMED message"
    for f in ARMED_REQUIRED:
        if f not in msg:
            return False, "missing required field: {}".format(f)
    created = msg.get("created_at")
    if created is not None:
        skew = abs(now - int(created))
        if skew > MAX_CREATED_AT_SKEW:
            return False, "created_at skew {}s > {}s".format(
                skew, MAX_CREATED_AT_SKEW)
    if allowed_npubs is not None:
        author = msg.get("author", "")
        if author not in allowed_npubs:
            return False, "author not in allowlist: {}".format(author[:16])
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
