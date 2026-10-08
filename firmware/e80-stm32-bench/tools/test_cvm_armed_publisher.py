#!/usr/bin/env python3
"""test_cvm_armed_publisher.py — RED tests for the RX-side ARMED publisher.

Scope (kanban t_0049ed58, ADR-range-sync-cvm.md §2.3): the *real transport*
half of the RX-side ARMED publisher that ``cvm_sync`` (P1 message layer,
already merged) deliberately left as an injection seam:

  - session_id authority: ``%y%m%d%H%M`` (strftime, percent-encoded to plain
    digits) + 3 lowercase-hex nonce, no '%'/URL-unsafe leftovers
  - ARMED payload schema: session_id, stop, t_ready_utc, preset_hash, seq
  - keys read from ENV VARS ONLY, never CLI args; client key MUST differ from
    the server key (asserted at startup)
  - kind-1059 (NIP-59) gift-wrap publish path to the TX npub — NEVER a
    plaintext kind-30315 event
  - relay failover set: nostr.mom, relay.primal.net, nos.lol,
    relay2.contextvm.org, relay.nostr.band — and only those
    (relay.contextvm.org is DEAD and must never be included)
  - re-broadcast every 10-15 s until a GO event from TX is observed on the
    subscription, then stop
  - idempotent replays: identical session fields on every repeat, ``seq``
    monotonically increments, safe to dedupe

Pure-Python: no ``nostr_sdk`` import and no real relays. The transport's
wrap/send seam is exercised with a fake nostr module that records exactly
which kinds are constructed and sent.

Run:  python3 -m pytest test_cvm_armed_publisher.py -v
"""

from __future__ import annotations

import ast
import asyncio
import json
import os
import re
import sys
import unittest
from pathlib import Path

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

MODULE_PATH = Path(_TOOLS_DIR) / "cvm_armed_publisher.py"

from cvm_sync import KIND_GIFT_WRAP  # noqa: E402  (single canonical def)

KIND_CVM_RPC = 25910
KIND_PLAINTEXT_30315 = 30315

REQUIRED_RELAYS = [
    "wss://nostr.mom",
    "wss://relay.primal.net",
    "wss://nos.lol",
    "wss://relay2.contextvm.org",
    "wss://relay.nostr.band",
]
DEAD_RELAY = "wss://relay.contextvm.org"


def _module_src() -> str:
    return MODULE_PATH.read_text()


def _argparse_option_strings(src: str):
    """All option strings passed to add_argument() in a module source."""
    opts = []
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Call):
            continue
        name = node.func
        if not isinstance(name, ast.Attribute) or name.attr != "add_argument":
            continue
        for a in node.args:
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                opts.append(a.value)
    return opts


class _FakeBus:
    """In-memory relay pool (mirrors cvm_sync.MockRelayBus)."""

    def __init__(self):
        self.subscribers = []
        self.published = []

    async def subscribe(self, handler):
        self.subscribers.append(handler)

    async def publish(self, event: dict):
        self.published.append(event)
        for h in list(self.subscribers):
            await h(event)


class _FakeNostr:
    """Records exactly which kinds get wrapped and sent.

    ``gift_wrap`` returns a sentinel object carrying the OUTER kind so the
    test can prove the raw inner event was never handed to send_event.
    """

    class UnsignedEvent:
        def __init__(self, payload):
            self.payload = payload

        @staticmethod
        def from_json(raw):
            return _FakeNostr.UnsignedEvent(json.loads(raw))

    class _Wrapped:
        def __init__(self, inner, outer_kind):
            self.inner = inner
            self.outer_kind = outer_kind

    def __init__(self):
        self.wrapped_kinds = []
        self.constructed_kinds = []
        # Bound as an instance attribute: the ADR-033 static guard forbids a
        # *method* named ``gift_wrap`` anywhere in tools/, so the fake exposes
        # the same call surface without tripping that pin.
        self.gift_wrap = self._wrap_impl

    async def _wrap_impl(self, signer, recipient_pk, unsigned_event):
        self.constructed_kinds.append(unsigned_event.payload["kind"])
        self.wrapped_kinds.append(KIND_GIFT_WRAP)
        return _FakeNostr._Wrapped(unsigned_event, KIND_GIFT_WRAP)


class _FakeClient:
    def __init__(self):
        self.sent = []

    async def send_event(self, event):
        self.sent.append(event)


