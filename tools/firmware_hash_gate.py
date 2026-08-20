"""Firmware hash gate — M2 requirement.

Parses FW_HASH from firmware boot banners and ID? responses,
validates the hash, and formats SESSION_START headers.

Also provides SHA256 file-hash verification (check()) and a CLI
entry point (main()) for standalone pre-flash integrity checks.
"""

import argparse
import hashlib
import os
import re
import sys
from datetime import datetime, timezone

# Patterns for extracting firmware hash
# Matches: FW_HASH=<any-value> or fw=<any-value>
# We capture non-whitespace chars after the = sign; validate_fw_hash()
# is responsible for rejecting invalid values like 'unknown'/'none'.
FW_HASH_PATTERN = re.compile(r'FW_HASH=(\S+)', re.IGNORECASE)
FW_ID_PATTERN = re.compile(r'fw=(\S+)', re.IGNORECASE)

# Invalid hash values
INVALID_HASHES = {None, "", "unknown", "none", "null"}


def parse_fw_hash(line: str) -> str | None:
    """Extract firmware hash from a serial output line.

    Tries FW_HASH=<hex> first, then fw=<hex> from ID? response.
    Returns the hash string or None if not found.

    Note: returns whatever value follows the pattern, including
    'unknown'/'none' — use validate_fw_hash() to check validity.
    """
    if not line:
        return None

    # Try FW_HASH= pattern first (boot banner)
    m = FW_HASH_PATTERN.search(line)
    if m:
        return m.group(1)

    # Try fw= pattern (ID? response)
    m = FW_ID_PATTERN.search(line)
    if m:
        return m.group(1)

    return None


def validate_fw_hash(hash_str: str | None) -> bool:
    """Validate that a firmware hash is present and non-trivial.

    Returns True if hash is 7+ hex characters and not a known invalid value.
    """
    if hash_str is None or hash_str == "":
        return False
    if hash_str.lower() in ("unknown", "none", "null"):
        return False
    if len(hash_str) < 7:
        return False
    if not re.match(r'^[0-9a-f]+$', hash_str, re.IGNORECASE):
        return False
    return True


def format_session_start(tx_fw: str, rx_fw: str, operator: str, rig: str) -> str:
    """Format the SESSION_START header line.

    Returns a comment line starting with # for CSV files.
    """
    iso8601 = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"# SESSION_START {iso8601} tx_fw={tx_fw} rx_fw={rx_fw} operator={operator} rig={rig}"


def query_firmware_hash(serial_port, timeout_s: float = 5.0) -> str | None:
    """Query a serial port for firmware hash.

    Sends 'ID?' and waits for response. Also monitors for boot banner.
    Returns the hash if found, None if timeout.

    Args:
        serial_port: An open serial port object with write/readline methods.
        timeout_s: Maximum seconds to wait for a response.

    Returns:
        The firmware hash string, or None if not found within timeout.
    """
    import time

    # Send ID? command
    try:
        serial_port.write(b"ID?\r\n")
    except Exception:
        pass

    # Read lines for up to timeout
    start = time.monotonic()
    while time.monotonic() - start < timeout_s:
        try:
            line = serial_port.readline().decode('utf-8', errors='replace').strip()
            if line:
                hash_str = parse_fw_hash(line)
                if hash_str:
                    return hash_str
        except Exception:
            break

    return None


# ── SHA256 file-hash verification ──────────────────────────────────

def check(firmware_path: str, expected_hash: str) -> bool:
    """Verify a firmware binary file's SHA256 hash against an expected value.

    Args:
        firmware_path: Path to the firmware binary file.
        expected_hash: Expected SHA256 hex digest (64 hex chars).

    Returns:
        True if the file's SHA256 matches expected_hash, False otherwise.
        Returns False if the file does not exist.
    """
    if not os.path.isfile(firmware_path):
        return False

    sha256 = hashlib.sha256()
    with open(firmware_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)

    actual_hash = sha256.hexdigest()
    return actual_hash.lower() == expected_hash.lower()


# ── CLI entry point ────────────────────────────────────────────────

def main(argv=None):
    """CLI: verify a firmware file's SHA256 hash before flashing.

    Usage:
        python3 tools/firmware_hash_gate.py <firmware.bin> <expected_hash>

    Exit codes:
        0 — hash matches
        1 — hash mismatch, file not found, or invalid arguments
    """
    parser = argparse.ArgumentParser(
        description="Verify firmware binary SHA256 hash before flashing."
    )
    parser.add_argument(
        "firmware",
        help="Path to firmware binary file",
    )
    parser.add_argument(
        "expected_hash",
        help="Expected SHA256 hex digest (64 hex chars)",
    )
    args = parser.parse_args(argv)

    if not os.path.isfile(args.firmware):
        print(f"ERROR: file not found: {args.firmware}")
        sys.exit(1)

    if check(args.firmware, args.expected_hash):
        print("OK: firmware hash matches")
        sys.exit(0)
    else:
        print("ERROR: hash mismatch")
        sys.exit(1)


if __name__ == "__main__":
    main()