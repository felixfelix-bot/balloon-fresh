#!/usr/bin/env python3
"""test_cvm_verdict_publisher.py — RED tests for the RX-side VERDICT publisher.

Scope (kanban t_49192514, ADR-range-sync-cvm.md §2.5): the production verdict
publisher that wraps ``range_check.py`` output into the SAME gift-wrapped
NIP-59 kind-1059 channel the ARMED/GO handshake already uses
(``cvm_sync.VerdictPublisher`` shipped the shape in P1; ``cvm_armed_publisher``
shipped the real transport).

Behaviours pinned here:

  - payload shape: status enum per config (OK / THIN / MISS ONLY), packet
    counts, the ``resend-<stop>.json`` content inlined verbatim (deep, not a
    path or a summary)
  - config-end granularity: exactly ONE verdict message per completed
    stop/config scan — provably independent of packet count, never per-packet
  - session linkage: ``session_id`` + ``stop`` correlate the verdict back to
    the ARMED session from phase 1, and a mismatched linkage is refused
  - kind-1059 gift wrap only: no plaintext kind-30315 event is ever
    constructed, and the only send path goes through gift_wrap
  - keys from env vars only (no key-bearing CLI option) and the client key
    must differ from the server key (reused from cvm_armed_publisher)

Pure-Python: no ``nostr_sdk`` import and no real relays. The transport's
wrap/send seam is exercised with a fake nostr module that records exactly
which kinds are constructed and sent.

Run:  python3 -m pytest test_cvm_verdict_publisher.py -v
"""

from __future__ import annotations

import ast
import asyncio
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

MODULE_PATH = Path(_TOOLS_DIR) / "cvm_verdict_publisher.py"

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

SID = "2609130435a3f"
STOP = "50m"
TX_HEX = "f" * 64


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


def _cfg(idx, status, n_pkts, counted, label=None):
    return {"idx": idx, "label": label or "cfg-{}".format(idx),
            "n_pkts": n_pkts, "counted": counted, "status": status}


def _three_results():
    return [_cfg(0, "OK", 10, 10), _cfg(1, "THIN", 10, 3),
            _cfg(2, "MISS", 10, 0)]


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

    ``gift_wrap`` is bound as an INSTANCE attribute: the ADR-033 static guard
    forbids a *method* named ``gift_wrap`` anywhere in tools/, so the fake
    exposes the same call surface without tripping that pin.
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


def _transport():
    from cvm_armed_publisher import NostrTxTransport
    nostr = _FakeNostr()
    client = _FakeClient()
    tx = NostrTxTransport(nostr, signer=object(), client=client,
                          tx_pubkey_hex=TX_HEX, tx_pubkey=object(),
                          author_pubkey_hex="a" * 64, log=lambda *_: None)
    return nostr, client, tx


# ===========================================================================
# payload shape (status enum, counts, inline resend JSON)
# ===========================================================================

