#!/usr/bin/env python3
"""test_rx_armed_publisher.py — RX ARMED publisher core contract.

Acceptance tests for card t_8b927b22: the session-id minting rule, the ARMED
payload schema, and env-only key handling with the ``client != server`` startup
assertion. Everything is exercised THROUGH ``rx_armed_publisher`` (the card's
import surface), which delegates to the canonical ``cvm_sync`` /
``cvm_armed_publisher`` implementation — so this file pins the *bridge
contract*, not a second copy of the implementation.

Full behavioural coverage of the underlying implementation lives in
``test_cvm_sync.py`` and ``test_cvm_armed_publisher.py`` (single suite of
record); these tests exist so the card's named entry point is real and stays
wired to that implementation.

Runs without ``nostr_sdk``, hardware, or network.

Run:  python3 -m pytest tools/test_rx_armed_publisher.py -v
"""

from __future__ import annotations

import os
import re
import sys
import time
import unittest
import urllib.parse
from unittest import mock

# Add tools dir for imports.
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import cvm_armed_publisher as _core  # noqa: E402
import cvm_sync as _cvm_sync  # noqa: E402
import rx_armed_publisher as rxp  # noqa: E402


# ===========================================================================
# Session id — RX is the sole session authority
# ===========================================================================

class TestSessionId(unittest.TestCase):
    """session_id = quote(strftime('%y%m%d%H%M')) + 3 lowercase-hex nonce."""

    def test_format_is_10_digits_plus_3_lowercase_hex(self):
        pat = re.compile(r"^\d{10}[0-9a-f]{3}$")
        for _ in range(200):
            self.assertRegex(rxp.generate_session_id(), pat)

    def test_timestamp_goes_through_urllib_quote_of_strftime(self):
        now = 1788096000  # 2026-08-30 12:00:00 UTC
        expected_ts = urllib.parse.quote(
            time.strftime("%y%m%d%H%M", time.gmtime(now)), safe="")
        sid = rxp.generate_session_id(now=now)
        self.assertTrue(sid.startswith(expected_ts), (sid, expected_ts))
        # digits only: percent-encoding is a no-op and leaves no residue.
        self.assertEqual(expected_ts, "2608301320")
        self.assertNotIn("%", sid)

    def test_nonce_comes_from_the_csprng_not_random(self):
        with mock.patch.object(_cvm_sync.secrets, "randbelow",
                               return_value=0xabc) as rb:
            sid = rxp.generate_session_id()
        self.assertTrue(sid.endswith("abc"), sid)
        rb.assert_called_once_with(0x1000)

    def test_validate_session_id_accepts_good_and_rejects_bad(self):
        self.assertTrue(rxp.validate_session_id(rxp.generate_session_id()))
        for bad in ("", "2608301200", "2608301200xyz", "2608301200ABC",
                    "260830 120abc", "2608301200a3f0"):
            self.assertFalse(rxp.validate_session_id(bad), bad)


# ===========================================================================
# ARMED payload schema
# ===========================================================================

class TestArmedPayloadSchema(unittest.TestCase):
    """The ARMED payload carries exactly the pinned contract fields."""

    def test_required_field_set_is_the_canonical_contract(self):
        # The card's draft listed 5 fields; the reviewed (Gate-2.5 R1) contract
        # additionally REQUIRES created_at.
        self.assertIn("created_at", rxp.ARMED_PAYLOAD_FIELDS)
        for f in ("session_id", "stop", "t_ready_utc", "preset_hash", "seq"):
            self.assertIn(f, rxp.ARMED_PAYLOAD_FIELDS)
        self.assertEqual(tuple(rxp.ARMED_PAYLOAD_FIELDS),
                         tuple(_cvm_sync.ARMED_REQUIRED))

    def test_build_armed_payload_has_exactly_the_envelope_fields(self):
        sid = rxp.generate_session_id()
        msg = rxp.build_armed_payload(sid, "50m", 1788096000, "abc123", 1)
        self.assertEqual(set(msg.keys()), set(rxp.ARMED_FIELDS))
        for f in rxp.ARMED_PAYLOAD_FIELDS:
            self.assertIn(f, msg)
        self.assertEqual(msg["type"], "ARMED")
        self.assertEqual(msg["session_id"], sid)
        self.assertEqual(msg["seq"], 1)

    def test_payload_passes_the_consumer_validator(self):
        sid, msg = rxp.arm_session("50m", 1788096000, "abc123", now=1788096000)
        ok, reason = _cvm_sync.validate_armed(msg, now=int(msg["created_at"]))
        self.assertTrue(ok, reason)

    def test_rx_is_the_sole_session_authority(self):
        sid, msg = rxp.arm_session("50m", 1788096000, "abc123")
        self.assertTrue(rxp.validate_session_id(sid))
        self.assertEqual(msg["session_id"], sid)
        self.assertEqual(msg["seq"], 1)

    def test_bad_session_id_is_rejected(self):
        with self.assertRaises(ValueError):
            rxp.build_armed_payload("not-a-session", "50m", 1, "h", 1)


# ===========================================================================
# Env-only keys + client != server
# ===========================================================================

class TestEnvOnlyKeys(unittest.TestCase):
    """Keys come from env vars ONLY; client must differ from server."""

    _CLIENT = "nsec1" + "a" * 58
    _SERVER = "nsec1" + "b" * 58

    def test_client_and_server_keys_read_from_env(self):
        env = {"CVM_RX_NSEC": self._CLIENT, "CVM_SERVER_NSEC": self._SERVER}
        got = rxp.load_env_secrets(env)
        self.assertEqual(got, {"client": self._CLIENT, "server": self._SERVER})

    def test_missing_key_is_an_error(self):
        with self.assertRaises(rxp.EnvKeyError):
            rxp.load_env_secrets({"CVM_SERVER_NSEC": self._SERVER})
        with self.assertRaises(rxp.EnvKeyError):
            rxp.load_env_secrets({"CVM_RX_NSEC": self._CLIENT})

    def test_same_client_and_server_key_is_refused(self):
        # 64-hex pubkey strings, made identical on purpose.
        same = "ab" * 32
        with self.assertRaises(rxp.KeyCollisionError):
            rxp.assert_keys_differ(same, same)
        # ... and case-insensitively.
        with self.assertRaises(rxp.KeyCollisionError):
            rxp.assert_keys_differ(same.upper(), same)

    def test_distinct_keys_pass_the_assertion(self):
        rxp.assert_keys_differ("ab" * 32, "cd" * 32)  # must not raise

    def test_parser_exposes_no_key_or_secret_option(self):
        parser = rxp.build_parser()
        options = [
            opt
            for action in parser._actions
            for opt in list(action.option_strings)
            if opt.startswith("-")
        ]
        self.assertNotIn("--nsec", options)
        self.assertNotIn("--hex", options)
        offenders = [o for o in options if "nsec" in o.lower() or "secret" in o.lower()]
        self.assertEqual(offenders, [], offenders)


# ===========================================================================
# The bridge stays wired to the single canonical implementation
# ===========================================================================

class TestBridgeIsCanonical(unittest.TestCase):
    def test_symbols_delegate_to_cvm_armed_publisher(self):
        self.assertIs(rxp.generate_session_id, _core.generate_session_id)
        self.assertIs(rxp.build_armed_payload, _core.build_armed_payload)
        self.assertIs(rxp.load_env_secrets, _core.load_env_secrets)
        self.assertIs(rxp.assert_keys_differ, _core.assert_keys_differ)
        self.assertIs(rxp.mint_session_id, _core.generate_session_id)


if __name__ == "__main__":
    unittest.main()
