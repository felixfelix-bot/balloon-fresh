#!/usr/bin/env python3
"""
board_serial_guard.py — Automatic monkeypatch for serial.Serial.

When BALLOON_TRACK env var is set, this intercepts ALL serial.Serial() calls
on /dev/ttyACM* ports and enforces the board flock lock. Scripts that bypass
BoardSerial() by using raw serial.Serial() are STILL blocked.

Install via usercustomize.py — see install-serial-guard.sh.
Safe for non-balloon Python: no effect when BALLOON_TRACK is unset.
"""

import os
import sys
import fcntl
import json
from pathlib import Path

LOCK_DIR = Path.home() / ".hermes" / "peripheral_locks"


def _resolve_port_to_resource(port: str) -> str | None:
    """Map serial port path to lock resource name via udev serial number."""
    import subprocess
    try:
        result = subprocess.run(
            ["udevadm", "info", "-q", "property", "-n", port],
            capture_output=True, text=True, timeout=3
        )
        for line in result.stdout.split("\n"):
            if line.startswith("ID_SERIAL_SHORT="):
                sn = line.split("=", 1)[1]
                if "F242D" in sn:
                    return "tx"
                if "8332" in sn:
                    return "rx"
    except Exception:
        pass
    return None


def _lock_held_by_us(resource: str) -> bool:
    """Check if flock for resource is held by our track."""
    lock_path = LOCK_DIR / f"balloon-{resource}.lock"
    if not lock_path.exists():
        return False
    fd = None
    try:
        fd = os.open(str(lock_path), os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False  # We got it → nobody holds it
        except BlockingIOError:
            try:
                data = json.loads(lock_path.read_text())
                return data.get("track") == os.getenv("BALLOON_TRACK", "unknown")
            except (json.JSONDecodeError, OSError):
                return False
    except OSError:
        return False
    finally:
        if fd is not None:
            os.close(fd)


def install_guard():
    """Monkeypatch serial.Serial to enforce board lock."""
    try:
        import serial as pyserial
    except ImportError:
        return  # pyserial not installed, nothing to guard

    # Avoid double-patch
    if getattr(pyserial.Serial, '_board_guard_installed', False):
        return

    _orig_init = pyserial.Serial.__init__

    def _guarded_init(self, port=None, *args, **kwargs):
        if port and "/dev/ttyACM" in str(port):
            resource = _resolve_port_to_resource(str(port))
            if resource and not _lock_held_by_us(resource):
                track = os.getenv("BALLOON_TRACK", "unknown")
                msg = (
                    f"\n{'='*60}\n"
                    f"BOARD LOCK GUARD: REFUSED to open {port} ({resource})\n"
                    f"Track '{track}' does not hold the board lock.\n"
                    f"\n"
                    f"Acquire the lock first:\n"
                    f"  BALLOON_TRACK={track} python3 "
                    f"~/repos/balloon-fresh/tools/balloon-board-lock.py "
                    f"acquire {resource} --purpose 'test' --timeout 120\n"
                    f"{'='*60}\n"
                )
                raise PermissionError(msg)
        _orig_init(self, port, *args, **kwargs)

    pyserial.Serial.__init__ = _guarded_init
    setattr(pyserial.Serial, '_board_guard_installed', True)
