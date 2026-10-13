#!/usr/bin/env python3
"""Tests for firmware_hash_gate.py — M2 requirement.

Run:  python3 -m unittest test_firmware_hash_gate -v
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import firmware_hash_gate as fhg  # noqa: E402


class ParseFwHashTests(unittest.TestCase):
    def test_boot_banner_fw_hash(self):
        line = "E80 BENCH FW v1.2 (STM32F103C8 + LR2021) fw=FW_HASH=abc123d - 'HELP' for commands"
        self.assertEqual(fhg.parse_fw_hash(line), "abc123d")

    def test_id_response_fw(self):
        line = "ID E80BENCH v1.2 fw=abc123d role=TX armed=0"
        self.assertEqual(fhg.parse_fw_hash(line), "abc123d")

    def test_empty_line(self):
        self.assertIsNone(fhg.parse_fw_hash(""))

    def test_none_line(self):
        self.assertIsNone(fhg.parse_fw_hash(None))

    def test_no_hash_in_line(self):
        self.assertIsNone(fhg.parse_fw_hash("some random console output"))

    def test_case_insensitive(self):
        line = "fw_hash=deadbeef"
        self.assertEqual(fhg.parse_fw_hash(line), "deadbeef")

    def test_fw_pattern_after_fw_hash_pattern(self):
        """FW_HASH= takes priority over fw=."""
        line = "fw=FW_HASH=abc123d fw=deadbeef"
        result = fhg.parse_fw_hash(line)
        self.assertEqual(result, "abc123d")


class ValidateFwHashTests(unittest.TestCase):
    def test_valid_7char_hex(self):
        self.assertTrue(fhg.validate_fw_hash("abc123d"))

    def test_valid_longer_hex(self):
        self.assertTrue(fhg.validate_fw_hash("abcdef1234567"))

    def test_valid_uppercase_hex(self):
        self.assertTrue(fhg.validate_fw_hash("ABC123D"))

    def test_unknown_rejected(self):
        self.assertFalse(fhg.validate_fw_hash("unknown"))

    def test_none_rejected(self):
        self.assertFalse(fhg.validate_fw_hash("none"))

    def test_null_rejected(self):
        self.assertFalse(fhg.validate_fw_hash("null"))

    def test_empty_string_rejected(self):
        self.assertFalse(fhg.validate_fw_hash(""))

    def test_none_value_rejected(self):
        self.assertFalse(fhg.validate_fw_hash(None))

    def test_short_hash_rejected(self):
        self.assertFalse(fhg.validate_fw_hash("abc123"))  # 6 chars < 7

    def test_non_hex_rejected(self):
        self.assertFalse(fhg.validate_fw_hash("xyz1234"))


class FormatSessionStartTests(unittest.TestCase):
    def test_format_contains_required_fields(self):
        line = fhg.format_session_start("abc123d", "def4567", "alice", "e80-bench")
        self.assertTrue(line.startswith("# SESSION_START "))
        self.assertIn("tx_fw=abc123d", line)
        self.assertIn("rx_fw=def4567", line)
        self.assertIn("operator=alice", line)
        self.assertIn("rig=e80-bench", line)

    def test_format_has_iso8601_timestamp(self):
        import re
        line = fhg.format_session_start("abc123d", "def4567", "?", "?")
        # Should contain an ISO 8601 UTC timestamp like 2026-08-20T12:34:56Z
        self.assertRegex(line, r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


class Sha256CheckTests(unittest.TestCase):
    def test_matching_hash(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"hello world")
            path = f.name
        try:
            import hashlib
            expected = hashlib.sha256(b"hello world").hexdigest()
            self.assertTrue(fhg.check(path, expected))
        finally:
            os.unlink(path)

    def test_mismatching_hash(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"hello world")
            path = f.name
        try:
            self.assertFalse(fhg.check(path, "0" * 64))
        finally:
            os.unlink(path)

    def test_nonexistent_file(self):
        self.assertFalse(fhg.check("/nonexistent/path.bin", "0" * 64))

    def test_case_insensitive_hash(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"hello world")
            path = f.name
        try:
            import hashlib
            expected = hashlib.sha256(b"hello world").hexdigest().upper()
            self.assertTrue(fhg.check(path, expected))
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()