class TestVerdictPayloadShape(unittest.TestCase):

    def test_type_and_linkage_fields(self):
        from cvm_verdict_publisher import build_verdict
        msg = build_verdict(SID, STOP, _three_results(), created_at=123)
        self.assertEqual(msg["type"], "VERDICT")
        self.assertEqual(msg["session_id"], SID)
        self.assertEqual(msg["stop"], STOP)
        self.assertEqual(msg["created_at"], 123)
        self.assertEqual(msg["author"], "")

    def test_per_config_carries_status_enum_and_counts(self):
        from cvm_verdict_publisher import VERDICT_STATUSES, build_verdict
        msg = build_verdict(SID, STOP, _three_results())
        per = msg["per_config"]
        self.assertEqual([c["status"] for c in per], ["OK", "THIN", "MISS"])
        self.assertEqual([c["idx"] for c in per], [0, 1, 2])
        self.assertEqual([c["n_pkts"] for c in per], [10, 10, 10])
        self.assertEqual([c["counted"] for c in per], [10, 3, 0])
        self.assertEqual(per[1]["label"], "cfg-1")
        for c in per:
            self.assertIn(c["status"], VERDICT_STATUSES)
            self.assertIsInstance(c["n_pkts"], int)
            self.assertIsInstance(c["counted"], int)

    def test_status_enum_is_exactly_ok_thin_miss(self):
        from cvm_verdict_publisher import VERDICT_STATUSES
        self.assertEqual(tuple(VERDICT_STATUSES), ("OK", "THIN", "MISS"))

    def test_unknown_status_is_refused(self):
        from cvm_verdict_publisher import build_verdict
        with self.assertRaises(ValueError):
            build_verdict(SID, STOP, [_cfg(0, "MAYBE", 10, 1)])

    def test_negative_counts_are_refused(self):
        from cvm_verdict_publisher import build_verdict
        with self.assertRaises(ValueError):
            build_verdict(SID, STOP, [_cfg(0, "OK", -1, 0)])

    def test_resend_json_inlined_verbatim(self):
        from cvm_verdict_publisher import build_verdict
        resend = {"name": "resend-50m-{}".format(SID),
                  "configs": [{"idx": 2, "label": "cfg-2", "sf": 12}]}
        msg = build_verdict(SID, STOP, _three_results(), resend_json=resend)
        # deep copy of the file content — not a path, not a summary
        self.assertEqual(msg["resend_json"], resend)
        self.assertEqual(msg["resend_json"]["configs"][0]["sf"], 12)
        self.assertIsNot(msg["resend_json"], resend)

    def test_resend_json_defaults_to_none(self):
        from cvm_verdict_publisher import build_verdict
        self.assertIsNone(build_verdict(SID, STOP, _three_results())["resend_json"])

    def test_summary_matches_range_check_verdict_line(self):
        import range_check as rc
        from cvm_verdict_publisher import build_verdict
        results = _three_results()
        msg = build_verdict(SID, STOP, results)
        self.assertEqual(msg["summary"],
                         rc.verdict_line(STOP, SID, results, "GAPS"))
        self.assertIn("c1:THIN 3/10", msg["summary"])
        self.assertIn("c2:MISS", msg["summary"])
        self.assertTrue(msg["summary"].endswith("(1/3 clean)"))

    def test_summary_pass_when_all_ok(self):
        import range_check as rc
        from cvm_verdict_publisher import build_verdict
        results = [_cfg(0, "OK", 4, 4), _cfg(1, "OK", 4, 4)]
        msg = build_verdict(SID, STOP, results)
        self.assertEqual(msg["summary"],
                         rc.verdict_line(STOP, SID, results, "PASS"))
        self.assertIn("PASS (2/2 clean)", msg["summary"])

    def test_logging_gap_variant(self):
        import range_check as rc
        from cvm_verdict_publisher import build_verdict
        msg = build_verdict(SID, STOP, [], stat_count=0)
        self.assertTrue(msg["log_gap"])
        self.assertEqual(msg["per_config"], [])
        self.assertEqual(msg["summary"],
                         rc.verdict_line(STOP, SID, [], "LOGGING_GAP"))
        self.assertIn("LOGGING GAP", msg["summary"])

    def test_log_gap_flag_false_when_results_present(self):
        from cvm_verdict_publisher import build_verdict
        self.assertFalse(build_verdict(SID, STOP, _three_results())["log_gap"])

    def test_payload_is_json_round_trippable(self):
        from cvm_verdict_publisher import build_verdict
        msg = build_verdict(SID, STOP, _three_results(),
                            resend_json={"configs": [{"idx": 1}]})
        self.assertEqual(json.loads(json.dumps(msg)), msg)

    def test_required_field_set_is_pinned(self):
        from cvm_verdict_publisher import VERDICT_REQUIRED, build_verdict
        msg = build_verdict(SID, STOP, _three_results())
        for field in VERDICT_REQUIRED:
            self.assertIn(field, msg)

    def test_payload_keys_match_cvm_sync_verdict_shape(self):
        """The P1 (cvm_sync) shape must stay a subset of ours — no drift."""
        import cvm_sync as cvm
        from cvm_verdict_publisher import build_verdict
        results = _three_results()
        bus = _FakeBus()
        asyncio.run(cvm.VerdictPublisher(bus).publish_verdict(
            STOP, SID, results, {"configs": [{"idx": 1}]}, created_at=7))
        p1 = bus.published[0]
        mine = build_verdict(SID, STOP, results,
                             resend_json={"configs": [{"idx": 1}]},
                             created_at=7)
        self.assertLessEqual(set(p1), set(mine))
        for key in p1:
            if key == "summary":
                # Deliberate: ours mirrors range_check.verdict_line (ADR §2.5),
                # cvm_sync's P1 helper formats "(clean/total)" instead.
                continue
            self.assertEqual(mine[key], p1[key],
                             "field {!r} drifted from cvm_sync".format(key))


# ===========================================================================
# config-end aggregation (N packets -> exactly 1 verdict)
# ===========================================================================

