"""Tests for M2 firmware-hash gate — parse, validate, and format session start."""

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