#!/usr/bin/env python3
"""
firmware_hash_gate.py — Firmware hash gate for capture safety (HOST-1).

Ensures data capture only proceeds when the firmware version matches what's
expected. This prevents logging data with wrong/mismatched firmware, which
would produce invalid or misleading results.

The gate supports two verification modes:

1. **File-based**: Compute the SHA-256 (or other algorithm) hash of a firmware
   binary file and compare it against an expected hash.

2. **Serial-based**: Send ``FW_QUERY`` to a connected board, parse the
   ``FW_BOOT hash=<hash> tag=<tag> built=<time>`` response, and compare the
   reported git-hash against the expected value.

Usage as a library:

    from firmware_hash_gate import FirmwareHashGate

    # File-based gate
    gate = FirmwareHashGate(expected_hash="abc123def...")
    if gate.check_file("build/firmware.bin"):
        print("Firmware verified — safe to capture")

    # Serial-based gate
    gate = FirmwareHashGate(expected_hash="abc123d")
    if gate.verify_from_serial(ser, timeout=3.0):
        print("Board firmware verified")

Usage as a CLI:

    python3 firmware_hash_gate.py --firmware build/firmware.bin --expected <hash>
    python3 firmware_hash_gate.py --serial /dev/ttyACM0 --expected <7-char-hash>
"""

import argparse
import hashlib
import os
import re
import sys
import time

# Regex for parsing FW_BOOT serial banner lines.
# Format: FW_BOOT hash=<7-char> tag=<4-char> built=<ISO8601>
# Hash field is permissive (\S+) — git short hashes are hex, but the parser
# should not reject otherwise valid FW_BOOT lines with unexpected characters.
FW_BOOT_PATTERN = re.compile(
    r'FW_BOOT\s+hash=(\S+)\s+tag=(\S+)\s+built=(\S+)'
)


class HashMismatchError(Exception):
    """Raised when firmware hash does not match the expected value."""
    pass


def compute_firmware_hash(firmware_path: str, algorithm: str = "sha256") -> str:
    """
    Compute the hash of a firmware binary file.

    Args:
        firmware_path: Path to the firmware binary file.
        algorithm: Hash algorithm name (default: "sha256").
                   Any algorithm supported by hashlib is accepted.

    Returns:
        Hexadecimal hash digest string.

    Raises:
        FileNotFoundError: If the firmware file does not exist.
    """
    h = hashlib.new(algorithm)
    with open(firmware_path, "rb") as f:
        while True:
            chunk = f.read(65536)  # 64 KB chunks
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def parse_fw_boot_line(line: str) -> dict | None:
    """
    Parse a FW_BOOT serial banner line.

    Expected format:
        FW_BOOT hash=abc123d tag=RX0 built=2026-07-24T14:30Z

    Args:
        line: Raw serial line (may include trailing \\r\\n).

    Returns:
        Dict with keys 'hash', 'tag', 'built' if the line matches,
        or None if the line is not a valid FW_BOOT banner.
    """
    line = line.strip()
    m = FW_BOOT_PATTERN.search(line)
    if not m:
        return None
    return {
        "hash": m.group(1),
        "tag": m.group(2),
        "built": m.group(3),
    }


def read_fw_hash_from_serial(ser, timeout: float = 5.0) -> str | None:
    """
    Query a connected board for its firmware hash via serial.

    Sends ``FW_QUERY\\n`` to the board and waits for a ``FW_BOOT`` response
    line. The board's firmware responds to FW_QUERY by printing its boot
    banner containing the git short hash.

    Args:
        ser: An open serial object (pyserial-compatible, must have
             write() and read() methods).
        timeout: Maximum seconds to wait for a response.

    Returns:
        The firmware hash string (e.g. "abc123d"), or None if no valid
        FW_BOOT line is received within the timeout.
    """
    # Send the query
    try:
        ser.write(b"FW_QUERY\n")
        if hasattr(ser, 'flush'):
            ser.flush()
    except Exception:
        return None

    deadline = time.time() + timeout
    buf = ""

    while time.time() < deadline:
        try:
            data = ser.read(256)
        except Exception:
            return None

        if data:
            buf += data.decode("ascii", errors="replace")

            # Process complete lines
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                parsed = parse_fw_boot_line(line)
                if parsed is not None:
                    return parsed["hash"]

    return None