class TestConfigEndAggregation(unittest.TestCase):

    def _publish(self, results, n_calls=1):
        from cvm_verdict_publisher import RxVerdictPublisher
        bus = _FakeBus()
        pub = RxVerdictPublisher(bus, SID, STOP)
        for _ in range(n_calls):
            asyncio.run(pub.publish_config_end(results))
        return bus, pub

    def test_one_message_regardless_of_packet_count(self):
        from cvm_verdict_publisher import RxVerdictPublisher
        for n in (0, 1, 7, 250, 1000):
            bus = _FakeBus()
            pub = RxVerdictPublisher(bus, SID, STOP)
            asyncio.run(pub.publish_config_end([_cfg(0, "MISS", n, 0)]))
            self.assertEqual(len(bus.published), 1,
                             "packet count {} changed the message count".format(n))
            self.assertEqual(pub.published_count, 1)

    def test_message_count_tracks_config_end_calls_not_packets(self):
        from cvm_verdict_publisher import RxVerdictPublisher
        bus = _FakeBus()
        pub = RxVerdictPublisher(bus, SID, STOP)
        results = [_cfg(i, "OK", 50, 50) for i in range(4)]
        for _ in range(3):                       # three completed scans
            asyncio.run(pub.publish_config_end(results))
        self.assertEqual(len(bus.published), 3)
        self.assertEqual(pub.published_count, 3)

    def test_multi_config_scan_is_one_message(self):
        from cvm_verdict_publisher import RxVerdictPublisher
        bus = _FakeBus()
        pub = RxVerdictPublisher(bus, SID, STOP)
        results = [_cfg(i, "OK" if i % 2 else "THIN", 25, 20)
                   for i in range(8)]
        asyncio.run(pub.publish_config_end(results))
        self.assertEqual(len(bus.published), 1)
        self.assertEqual(len(bus.published[0]["per_config"]), 8)

    def test_every_message_is_complete_not_partial(self):
        from cvm_verdict_publisher import RxVerdictPublisher
        bus = _FakeBus()
        pub = RxVerdictPublisher(bus, SID, STOP)
        asyncio.run(pub.publish_config_end(_three_results()))
        msg = bus.published[0]
        self.assertEqual(len(msg["per_config"]), 3)
        self.assertTrue(msg["summary"])

    def test_no_per_packet_api_surface(self):
        tree = ast.parse(_module_src())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.assertNotIn(
                    "packet", node.name.lower(),
                    "per-packet publish surface is forbidden "
                    "(config-end granularity): {}".format(node.name))


# ===========================================================================
# session linkage to the phase-1 ARMED session
# ===========================================================================

class TestSessionLinkage(unittest.TestCase):

    def test_link_fields_are_session_id_and_stop(self):
        from cvm_verdict_publisher import LINK_FIELDS
        self.assertEqual(tuple(LINK_FIELDS), ("session_id", "stop"))

    def test_valid_link_to_armed_message(self):
        from cvm_verdict_publisher import build_verdict, validate_session_link
        armed = {"type": "ARMED", "session_id": SID, "stop": STOP,
                 "t_ready_utc": 1, "preset_hash": "abc", "seq": 1}
        ok, reason = validate_session_link(
            build_verdict(SID, STOP, _three_results()), armed)
        self.assertTrue(ok, reason)

    def test_mismatched_session_is_refused(self):
        from cvm_verdict_publisher import build_verdict, validate_session_link
        armed = {"type": "ARMED", "session_id": "2609130435fff", "stop": STOP}
        ok, reason = validate_session_link(
            build_verdict(SID, STOP, _three_results()), armed)
        self.assertFalse(ok)
        self.assertIn("session_id", reason)

    def test_mismatched_stop_is_refused(self):
        from cvm_verdict_publisher import build_verdict, validate_session_link
        armed = {"type": "ARMED", "session_id": SID, "stop": "872m"}
        ok, reason = validate_session_link(
            build_verdict(SID, STOP, _three_results()), armed)
        self.assertFalse(ok)
        self.assertIn("stop", reason)

    def test_missing_link_fields_are_refused(self):
        from cvm_verdict_publisher import build_verdict, validate_session_link
        ok, reason = validate_session_link(build_verdict(SID, STOP, []),
                                           {"type": "VERDICT"})
        self.assertFalse(ok)
        self.assertTrue(reason)

    def test_publisher_refuses_bad_session_id(self):
        from cvm_verdict_publisher import RxVerdictPublisher
        with self.assertRaises(ValueError):
            RxVerdictPublisher(_FakeBus(), "nope", STOP)

    def test_publisher_refuses_placeholder_stop(self):
        from cvm_verdict_publisher import RxVerdictPublisher
        for bad in ("", "?", None):
            with self.assertRaises(ValueError):
                RxVerdictPublisher(_FakeBus(), SID, bad)

    def test_validate_verdict_flags_broken_link_fields(self):
        from cvm_verdict_publisher import build_verdict, validate_verdict
        msg = build_verdict(SID, STOP, _three_results())
        self.assertEqual(validate_verdict(msg), (True, ""))
        del msg["session_id"]
        ok, reason = validate_verdict(msg)
        self.assertFalse(ok)
        self.assertIn("session_id", reason)

    def test_validate_verdict_rejects_unknown_status(self):
        from cvm_verdict_publisher import build_verdict, validate_verdict
        msg = build_verdict(SID, STOP, _three_results())
        msg["per_config"][0]["status"] = "MAYBE"
        ok, reason = validate_verdict(msg)
        self.assertFalse(ok)
        self.assertIn("status", reason)