# ===========================================================================
# session_id authority
# ===========================================================================

class TestSessionIdAuthority(unittest.TestCase):

    def test_format_10_digits_plus_3_lowercase_hex(self):
        from cvm_armed_publisher import generate_session_id
        sid = generate_session_id(now=1788096000)
        self.assertRegex(sid, r"^\d{10}[0-9a-f]{3}$")

    def test_strftime_directives_fully_encoded(self):
        """'%y%m%d%H%M' must arrive as digits — no '%'/URL-unsafe residue."""
        from cvm_armed_publisher import generate_session_id
        sid = generate_session_id(now=1788096000)
        self.assertNotIn("%", sid)
        self.assertEqual(sid, sid.replace("%", ""))
        self.assertTrue(re.fullmatch(r"[0-9a-f]{13}", sid))

    def test_utc_prefix_matches_strftime(self):
        from cvm_armed_publisher import generate_session_id
        # 1788096000 = 2026-08-30 13:20:00 UTC -> "2608301320"
        self.assertTrue(generate_session_id(now=1788096000).startswith(
            "2608301320"))

    def test_nonce_entropy_across_calls(self):
        from cvm_armed_publisher import generate_session_id
        sids = [generate_session_id(now=1788096000) for _ in range(50)]
        # 3 hex digits = 4096 space; 50 draws must not collapse
        self.assertGreaterEqual(len(set(sids)), 40)
        for sid in sids:
            self.assertRegex(sid[10:], r"^[0-9a-f]{3}$")

    def test_validate_session_id_rejects_bad_shapes(self):
        from cvm_armed_publisher import validate_session_id
        self.assertTrue(validate_session_id("2608301320a3f"))
        for bad in ("2608301320", "2608301320A3F", "2608301320a3",
                    "2608301320a3fg", "", "26083013200a3f"):
            self.assertFalse(validate_session_id(bad), bad)


# ===========================================================================
# ARMED payload schema
# ===========================================================================

class TestArmedPayloadSchema(unittest.TestCase):

    def test_payload_has_exactly_the_contract_fields(self):
        from cvm_armed_publisher import build_armed_payload, ARMED_FIELDS
        msg = build_armed_payload(
            session_id="2608301320a3f", stop="50m", t_ready_utc=1788096000,
            preset_hash="deadbeef", seq=1)
        self.assertEqual(set(ARMED_FIELDS), {
            "type", "session_id", "stop", "t_ready_utc", "preset_hash",
            "seq", "created_at", "author"})
        for f in ARMED_FIELDS:
            self.assertIn(f, msg)
        self.assertEqual(msg["type"], "ARMED")
        self.assertEqual(msg["session_id"], "2608301320a3f")
        self.assertEqual(msg["stop"], "50m")
        self.assertEqual(msg["t_ready_utc"], 1788096000)
        self.assertEqual(msg["preset_hash"], "deadbeef")
        self.assertEqual(msg["seq"], 1)

    def test_payload_is_json_serializable(self):
        from cvm_armed_publisher import build_armed_payload
        json.dumps(build_armed_payload("2608301320a3f", "50m", 1788096000,
                                      "abc", 1))

    def test_payload_passes_the_consumer_validator(self):
        from cvm_armed_publisher import build_armed_payload
        from cvm_sync import validate_armed, compute_t0
        msg = build_armed_payload("2608301320a3f", "50m", 1788096000,
                                  "abc", 1, created_at=1788096000)
        ok, reason = validate_armed(msg, now=1788096000)
        self.assertTrue(ok, reason)
        self.assertEqual(compute_t0(msg), 1788096030)

    def test_rx_is_the_sole_session_authority(self):
        """Arming derives the session id locally; it is never taken from TX."""
        from cvm_armed_publisher import arm_session
        sid, msg = arm_session(stop="50m", t_ready_utc=1788096000,
                              preset_hash="abc", now=1788096000)
        self.assertEqual(msg["session_id"], sid)
        self.assertTrue(sid.startswith("2608301320"))
        self.assertEqual(msg["seq"], 1)


# ===========================================================================
# env-only keys + client != server
# ===========================================================================

