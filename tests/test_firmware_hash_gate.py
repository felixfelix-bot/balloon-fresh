"""
Tests for firmware_hash_gate.py — HOST-1 firmware hash gate.

Tests cover:
  - Computing a hash from a firmware binary file
  - Verifying a hash matches an expected value
  - Gate behaviour: pass on match, fail on mismatch
  - Parsing FW_BOOT serial banner lines to extract the firmware hash
  - Reading firmware hash from a serial port (mocked)
  - Edge cases: missing file, empty file, wrong hash format
"""

import hashlib
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure tools/ is importable
TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from firmware_hash_gate import (
    FirmwareHashGate,
    compute_firmware_hash,
    parse_fw_boot_line,
    read_fw_hash_from_serial,
    HashMismatchError,
)


# ─── compute_firmware_hash ──────────────────────────────────────────────


class TestComputeFirmwareHash:
    def test_computes_sha256_of_file(self, tmp_path):
        """compute_firmware_hash returns the SHA-256 hex digest of the file."""
        data = b"firmware-binary-blob-123"
        fw_path = tmp_path / "firmware.bin"
        fw_path.write_bytes(data)

        expected = hashlib.sha256(data).hexdigest()
        result = compute_firmware_hash(str(fw_path))
        assert result == expected

    def test_empty_file(self, tmp_path):
        """Hash of an empty file is the SHA-256 of empty bytes."""
        fw_path = tmp_path / "empty.bin"
        fw_path.write_bytes(b"")
        result = compute_firmware_hash(str(fw_path))
        assert result == hashlib.sha256(b"").hexdigest()

    def test_missing_file_raises(self, tmp_path):
        """Missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            compute_firmware_hash(str(tmp_path / "nonexistent.bin"))

    def test_hash_is_deterministic(self, tmp_path):
        """Same file always produces same hash."""
        data = b"deterministic-content"
        fw_path = tmp_path / "fw.bin"
        fw_path.write_bytes(data)
        h1 = compute_firmware_hash(str(fw_path))
        h2 = compute_firmware_hash(str(fw_path))
        assert h1 == h2

    def test_different_files_different_hashes(self, tmp_path):
        """Different content produces different hashes."""
        p1 = tmp_path / "a.bin"
        p2 = tmp_path / "b.bin"
        p1.write_bytes(b"content-a")
        p2.write_bytes(b"content-b")
        assert compute_firmware_hash(str(p1)) != compute_firmware_hash(str(p2))

    def test_supports_custom_algorithm(self, tmp_path):
        """Can compute hash with a custom algorithm (e.g. md5)."""
        data = b"test-data"
        fw_path = tmp_path / "fw.bin"
        fw_path.write_bytes(data)
        result = compute_firmware_hash(str(fw_path), algorithm="md5")
        assert result == hashlib.md5(data).hexdigest()


# ─── parse_fw_boot_line ─────────────────────────────────────────────────


class TestParseFwBootLine:
    def test_parses_valid_boot_line(self):
        """Parse a standard FW_BOOT line and extract hash, tag, built."""
        line = "FW_BOOT hash=abc123d tag=RX0 built=2026-07-24T14:30Z"
        result = parse_fw_boot_line(line)
        assert result is not None
        assert result["hash"] == "abc123d"
        assert result["tag"] == "RX0"
        assert result["built"] == "2026-07-24T14:30Z"

    def test_parses_tx_tag(self):
        """TX tag is parsed correctly."""
        line = "FW_BOOT hash=def4567 tag=TX0 built=2026-08-01T10:00Z"
        result = parse_fw_boot_line(line)
        assert result["hash"] == "def4567"
        assert result["tag"] == "TX0"

    def test_returns_none_for_non_boot_line(self):
        """Non-FW_BOOT lines return None."""
        assert parse_fw_boot_line("PKT 1 seq=1 rssi=-70") is None
        assert parse_fw_boot_line("RANGE_RESULT_RX,rx=100") is None
        assert parse_fw_boot_line("") is None

    def test_returns_none_for_malformed_boot_line(self):
        """Malformed FW_BOOT lines return None."""
        assert parse_fw_boot_line("FW_BOOT hash=abc123d") is None
        assert parse_fw_boot_line("FW_BOOT missing fields") is None

    def test_handles_carriage_return(self):
        """FW_BOOT lines with trailing \\r\\n are parsed correctly."""
        line = "FW_BOOT hash=abc123d tag=RX0 built=2026-07-24T14:30Z\r\n"
        result = parse_fw_boot_line(line)
        assert result is not None
        assert result["hash"] == "abc123d"

    def test_handles_unknown_tag(self):
        """Unknown build tags are still parsed (tag is informational)."""
        line = "FW_BOOT hash=xyz9999 tag=UNK0 built=2026-01-01T00:00Z"
        result = parse_fw_boot_line(line)
        assert result is not None
        assert result["tag"] == "UNK0"


# ─── read_fw_hash_from_serial ───────────────────────────────────────────


class TestReadFwHashFromSerial:
    def test_reads_hash_from_serial(self):
        """read_fw_hash_from_serial sends FW_QUERY and parses the response."""
        mock_ser = MagicMock()
        # Simulate: first read returns FW_BOOT line, second returns empty
        fw_line = b"FW_BOOT hash=abc123d tag=RX0 built=2026-07-24T14:30Z\r\n"
        mock_ser.read.side_effect = [fw_line, b""]
        mock_ser.in_waiting = 0

        result = read_fw_hash_from_serial(mock_ser, timeout=2.0)
        assert result == "abc123d"
        # Verify FW_QUERY was sent
        mock_ser.write.assert_called()
        sent = mock_ser.write.call_args[0][0]
        assert b"FW_QUERY" in sent

    def test_returns_none_on_timeout(self):
        """Returns None when no FW_BOOT line is received within timeout."""
        mock_ser = MagicMock()
        mock_ser.read.return_value = b""
        mock_ser.in_waiting = 0

        result = read_fw_hash_from_serial(mock_ser, timeout=0.1)
        assert result is None

    def test_returns_none_on_garbage(self):
        """Returns None when serial output is not a FW_BOOT line."""
        mock_ser = MagicMock()
        mock_ser.read.side_effect = [b"random garbage\n", b""]
        mock_ser.in_waiting = 0

        result = read_fw_hash_from_serial(mock_ser, timeout=0.5)
        assert result is None


# ─── FirmwareHashGate ───────────────────────────────────────────────────


class TestFirmwareHashGate:
    def test_gate_passes_on_matching_hash(self, tmp_path):
        """Gate allows capture when firmware hash matches expected."""
        data = b"correct-firmware-binary"
        fw_path = tmp_path / "fw.bin"
        fw_path.write_bytes(data)

        expected_hash = hashlib.sha256(data).hexdigest()
        gate = FirmwareHashGate(expected_hash=expected_hash)
        assert gate.check_file(str(fw_path)) is True

    def test_gate_fails_on_mismatched_hash(self, tmp_path):
        """Gate raises HashMismatchError when hash doesn't match."""
        fw_path = tmp_path / "fw.bin"
        fw_path.write_bytes(b"wrong-firmware")

        gate = FirmwareHashGate(expected_hash="0" * 64)  # 64 hex chars
        with pytest.raises(HashMismatchError):
            gate.check_file(str(fw_path))

    def test_gate_check_serial_hash_pass(self):
        """Gate allows capture when serial-reported hash matches expected."""
        gate = FirmwareHashGate(expected_hash="abc123d")
        assert gate.check_serial_hash("abc123d") is True

    def test_gate_check_serial_hash_fail(self):
        """Gate raises HashMismatchError when serial hash doesn't match."""
        gate = FirmwareHashGate(expected_hash="abc123d")
        with pytest.raises(HashMismatchError):
            gate.check_serial_hash("wrong999")

    def test_gate_with_none_expected_allows_any(self, tmp_path):
        """Gate with expected_hash=None allows any firmware (no gate)."""
        fw_path = tmp_path / "fw.bin"
        fw_path.write_bytes(b"any-firmware")
        gate = FirmwareHashGate(expected_hash=None)
        assert gate.check_file(str(fw_path)) is True

    def test_gate_with_none_expected_allows_serial(self):
        """Gate with expected_hash=None allows any serial hash."""
        gate = FirmwareHashGate(expected_hash=None)
        assert gate.check_serial_hash("anything") is True

    def test_gate_missing_file_raises(self):
        """Gate raises FileNotFoundError for missing firmware file."""
        gate = FirmwareHashGate(expected_hash="0" * 64)
        with pytest.raises(FileNotFoundError):
            gate.check_file("/nonexistent/path/firmware.bin")

    def test_gate_verify_from_serial(self):
        """Gate.verify_from_serial reads hash from serial and checks it."""
        mock_ser = MagicMock()
        fw_line = b"FW_BOOT hash=abc123d tag=RX0 built=2026-07-24T14:30Z\r\n"
        mock_ser.read.side_effect = [fw_line, b""]
        mock_ser.in_waiting = 0

        gate = FirmwareHashGate(expected_hash="abc123d")
        assert gate.verify_from_serial(mock_ser, timeout=1.0) is True

    def test_gate_verify_from_serial_mismatch(self):
        """Gate.verify_from_serial raises on hash mismatch."""
        mock_ser = MagicMock()
        fw_line = b"FW_BOOT hash=wrong999 tag=RX0 built=2026-07-24T14:30Z\r\n"
        mock_ser.read.side_effect = [fw_line, b""]
        mock_ser.in_waiting = 0

        gate = FirmwareHashGate(expected_hash="abc123d")
        with pytest.raises(HashMismatchError):
            gate.verify_from_serial(mock_ser, timeout=1.0)

    def test_gate_verify_from_serial_no_response(self):
        """Gate.verify_from_serial returns False when no FW_BOOT received."""
        mock_ser = MagicMock()
        mock_ser.read.return_value = b""
        mock_ser.in_waiting = 0

        gate = FirmwareHashGate(expected_hash="abc123d")
        assert gate.verify_from_serial(mock_ser, timeout=0.1) is False

    def test_mismatch_error_contains_hashes(self, tmp_path):
        """HashMismatchError message contains both expected and actual hashes."""
        fw_path = tmp_path / "fw.bin"
        fw_path.write_bytes(b"wrong")
        actual = hashlib.sha256(b"wrong").hexdigest()
        expected = "1" * 64

        gate = FirmwareHashGate(expected_hash=expected)
        with pytest.raises(HashMismatchError) as exc_info:
            gate.check_file(str(fw_path))
        error_msg = str(exc_info.value)
        # The error should mention both hashes for debugging
        assert expected in error_msg or "expected" in error_msg.lower()