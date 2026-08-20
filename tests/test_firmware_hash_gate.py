"""Tests for M2 firmware-hash gate — parse, validate, and format session start."""

import hashlib
import os
import subprocess
import sys
import tempfile

import pytest
from tools.firmware_hash_gate import parse_fw_hash, validate_fw_hash, format_session_start


class TestParseFwHash:
    def test_parse_from_boot_banner_e80(self):
        line = "E80 BENCH FW v1.2 (STM32F103C8 + LR2021) FW_HASH=abc1234 - 'HELP' for commands"
        assert parse_fw_hash(line) == "abc1234"

    def test_parse_from_boot_banner_c3(self):
        line = "FW_HASH=deadbee"
        assert parse_fw_hash(line) == "deadbee"

    def test_parse_from_id_response(self):
        line = "ID E80BENCH v1.2 fw=abc1234 role=TX"
        assert parse_fw_hash(line) == "abc1234"

    def test_parse_no_hash_returns_none(self):
        line = "=== LR2021 Range Test v1.0 ==="
        assert parse_fw_hash(line) is None

    def test_parse_unknown_hash(self):
        line = "FW_HASH=unknown"
        assert parse_fw_hash(line) == "unknown"


class TestValidateFwHash:
    def test_valid_hash_passes(self):
        assert validate_fw_hash("abc1234") is True

    def test_unknown_fails(self):
        assert validate_fw_hash("unknown") is False

    def test_none_fails(self):
        assert validate_fw_hash(None) is False

    def test_empty_fails(self):
        assert validate_fw_hash("") is False

    def test_short_hash_fails(self):
        assert validate_fw_hash("abc") is False  # < 7 chars


class TestFormatSessionStart:
    def test_format_includes_all_fields(self):
        header = format_session_start(
            tx_fw="abc1234", rx_fw="def5678",
            operator="felix", rig="A"
        )
        assert "SESSION_START" in header
        assert "tx_fw=abc1234" in header
        assert "rx_fw=def5678" in header
        assert "operator=felix" in header
        assert "rig=A" in header
        assert header.startswith("#")


class TestCheckFileHash:
    """Tests for check() — SHA256 file hash comparison."""

    def test_check_matching_hash_passes(self, tmp_path):
        """Create a temp file with known content, compute its SHA256, call check() — assert True."""
        fw_file = tmp_path / "firmware.bin"
        content = b"firmware-binary-content-for-testing"
        fw_file.write_bytes(content)
        expected = hashlib.sha256(content).hexdigest()
        from tools.firmware_hash_gate import check
        assert check(str(fw_file), expected) is True

    def test_check_mismatching_hash_fails(self, tmp_path):
        """Create a temp file, call check() with wrong hash — assert False."""
        fw_file = tmp_path / "firmware.bin"
        fw_file.write_bytes(b"actual firmware content")
        wrong_hash = "0" * 64  # clearly wrong
        from tools.firmware_hash_gate import check
        assert check(str(fw_file), wrong_hash) is False

    def test_check_missing_file_fails(self):
        """Call check() with non-existent path — assert it returns False or raises."""
        from tools.firmware_hash_gate import check
        missing_path = "/tmp/nonexistent_firmware_12345678.bin"
        # check() returns False for missing files (graceful handling)
        assert check(missing_path, "0" * 64) is False


class TestCliMain:
    """Tests for main() CLI — argparse-based firmware hash checker."""

    def test_cli_match_exits_zero(self, tmp_path):
        """Run the CLI with --firmware and --expected-hash that match, assert exit code 0."""
        fw_file = tmp_path / "firmware.bin"
        content = b"cli-test-firmware-content"
        fw_file.write_bytes(content)
        expected = hashlib.sha256(content).hexdigest()
        result = subprocess.run(
            [sys.executable, "-m", "tools.firmware_hash_gate",
             "--firmware", str(fw_file), "--expected-hash", expected],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert "OK" in result.stdout

    def test_cli_mismatch_exits_one(self, tmp_path):
        """Run the CLI with mismatching hash, assert exit code 1."""
        fw_file = tmp_path / "firmware.bin"
        fw_file.write_bytes(b"some firmware content")
        result = subprocess.run(
            [sys.executable, "-m", "tools.firmware_hash_gate",
             "--firmware", str(fw_file), "--expected-hash", "0" * 64],
            capture_output=True, text=True
        )
        assert result.returncode == 1
        assert "mismatch" in result.stdout.lower()