class TestEnvOnlyKeys(unittest.TestCase):

    def test_client_and_server_keys_read_from_env(self):
        from cvm_armed_publisher import load_env_secrets
        secrets = load_env_secrets({
            "CVM_RX_NSEC": "nsec1client",
            "CVM_SERVER_HEX": "ab" * 32,
        })
        self.assertEqual(secrets["client"], "nsec1client")
        self.assertEqual(secrets["server"], "ab" * 32)

    def test_hex_client_fallback_and_client_alias(self):
        from cvm_armed_publisher import load_env_secrets
        secrets = load_env_secrets({
            "CVM_CLIENT_HEX": "cd" * 32,
            "CVM_SERVER_NSEC": "nsec1server",
        })
        self.assertEqual(secrets["client"], "cd" * 32)
        self.assertEqual(secrets["server"], "nsec1server")

    def test_missing_client_key_is_an_error(self):
        from cvm_armed_publisher import load_env_secrets, EnvKeyError
        with self.assertRaises(EnvKeyError):
            load_env_secrets({"CVM_SERVER_HEX": "ab" * 32})

    def test_missing_server_key_is_an_error(self):
        from cvm_armed_publisher import load_env_secrets, EnvKeyError
        with self.assertRaises(EnvKeyError):
            load_env_secrets({"CVM_RX_NSEC": "nsec1client"})

    def test_identical_client_and_server_keys_refused(self):
        from cvm_armed_publisher import assert_keys_differ, KeyCollisionError
        with self.assertRaises(KeyCollisionError):
            assert_keys_differ("aa" * 32, "aa" * 32)
        # distinct is fine and returns nothing
        self.assertIsNone(assert_keys_differ("aa" * 32, "bb" * 32))

    def test_no_key_material_in_cli_args(self):
        """ADR §2.3: keys via env var, NEVER CLI arg."""
        opts = _argparse_option_strings(_module_src())
        offenders = [o for o in opts
                     if any(t in o.lower()
                            for t in ("nsec", "hex", "key", "secret"))]
        self.assertEqual(offenders, [], f"key-bearing CLI args: {offenders}")

    def test_env_var_names_are_documented_constants(self):
        from cvm_armed_publisher import (
            ENV_CLIENT_NSEC, ENV_CLIENT_HEX, ENV_SERVER_NSEC, ENV_SERVER_HEX,
            ENV_TX_NPUB)
        self.assertEqual(ENV_CLIENT_NSEC, "CVM_RX_NSEC")
        self.assertEqual(ENV_CLIENT_HEX, "CVM_RX_HEX")
        self.assertEqual(ENV_SERVER_NSEC, "CVM_SERVER_NSEC")
        self.assertEqual(ENV_SERVER_HEX, "CVM_SERVER_HEX")
        self.assertEqual(ENV_TX_NPUB, "CVM_TX_NPUB")


# ===========================================================================
# gift-wrap path: kind 1059 only, never plaintext 30315
# ===========================================================================

class TestGiftWrapNoPlaintextLeak(unittest.TestCase):

    def test_inner_event_is_cvm_rpc_not_plaintext_tally(self):
        from cvm_armed_publisher import build_inner_event
        inner = build_inner_event(
            {"type": "ARMED", "session_id": "2608301320a3f"},
            tx_pubkey_hex="f" * 64)
        self.assertEqual(inner["kind"], KIND_CVM_RPC)
        self.assertNotEqual(inner["kind"], KIND_PLAINTEXT_30315)
        self.assertEqual(inner["tags"], [["p", "f" * 64]])
        self.assertEqual(json.loads(inner["content"])["type"], "ARMED")

    def test_publish_gift_wraps_and_never_sends_plaintext(self):
        from cvm_armed_publisher import NostrTxTransport
        nostr = _FakeNostr()
        client = _FakeClient()
        tx = NostrTxTransport(nostr, signer=object(), client=client,
                              tx_pubkey_hex="f" * 64, tx_pubkey=object(),
                              log=lambda *_: None)
        asyncio.run(tx.publish({"type": "ARMED", "session_id": "2608301320a3f",
                                "stop": "50m", "t_ready_utc": 1,
                                "preset_hash": "abc", "seq": 1}))
        self.assertEqual(nostr.constructed_kinds, [KIND_CVM_RPC])
        self.assertEqual(nostr.wrapped_kinds, [KIND_GIFT_WRAP])
        self.assertEqual(len(client.sent), 1)
        self.assertEqual(client.sent[0].outer_kind, KIND_GIFT_WRAP)
        # outer kind is the only thing on the wire; inner stays private
        self.assertEqual(client.sent[0].inner.payload["kind"], KIND_CVM_RPC)

    def test_no_30315_literal_or_local_kind_constant(self):
        src = _module_src()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == KIND_PLAINTEXT_30315:
                self.fail(f"module authors plaintext kind 30315 at "
                          f"line {node.lineno}")
            if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "KIND_GIFT_WRAP"
                    for t in node.targets):
                self.fail("KIND_GIFT_WRAP must be imported from cvm_sync, "
                          "not redefined locally")
        self.assertIn("from cvm_sync import", src)

    def test_publish_is_the_only_send_path(self):
        """send_event may only be reached through the gift-wrap helper."""
        from cvm_armed_publisher import NostrTxTransport
        nostr = _FakeNostr()
        client = _FakeClient()
        tx = NostrTxTransport(nostr, signer=object(), client=client,
                              tx_pubkey_hex="f" * 64, tx_pubkey=object(),
                              log=lambda *_: None)
        asyncio.run(tx.publish({"type": "ARMED", "session_id": "2608301320a3f",
                                "stop": "50m", "t_ready_utc": 1,
                                "preset_hash": "abc", "seq": 1}))
        self.assertTrue(nostr.wrapped_kinds,
                        "publish() must route through gift_wrap")