class FirmwareHashGate:
    """
    Gate that verifies firmware hash before allowing data capture.

    When expected_hash is None, the gate is disabled (always passes).
    This allows running without a hash check when the expected hash is
    unknown or not yet established.

    Args:
        expected_hash: The expected firmware hash. For file-based checks,
                       this should be a full hex digest (e.g. 64 chars for
                       SHA-256). For serial-based checks, this is the 7-char
                       git short hash. None disables the gate.
        algorithm: Hash algorithm for file-based checks (default: "sha256").
    """

    def __init__(self, expected_hash: str | None = None,
                 algorithm: str = "sha256"):
        self.expected_hash = expected_hash
        self.algorithm = algorithm

    def check_file(self, firmware_path: str) -> bool:
        """
        Check that a firmware binary file matches the expected hash.

        Args:
            firmware_path: Path to the firmware binary file.

        Returns:
            True if the hash matches (or gate is disabled).

        Raises:
            FileNotFoundError: If the firmware file does not exist.
            HashMismatchError: If the hash does not match.
        """
        if self.expected_hash is None:
            return True

        actual = compute_firmware_hash(firmware_path, self.algorithm)
        if actual != self.expected_hash:
            raise HashMismatchError(
                f"Firmware hash mismatch: expected {self.expected_hash}, "
                f"got {actual}"
            )
        return True

    def check_serial_hash(self, reported_hash: str) -> bool:
        """
        Check that a serial-reported firmware hash matches the expected hash.

        Args:
            reported_hash: The hash string reported by the board (e.g.
                           "abc123d" from FW_BOOT).

        Returns:
            True if the hash matches (or gate is disabled).

        Raises:
            HashMismatchError: If the hash does not match.
        """
        if self.expected_hash is None:
            return True

        if reported_hash != self.expected_hash:
            raise HashMismatchError(
                f"Firmware hash mismatch: expected {self.expected_hash}, "
                f"got {reported_hash}"
            )
        return True

    def verify_from_serial(self, ser, timeout: float = 5.0) -> bool:
        """
        Query a board over serial and verify its firmware hash.

        Sends FW_QUERY, reads the FW_BOOT response, and checks the hash.
        If the gate is disabled (expected_hash is None), always returns True.

        Args:
            ser: An open serial object (pyserial-compatible).
            timeout: Maximum seconds to wait for FW_BOOT response.

        Returns:
            True if the hash matches (or gate is disabled).
            False if no FW_BOOT response is received within timeout.

        Raises:
            HashMismatchError: If a FW_BOOT response is received but the
                               hash does not match the expected value.
        """
        if self.expected_hash is None:
            return True

        reported = read_fw_hash_from_serial(ser, timeout=timeout)
        if reported is None:
            return False

        return self.check_serial_hash(reported)


def main():
    """CLI entry point for firmware hash verification."""
    parser = argparse.ArgumentParser(
        description="Firmware hash gate — verify firmware before capture"
    )
    parser.add_argument("--firmware", help="Path to firmware binary file")
    parser.add_argument("--serial", help="Serial port for board query")
    parser.add_argument("--baud", type=int, default=115200,
                        help="Serial baud rate (default: 115200)")
    parser.add_argument("--expected", required=True,
                        help="Expected firmware hash")
    parser.add_argument("--algorithm", default="sha256",
                        help="Hash algorithm for file mode (default: sha256)")
    parser.add_argument("--timeout", type=float, default=5.0,
                        help="Serial query timeout in seconds (default: 5)")
    args = parser.parse_args()

    gate = FirmwareHashGate(expected_hash=args.expected,
                            algorithm=args.algorithm)

    if args.firmware:
        try:
            gate.check_file(args.firmware)
            print(f"[OK] Firmware hash verified: {args.firmware}")
            sys.exit(0)
        except FileNotFoundError:
            print(f"[ERROR] Firmware file not found: {args.firmware}",
                  file=sys.stderr)
            sys.exit(2)
        except HashMismatchError as e:
            print(f"[FAIL] {e}", file=sys.stderr)
            sys.exit(1)

    if args.serial:
        try:
            import serial
        except ImportError:
            print("ERROR: pyserial not installed", file=sys.stderr)
            sys.exit(1)

        try:
            ser = serial.Serial(args.serial, args.baud, timeout=1.0)
        except Exception as e:
            print(f"[ERROR] Cannot open {args.serial}: {e}", file=sys.stderr)
            sys.exit(2)

        try:
            if gate.verify_from_serial(ser, timeout=args.timeout):
                print(f"[OK] Board firmware hash verified: {args.serial}")
                sys.exit(0)
            else:
                print(f"[FAIL] No FW_BOOT response from {args.serial}",
                      file=sys.stderr)
                sys.exit(1)
        except HashMismatchError as e:
            print(f"[FAIL] {e}", file=sys.stderr)
            sys.exit(1)
        finally:
            ser.close()

    parser.error("Provide either --firmware or --serial")


if __name__ == "__main__":
    main()