# ===========================================================================
# kind-1059 wrapping, no plaintext leak
# ===========================================================================

class TestGiftWrapNoPlaintextLeak(unittest.TestCase):

    def test_publish_routes_through_gift_wrap_kind_1059(self):
        from cvm_verdict_publisher import RxVerdictPublisher
        nostr, client, tx = _transport()
        pub = RxVerdictPublisher(tx, SID, STOP)
        asyncio.run(pub.publish_config_end(_three_results(),
                                           resend_json={"configs": [{"idx": 2}]}))
        self.assertEqual(nostr.constructed_kinds, [KIND_CVM_RPC])
        self.assertEqual(nostr.wrapped_kinds, [KIND_GIFT_WRAP])
        self.assertEqual(len(client.sent), 1)
        self.assertEqual(client.sent[0].outer_kind, KIND_GIFT_WRAP)
        inner = client.sent[0].inner.payload
        self.assertEqual(inner["kind"], KIND_CVM_RPC)
        self.assertNotEqual(inner["kind"], KIND_PLAINTEXT_30315)
        self.assertEqual(inner["tags"], [["p", TX_HEX]])
        content = json.loads(inner["content"])
        self.assertEqual(content["type"], "VERDICT")
        self.assertEqual(content["session_id"], SID)
        self.assertEqual(content["stop"], STOP)
        self.assertEqual(len(content["per_config"]), 3)

    def test_no_30315_literal_or_local_gift_wrap_kind(self):
        src = _module_src()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Constant) and node.value == KIND_PLAINTEXT_30315:
                self.fail("module authors plaintext kind 30315 at line "
                          "{}".format(node.lineno))
            if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "KIND_GIFT_WRAP"
                    for t in node.targets):
                self.fail("KIND_GIFT_WRAP must be imported, not redefined")
        self.assertIn("from cvm_sync import", src)

    def test_plaintext_tally_type_is_refused_by_the_send_path(self):
        from cvm_armed_publisher import PlaintextKindError
        _, _, tx = _transport()
        with self.assertRaises(PlaintextKindError):
            asyncio.run(tx.publish({"type": "TALLY", "session_id": SID}))

    def test_publisher_uses_the_shared_gift_wrap_transport(self):
        """The only send path must be cvm_armed_publisher.NostrTxTransport."""
        import cvm_verdict_publisher as cvp
        from cvm_armed_publisher import NostrTxTransport
        self.assertIs(cvp.NostrTxTransport, NostrTxTransport)
        src = _module_src()
        self.assertNotIn("send_event(", src.split("def ")[0],
                         "module must not hand-roll a send path")


# ===========================================================================
# env-only keys + client/server key separation
# ===========================================================================