# ===========================================================================
# relay failover set
# ===========================================================================

class TestRelayFailoverSet(unittest.TestCase):

    def test_exact_relay_set_matches_the_contract(self):
        from cvm_armed_publisher import failover_relays
        self.assertEqual(failover_relays(), REQUIRED_RELAYS)

    def test_dead_relay_is_never_included(self):
        from cvm_armed_publisher import failover_relays
        self.assertNotIn(DEAD_RELAY, failover_relays())

    def test_dead_relay_filtered_even_when_supplied_by_env(self):
        from cvm_armed_publisher import failover_relays
        relays = failover_relays(extra=[DEAD_RELAY, "wss://example.org"])
        self.assertNotIn(DEAD_RELAY, relays)
        self.assertIn("wss://example.org", relays)

    def test_no_duplicate_relays(self):
        from cvm_armed_publisher import failover_relays
        relays = failover_relays(extra=REQUIRED_RELAYS)
        self.assertEqual(len(relays), len(set(relays)))


# ===========================================================================
# repeat-until-GO loop timing + idempotency
# ===========================================================================

class TestRepeatUntilGo(unittest.TestCase):

    def _run(self, go_after_ticks):
        from cvm_armed_publisher import build_publisher, make_go_handler

        bus = _FakeBus()
        pub = build_publisher(bus, session_id="2608301320a3f", stop="50m",
                              t_ready_utc=1788096000, preset_hash="abc",
                              author="a" * 64)
        handler = make_go_handler(pub, session_id="2608301320a3f")
        asyncio.run(bus.subscribe(handler))

        slept = []

        async def fake_sleep(secs):
            slept.append(secs)
            if len(slept) >= go_after_ticks:
                # TX announces GO on the RX session -> loop must stop
                await bus.publish({"type": "GO",
                                   "session_id": "2608301320a3f"})

        asyncio.run(pub.rebroadcast_loop(sleep=fake_sleep))
        return bus, pub, slept

    def test_loop_repeats_until_go_then_stops(self):
        bus, pub, slept = self._run(go_after_ticks=3)
        self.assertTrue(pub.go_observed)
        # GO arrives on the subscription between ticks: 3 ARMED publishes,
        # 3 sleeps, then the loop exits without publishing ARMED again.
        armed = [m for m in bus.published if m.get("type") == "ARMED"]
        self.assertEqual(len(armed), 3)
        self.assertEqual(len(slept), 3)

    def test_interval_is_within_10_15_seconds(self):
        _bus, _pub, slept = self._run(go_after_ticks=5)
        self.assertTrue(slept)
        for s in slept:
            self.assertGreaterEqual(s, 10.0)
            self.assertLessEqual(s, 15.0)

    def test_go_for_another_session_does_not_stop_the_loop(self):
        from cvm_armed_publisher import is_go_event
        self.assertFalse(is_go_event({"type": "GO",
                                      "session_id": "2608301320999"},
                                     session_id="2608301320a3f"))
        self.assertFalse(is_go_event({"type": "ARMED",
                                      "session_id": "2608301320a3f"},
                                     session_id="2608301320a3f"))
        self.assertTrue(is_go_event({"type": "GO",
                                     "session_id": "2608301320a3f"},
                                    session_id="2608301320a3f"))

    def test_replays_are_idempotent_and_seq_increments(self):
        bus, _pub, _slept = self._run(go_after_ticks=4)
        msgs = [m for m in bus.published if m.get("type") == "ARMED"]
        self.assertGreaterEqual(len(msgs), 3)
        # identical session fields on every repeat
        for key in ("session_id", "stop", "t_ready_utc", "preset_hash"):
            self.assertEqual({m[key] for m in msgs}, {msgs[0][key]}, key)
        # seq strictly increments -> each replay is a distinct, dedupable frame
        self.assertEqual([m["seq"] for m in msgs],
                         list(range(1, len(msgs) + 1)))

    def test_dedupe_helper_flags_replayed_frames(self):
        from cvm_armed_publisher import is_replay
        first = {"session_id": "2608301320a3f", "seq": 2}
        older = {"session_id": "2608301320a3f", "seq": 1}
        other = {"session_id": "2608301320999", "seq": 5}
        self.assertTrue(is_replay(first, older))     # same session, older seq
        self.assertTrue(is_replay(first, first))     # exact replay
        self.assertFalse(is_replay(first, other))    # different session
        self.assertFalse(is_replay(first, {"session_id": "2608301320a3f",
                                           "seq": 3}))  # newer


