#!/usr/bin/env python3
"""test_cvm_sync.py — unit tests for the CVM range-sync message layer.

Covers the Phase-1 message layer (ADR-range-sync-cvm.md):
  - session_id generation (RX sole authority: %y%m%d%H%M + 3-hex nonce)
  - ARMED message build / validate (fields, freshness skew, npub allowlist)
  - T0 = t_ready_utc + 30s margin
  - ARMED re-broadcast loop (10-15s, idempotent, stops on GO)
  - TX freshness watchdog (reject skew > 60s, abort if stale > 30s)
  - verdict publisher (range_check output wrapped, config-end granularity)

Runs without real hardware or Nostr relays. The relay pool is mocked via
`MockRelayBus`, which fans out published events to all subscribers
in-memory (mirrors the gift-wrapped kind-1059 broadcast shape minus the
NIP-44/NIP-59 wrap, which is unit-tested separately in test_cvm_board_server).

Run:  python3 -m pytest test_cvm_sync.py -v
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import unittest

# Add tools dir for imports
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)


# ---------------------------------------------------------------------------
# Mock relay bus — simulates the Nostr relay pool in-memory
# ---------------------------------------------------------------------------

class MockRelayBus:
    """In-memory relay pool: publish() fans out to all subscribers.

    Mirrors the gift-wrapped kind-1059 broadcast shape minus the NIP-44/59
    wrap. Subscribers register an async handler; publish() delivers the
    event dict to every registered handler.
    """

    def __init__(self):
        self.subscribers = []  # list of async callables(event_dict)
        self.published = []    # every event dict published (for assertions)

    async def subscribe(self, handler):
        self.subscribers.append(handler)

    async def publish(self, event: dict):
        self.published.append(event)
        for h in list(self.subscribers):
            await h(event)


# ===========================================================================
# SESSION ID + ARMED MESSAGE (pure functions)
# ===========================================================================

class TestSessionId(unittest.TestCase):
    """RX is the sole session authority: %y%m%d%H%M + 3-hex nonce."""

    def test_format_is_10_digits_plus_3_hex(self):
        from cvm_sync import generate_session_id
        sid = generate_session_id(now=1788096000)  # fixed epoch
        self.assertRegex(sid, r"^\d{10}[0-9a-f]{3}$")

    def test_uses_utc_ymdhm_of_now(self):
        from cvm_sync import generate_session_id
        # 1788096000 = 2026-08-30 13:20:00 UTC
        sid = generate_session_id(now=1788096000)
        self.assertTrue(sid.startswith("2608301320"))

    def test_nonce_varies_across_calls(self):
        from cvm_sync import generate_session_id
        sids = {generate_session_id(now=1788096000) for _ in range(50)}
        # 3 hex digits = 4096 space; 50 draws should almost surely differ
        self.assertGreater(len(sids), 1)


class TestArmedBuild(unittest.TestCase):
    """ARMED carries session_id, stop, t_ready_utc, preset_hash, seq."""

    def test_build_armed_has_all_fields(self):
        from cvm_sync import build_armed
        msg = build_armed(
            session_id="2608301440a3f", stop="50m", t_ready_utc=1788096000,
            preset_hash="abc123", seq=1)
        self.assertEqual(msg["type"], "ARMED")
        self.assertEqual(msg["session_id"], "2608301440a3f")
        self.assertEqual(msg["stop"], "50m")
        self.assertEqual(msg["t_ready_utc"], 1788096000)
        self.assertEqual(msg["preset_hash"], "abc123")
        self.assertEqual(msg["seq"], 1)

    def test_build_armed_serializes_to_json(self):
        from cvm_sync import build_armed
        msg = build_armed("2608301440a3f", "50m", 1788096000, "abc", 1)
        # Must be JSON-serializable (it travels as the inner event content)
        json.dumps(msg)


class TestComputeT0(unittest.TestCase):
    """T0 = t_ready_utc + 30s margin (message-derived, not clock boundary)."""

    def test_t0_is_t_ready_plus_30(self):
        from cvm_sync import compute_t0
        self.assertEqual(compute_t0({"t_ready_utc": 1788096000}), 1788096030)

    def test_t0_margin_constant(self):
        from cvm_sync import T0_MARGIN
        self.assertEqual(T0_MARGIN, 30.0)


class TestValidateArmed(unittest.TestCase):
    """Freshness + npub allowlist validation."""

    def test_valid_armed_passes(self):
        from cvm_sync import validate_armed
        msg = {"type": "ARMED", "session_id": "2608301440a3f",
               "stop": "50m", "t_ready_utc": 1788096000,
               "preset_hash": "abc", "seq": 1, "created_at": 1788096000}
        ok, reason = validate_armed(msg, now=1788096000)
        self.assertTrue(ok)
        self.assertEqual(reason, "")

    def test_rejects_created_at_skew_gt_60s(self):
        from cvm_sync import validate_armed
        msg = {"type": "ARMED", "session_id": "2608301440a3f",
               "stop": "50m", "t_ready_utc": 1788096000,
               "preset_hash": "abc", "seq": 1, "created_at": 1788095000}
        # now - created_at = 1000s > 60s skew -> reject
        ok, reason = validate_armed(msg, now=1788096000)
        self.assertFalse(ok)
        self.assertIn("skew", reason.lower())

    def test_rejects_missing_required_field(self):
        from cvm_sync import validate_armed
        msg = {"type": "ARMED", "session_id": "2608301440a3f",
               "stop": "50m", "t_ready_utc": 1788096000,
               "preset_hash": "abc", "seq": 1, "created_at": 1788096000}
        del msg["preset_hash"]
        ok, reason = validate_armed(msg, now=1788096000)
        self.assertFalse(ok)
        self.assertIn("preset_hash", reason)

    def test_rejects_non_allowlisted_npub(self):
        from cvm_sync import validate_armed
        msg = {"type": "ARMED", "session_id": "2608301440a3f",
               "stop": "50m", "t_ready_utc": 1788096000,
               "preset_hash": "abc", "seq": 1, "created_at": 1788096000,
               "author": "deadbeef"}
        ok, reason = validate_armed(msg, now=1788096000,
                                    allowed_npubs={"cafebabe"})
        self.assertFalse(ok)
        self.assertIn("author", reason.lower())


# ===========================================================================
# ARMED PUBLISHER (RX side) — re-broadcast loop
# ===========================================================================

class TestArmedPublisher(unittest.IsolatedAsyncioTestCase):
    """RX publishes ARMED, re-broadcasts every 10-15s until GO, idempotent."""

    async def test_publish_sends_armed_to_bus(self):
        from cvm_sync import ArmedPublisher
        bus = MockRelayBus()
        pub = ArmedPublisher(bus, session_id="2608301440a3f", stop="50m",
                             t_ready_utc=1788096000, preset_hash="abc")
        await pub.publish()
        self.assertEqual(len(bus.published), 1)
        self.assertEqual(bus.published[0]["type"], "ARMED")
        self.assertEqual(bus.published[0]["session_id"], "2608301440a3f")

    async def test_rebroadcast_increments_seq(self):
        from cvm_sync import ArmedPublisher
        bus = MockRelayBus()
        pub = ArmedPublisher(bus, session_id="2608301440a3f", stop="50m",
                             t_ready_utc=1788096000, preset_hash="abc")
        await pub.publish()
        await pub.publish()
        self.assertEqual(bus.published[0]["seq"], 1)
        self.assertEqual(bus.published[1]["seq"], 2)

    async def test_rebroadcast_loop_stops_on_go(self):
        from cvm_sync import ArmedPublisher
        bus = MockRelayBus()
        pub = ArmedPublisher(bus, session_id="2608301440a3f", stop="50m",
                             t_ready_utc=1788096000, preset_hash="abc")

        # GO observed after the 2nd publish -> loop must stop
        async def go_after_two():
            await asyncio.sleep(0.01)
            if len(bus.published) >= 2:
                pub.observe_go()

        task = asyncio.create_task(pub.rebroadcast_loop(
            min_interval=0.01, max_interval=0.02, go_check=go_after_two))
        await asyncio.wait_for(task, timeout=2.0)
        # Loop exited (GO observed) — no more publishes after GO
        self.assertGreaterEqual(len(bus.published), 2)
        self.assertTrue(pub.go_observed)

    async def test_rebroadcast_loop_interval_bounds(self):
        from cvm_sync import ArmedPublisher
        bus = MockRelayBus()
        pub = ArmedPublisher(bus, session_id="2608301440a3f", stop="50m",
                             t_ready_utc=1788096000, preset_hash="abc")
        # Defaults must be 10-15s per ADR
        self.assertEqual(pub.min_interval, 10.0)
        self.assertEqual(pub.max_interval, 15.0)


# ===========================================================================
# ARMED SUBSCRIBER (TX side) — freshness watchdog
# ===========================================================================

class TestArmedSubscriber(unittest.IsolatedAsyncioTestCase):
    """TX subscribes broad + npub allowlist; rejects skew>60s, aborts stale>30s."""

    async def test_receives_valid_armed(self):
        from cvm_sync import ArmedSubscriber
        bus = MockRelayBus()
        sub = ArmedSubscriber(bus, allowed_npubs={"cafebabe"},
                              now_fn=lambda: 1788096000)
        await sub.start()
        msg = {"type": "ARMED", "session_id": "2608301440a3f",
               "stop": "50m", "t_ready_utc": 1788096000,
               "preset_hash": "abc", "seq": 1, "created_at": 1788096000,
               "author": "cafebabe"}
        await bus.publish(msg)
        self.assertIsNotNone(sub.last_armed)
        self.assertEqual(sub.last_armed["session_id"], "2608301440a3f")

    async def test_ignores_skew_gt_60s(self):
        from cvm_sync import ArmedSubscriber
        bus = MockRelayBus()
        sub = ArmedSubscriber(bus, allowed_npubs={"cafebabe"},
                              now_fn=lambda: 1788096000)
        await sub.start()
        msg = {"type": "ARMED", "session_id": "2608301440a3f",
               "stop": "50m", "t_ready_utc": 1788096000,
               "preset_hash": "abc", "seq": 1, "created_at": 1788095000,
               "author": "cafebabe"}
        await bus.publish(msg)
        # created_at skew 1000s > 60s -> rejected, last_armed stays None
        self.assertIsNone(sub.last_armed)

    async def test_ignores_non_allowlisted_npub(self):
        from cvm_sync import ArmedSubscriber
        bus = MockRelayBus()
        sub = ArmedSubscriber(bus, allowed_npubs={"cafebabe"},
                              now_fn=lambda: 1788096000)
        await sub.start()
        msg = {"type": "ARMED", "session_id": "2608301440a3f",
               "stop": "50m", "t_ready_utc": 1788096000,
               "preset_hash": "abc", "seq": 1, "created_at": 1788096000,
               "author": "deadbeef"}
        await bus.publish(msg)
        self.assertIsNone(sub.last_armed)

    async def test_aborts_when_stale_gt_30s(self):
        from cvm_sync import ArmedSubscriber
        bus = MockRelayBus()
        sub = ArmedSubscriber(bus, allowed_npubs={"cafebabe"},
                              now_fn=lambda: 1788096000)
        await sub.start()
        msg = {"type": "ARMED", "session_id": "2608301440a3f",
               "stop": "50m", "t_ready_utc": 1788096000,
               "preset_hash": "abc", "seq": 1, "created_at": 1788096000,
               "author": "cafebabe"}
        await bus.publish(msg)
        self.assertIsNotNone(sub.last_armed)
        # No fresh re-broadcast for > 30s -> watchdog aborts
        aborted = sub.check_stale(now=1788096000 + 31)
        self.assertTrue(aborted)

    async def test_not_stale_within_30s(self):
        from cvm_sync import ArmedSubscriber
        bus = MockRelayBus()
        sub = ArmedSubscriber(bus, allowed_npubs={"cafebabe"},
                              now_fn=lambda: 1788096000)
        await sub.start()
        msg = {"type": "ARMED", "session_id": "2608301440a3f",
               "stop": "50m", "t_ready_utc": 1788096000,
               "preset_hash": "abc", "seq": 1, "created_at": 1788096000,
               "author": "cafebabe"}
        await bus.publish(msg)
        aborted = sub.check_stale(now=1788096000 + 20)
        self.assertFalse(aborted)

    async def test_stale_abort_constant(self):
        from cvm_sync import ArmedSubscriber, STALE_ABORT
        self.assertEqual(STALE_ABORT, 30.0)


# ===========================================================================
# VERDICT PUBLISHER — wrap range_check output, config-end granularity
# ===========================================================================

class TestVerdictPublisher(unittest.IsolatedAsyncioTestCase):
    """Wrap range_check.py output (per-config OK/THIN/MISS + counts + resend)."""

    def _range_check_results(self):
        # Mirrors range_check.analyze_capture output shape
        return [
            {"idx": 0, "label": "SF7-BW125", "n_pkts": 10, "counted": 10,
             "status": "OK"},
            {"idx": 1, "label": "SF12-BW125", "n_pkts": 10, "counted": 0,
             "status": "MISS"},
            {"idx": 2, "label": "FLRC-650", "n_pkts": 10, "counted": 3,
             "status": "THIN"},
        ]

    async def test_publish_verdict_has_config_end_granularity(self):
        from cvm_sync import VerdictPublisher
        bus = MockRelayBus()
        vp = VerdictPublisher(bus)
        await vp.publish_verdict(
            dist="50m", session_id="2608301440a3f",
            results=self._range_check_results(),
            resend_json={"name": "resend-50m-2608301440a3f", "configs": []})
        self.assertEqual(len(bus.published), 1)
        v = bus.published[0]
        self.assertEqual(v["type"], "VERDICT")
        self.assertEqual(v["session_id"], "2608301440a3f")
        self.assertEqual(v["stop"], "50m")
        # per-config list, NOT per-packet
        self.assertEqual(len(v["per_config"]), 3)
        self.assertEqual(v["per_config"][0]["status"], "OK")
        self.assertEqual(v["per_config"][1]["status"], "MISS")
        self.assertEqual(v["per_config"][2]["status"], "THIN")
        self.assertEqual(v["per_config"][2]["counted"], 3)
        self.assertEqual(v["per_config"][2]["n_pkts"], 10)
        # resend json inline
        self.assertEqual(v["resend_json"]["name"],
                         "resend-50m-2608301440a3f")

    async def test_verdict_summary_line(self):
        from cvm_sync import VerdictPublisher
        bus = MockRelayBus()
        vp = VerdictPublisher(bus)
        await vp.publish_verdict(
            dist="50m", session_id="2608301440a3f",
            results=self._range_check_results(), resend_json=None)
        v = bus.published[0]
        # summary names the gaps (MISS + THIN), not the OK config
        self.assertIn("MISS", v["summary"])
        self.assertIn("THIN", v["summary"])
        self.assertNotIn("SF7-BW125", v["summary"])

    async def test_verdict_serializes_to_json(self):
        from cvm_sync import VerdictPublisher
        bus = MockRelayBus()
        vp = VerdictPublisher(bus)
        await vp.publish_verdict(
            dist="50m", session_id="2608301440a3f",
            results=self._range_check_results(), resend_json=None)
        json.dumps(bus.published[0])


if __name__ == "__main__":
    unittest.main()
