"""Firmware hash gate — M2 requirement.

Parses FW_HASH from firmware boot banners and ID? responses,
validates the hash, and formats SESSION_START headers.
"""

import re
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