class TestEnvOnlyKeys(unittest.TestCase):

    def test_parser_exposes_no_key_bearing_option(self):
        from cvm_verdict_publisher import build_parser
        opts = [o for action in build_parser()._actions for o in action.option_strings]
        for opt in opts:
            for needle in ("nsec", "hex", "key", "secret", "priv"):
                self.assertNotIn(needle, opt.lower(),
                                 "key-bearing CLI option: {}".format(opt))

    def test_module_source_has_no_key_bearing_option(self):
        for opt in _argparse_option_strings(_module_src()):
            for needle in ("nsec", "hex", "key", "secret", "priv"):
                self.assertNotIn(needle, opt.lower())

    def test_key_helpers_are_reused_from_armed_publisher(self):
        import cvm_armed_publisher as cap
        import cvm_verdict_publisher as cvp
        self.assertIs(cvp.load_env_secrets, cap.load_env_secrets)
        self.assertIs(cvp.assert_keys_differ, cap.assert_keys_differ)
        self.assertIs(cvp.EnvKeyError, cap.EnvKeyError)
        self.assertIs(cvp.KeyCollisionError, cap.KeyCollisionError)

    def test_env_only_loading_and_missing_key_raises(self):
        from cvm_verdict_publisher import EnvKeyError, load_env_secrets
        with self.assertRaises(EnvKeyError):
            load_env_secrets({})
        secrets = load_env_secrets({"CVM_RX_NSEC": "nsec1x",
                                    "CVM_SERVER_NSEC": "nsec1y"})
        self.assertEqual(secrets["client"], "nsec1x")
        self.assertEqual(secrets["server"], "nsec1y")

    def test_identical_client_and_server_keys_refused(self):
        from cvm_verdict_publisher import KeyCollisionError, assert_keys_differ
        with self.assertRaises(KeyCollisionError):
            assert_keys_differ("ab" * 32, "ab" * 32)
        assert_keys_differ("ab" * 32, "cd" * 32)   # distinct: no raise

    def test_help_lists_no_key_option_and_needs_session_linkage(self):
        proc = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--help"],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = proc.stdout
        self.assertIn("--session-id", out)
        self.assertIn("--stop", out)
        self.assertIn("--results", out)
        # no key-bearing OPTION (the env var NAMES may appear as documentation)
        for needle in ("--key", "--secret", "--priv", "nsec1"):
            self.assertNotIn(needle, out)
        self.assertIn("CVM_RX_NSEC", out)   # documents WHERE keys come from

    def test_required_cli_args_fail_fast(self):
        from cvm_verdict_publisher import build_parser
        with self.assertRaises(SystemExit):
            build_parser().parse_args([])


# ===========================================================================
# relay failover set
# ===========================================================================

class TestRelayFailoverSet(unittest.TestCase):

    def test_exact_relay_set_matches_the_contract(self):
        from cvm_verdict_publisher import failover_relays
        self.assertEqual(failover_relays(), REQUIRED_RELAYS)

    def test_dead_relay_is_never_included(self):
        from cvm_verdict_publisher import failover_relays
        self.assertNotIn(DEAD_RELAY, failover_relays([DEAD_RELAY]))
        self.assertNotIn(DEAD_RELAY, failover_relays())

    def test_relay_helper_is_reused_from_armed_publisher(self):
        import cvm_armed_publisher as cap
        import cvm_verdict_publisher as cvp
        self.assertIs(cvp.failover_relays, cap.failover_relays)


# ===========================================================================
# CLI results ingestion (JSON -> per_config)
# ===========================================================================

class TestResultsIngestion(unittest.TestCase):

    def test_list_form(self):
        import tempfile
        from cvm_verdict_publisher import load_results
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(_three_results(), fh)
            path = fh.name
        try:
            results, meta = load_results(path)
            self.assertEqual(len(results), 3)
            self.assertEqual(meta, {})
        finally:
            os.unlink(path)

    def test_dict_form_with_inline_resend_and_stat_count(self):
        import tempfile
        from cvm_verdict_publisher import load_results
        payload = {"results": _three_results(), "stat_count": 6,
                   "resend_json": {"configs": [{"idx": 2}]}}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(payload, fh)
            path = fh.name
        try:
            results, meta = load_results(path)
            self.assertEqual(len(results), 3)
            self.assertEqual(meta["stat_count"], 6)
            self.assertEqual(meta["resend_json"], {"configs": [{"idx": 2}]})
        finally:
            os.unlink(path)

    def test_end_to_end_payload_from_file(self):
        import tempfile
        from cvm_verdict_publisher import build_verdict, load_results
        resend = {"name": "resend-50m-{}".format(SID),
                  "configs": [{"idx": 1, "label": "cfg-1"}]}
        payload = {"per_config": _three_results(), "resend_json": resend}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(payload, fh)
            path = fh.name
        try:
            results, meta = load_results(path)
            msg = build_verdict(SID, STOP, results,
                                resend_json=meta.get("resend_json"))
            self.assertEqual(msg["resend_json"], resend)
            self.assertEqual([c["status"] for c in msg["per_config"]],
                             ["OK", "THIN", "MISS"])
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