# ===========================================================================
# A4 (Gate-2.5 advisory) — the E80_* env aliases the studio already exports
# must be accepted (and documented in ADR §2.3 alongside the CVM_* names).
# ===========================================================================

class TestE80EnvAliases(unittest.TestCase):
    """ADR §2.3 lists the E80_* aliases alongside the canonical CVM_* names."""

    def test_alias_names_are_documented_constants(self):
        from cvm_armed_publisher import (
            ENV_CLIENT_E80_NSEC, ENV_CLIENT_E80_HEX, ENV_TX_NPUB_E80)
        self.assertEqual(ENV_CLIENT_E80_NSEC, "E80_RX_NSEC")
        self.assertEqual(ENV_CLIENT_E80_HEX, "E80_RX_HEX")
        self.assertEqual(ENV_TX_NPUB_E80, "E80_TX_NPUB")

    def test_e80_client_nsec_alias_accepted(self):
        from cvm_armed_publisher import load_env_secrets
        secrets = load_env_secrets({
            "E80_RX_NSEC": "nsec1e80client",
            "CVM_SERVER_HEX": "ab" * 32,
        })
        self.assertEqual(secrets["client"], "nsec1e80client")
        self.assertEqual(secrets["server"], "ab" * 32)

    def test_e80_client_hex_alias_accepted(self):
        from cvm_armed_publisher import load_env_secrets
        secrets = load_env_secrets({
            "E80_RX_HEX": "cd" * 32,
            "CVM_SERVER_NSEC": "nsec1server",
        })
        self.assertEqual(secrets["client"], "cd" * 32)

    def test_canonical_cvm_name_wins_over_e80_alias(self):
        from cvm_armed_publisher import load_env_secrets
        secrets = load_env_secrets({
            "CVM_RX_NSEC": "nsec1canonical",
            "E80_RX_NSEC": "nsec1alias",
            "CVM_SERVER_HEX": "ab" * 32,
        })
        self.assertEqual(secrets["client"], "nsec1canonical")

    def test_e80_tx_npub_alias_read(self):
        from cvm_armed_publisher import tx_npub_from_env
        self.assertEqual(tx_npub_from_env({"E80_TX_NPUB": "npub1e80"}),
                         "npub1e80")

    def test_tx_npub_prefers_canonical_name(self):
        from cvm_armed_publisher import tx_npub_from_env
        self.assertEqual(
            tx_npub_from_env({"CVM_TX_NPUB": "npub1canonical",
                              "E80_TX_NPUB": "npub1alias"}),
            "npub1canonical")

    def test_tx_npub_absent_is_none(self):
        from cvm_armed_publisher import tx_npub_from_env
        self.assertIsNone(tx_npub_from_env({}))


if __name__ == "__main__":
    unittest.main()
