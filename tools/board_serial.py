#!/usr/bin/env python3
"""
board-serial.py — Mandatory serial wrapper with flock enforcement.

ALL board test scripts MUST use BoardSerial() instead of serial.Serial().
This wrapper checks that the calling track holds the flock before opening
any /dev/ttyACM* port. If the lock is not held, it refuses to open and
prints a clear error with instructions.

Usage:
    from board_serial import BoardSerial

    # Instead of: ser = serial.Serial('/dev/ttyACM0', 115200)
    # Use:
    ser = BoardSerial('/dev/ttyACM0', 115200)
    ser.write(b'data')
    data = ser.read(1024)

The wrapper proxies ALL pyserial methods, so it's a drop-in replacement.
"""

import os
import sys
import fcntl
import json
from pathlib import Path

try:
    import serial as pyserial
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial", file=sys.stderr)
    sys.exit(1)

LOCK_DIR = Path.home() / ".hermes" / "peripheral_locks"

# Map serial ports to lock resources
PORT_TO_RESOURCE = {
    "/dev/ttyACM0": "tx",   # F242D TX board (was ACM3 in older config, check udev)
    "/dev/ttyACM2": "rx",   # 8332 RX board (was ACM4 in older config)
    # ESP32-S3 boards
    # board-a, board-b, board-c mappings TBD
}

# Reverse map built dynamically from lock file metadata too
def _resolve_port_to_resource(port: str) -> str | None:
    """Map a serial port path to a lock resource name.
    
    Priority: udev serial number > hardcoded map.
    Ports swap on reboot (known RP2040 USB issue), so udev is authoritative.
    """
    # Try udev serial number FIRST (ports swap on reboot)
    import subprocess
    try:
        result = subprocess.run(
            ["udevadm", "info", "-q", "property", "-n", port],
            capture_output=True, text=True, timeout=5
        )
        serial_short = ""
        for line in result.stdout.split("\n"):
            if line.startswith("ID_SERIAL_SHORT="):
                serial_short = line.split("=", 1)[1]
                break
        if "F242D" in serial_short:
            return "tx"
        if "8332" in serial_short:
            return "rx"
    except Exception:
        pass
    # Fall back to hardcoded map (may be stale after port swap)
    if port in PORT_TO_RESOURCE:
        return PORT_TO_RESOURCE[port]
    return None


def _is_locked_by_us(resource: str) -> bool:
    """Check if the flock for this resource is held by our track."""
    lock_path = LOCK_DIR / f"balloon-{resource}.lock"
    if not lock_path.exists():
        return False

    # Test if flock is held (non-blocking attempt)
    fd = None
    try:
        fd = os.open(str(lock_path), os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # We got the lock → nobody was holding it
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False
        except BlockingIOError:
            # Someone holds it. Check if it's our track.
            try:
                data = json.loads(lock_path.read_text())
                our_track = os.getenv("BALLOON_TRACK", "unknown")
                holder_track = data.get("track", "?")
                return holder_track == our_track
            except (json.JSONDecodeError, OSError):
                return False
    except OSError:
        return False
    finally:
        if fd is not None:
            os.close(fd)


def check_board_lock(port: str) -> bool:
    """Verify the calling track holds the lock for the given port.

    Returns True if safe to proceed.
    Exits with error if lock not held.
    """
    # Only enforce on /dev/ttyACM* (board ports)
    if "/dev/ttyACM" not in port and "/dev/ttyUSB" not in port:
        return True  # Not a board port, allow

    resource = _resolve_port_to_resource(port)
    if resource is None:
        # Unknown board — still try to protect, but warn
        print(f"WARNING: Cannot map {port} to a board resource. "
              f"Lock not enforced for unknown ports.", file=sys.stderr)
        return True

    if _is_locked_by_us(resource):
        return True

    # Lock not held by us — REFUSE
    track = os.getenv("BALLOON_TRACK", "unknown")
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"REFUSED: Cannot open {port} ({resource})", file=sys.stderr)
    print(f"Track '{track}' does not hold the board lock.", file=sys.stderr)
    print(f"", file=sys.stderr)
    print(f"You MUST acquire the lock first:", file=sys.stderr)
    print(f"  BALLOON_TRACK={track} python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire {resource} --purpose 'your test' --timeout 120", file=sys.stderr)
    print(f"", file=sys.stderr)
    print(f"Or check who holds it:", file=sys.stderr)
    print(f"  python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py status", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)
    return False


class BoardSerial(pyserial.Serial):
    """Drop-in replacement for serial.Serial that enforces board mutex lock.

    Behaves identically to pyserial.Serial but refuses to open /dev/ttyACM*
    ports unless the calling track holds the flock.
    """

    def __init__(self, port=None, *args, **kwargs):
        if port and not check_board_lock(port):
            raise PermissionError(
                f"Board lock not held for {port}. "
                f"Run balloon-board-lock.py acquire first. "
                f"See AGENTS.md BOARD ACCESS section."
            )
        super().__init__(port, *args, **kwargs)


# Convenience function for scripts that want explicit checking without opening
def assert_locked(*resources: str):
    """Assert that locks are held for all given resources.

    Exits process with error if any lock is missing.
    """
    import subprocess
    lock_script = Path.home() / "repos" / "balloon-fresh" / "tools" / "balloon-board-lock.py"
    for r in resources:
        # Map resource to a port for check_board_lock
        port_map = {"tx": "/dev/ttyACM0", "rx": "/dev/ttyACM2"}
        port = port_map.get(r, f"/dev/ttyACM0")
        if not check_board_lock(port):
            sys.exit(1)


if __name__ == "__main__":
    # CLI mode: assert lock before proceeding
    import argparse
    parser = argparse.ArgumentParser(description="Check board lock before serial access")
    parser.add_argument("ports", nargs="*", help="Serial ports to check (e.g. /dev/ttyACM0)")
    parser.add_argument("--resource", "-r", action="append", help="Lock resource names (tx, rx)")
    args = parser.parse_args()

    all_ok = True
    for port in args.ports:
        if not check_board_lock(port):
            all_ok = False
    for r in (args.resource or []):
        port_map = {"tx": "/dev/ttyACM0", "rx": "/dev/ttyACM2"}
        port = port_map.get(r, "/dev/ttyACM0")
        if not check_board_lock(port):
            all_ok = False

    if all_ok:
        print("OK: All board locks held by current track")
        sys.exit(0)
    else:
        sys.exit(1)
