#!/usr/bin/env python3
"""
pio_upload_guard.py — PlatformIO pre-upload lock enforcement.

This script hooks into PlatformIO's build system via extra_scripts.
Before ANY upload, it checks that the calling track holds the board lock
for the target port. If the lock is not held, the upload is ABORTED.

Install in platformio.ini:
    extra_scripts = pre:tools/pio_upload_guard.py

The script reads BALLOON_TRACK env var and the upload_port to determine
which lock resource to check.
"""

import os
import sys
import fcntl
import json
import subprocess
from pathlib import Path

LOCK_DIR = Path.home() / ".hermes" / "peripheral_locks"


def _resolve_port_to_resource(port: str) -> str | None:
    """Map serial port path to lock resource name via udev."""
    try:
        result = subprocess.run(
            ["udevadm", "info", "-q", "property", "-n", port],
            capture_output=True, text=True, timeout=5
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
    # Static fallback
    static = {
        "/dev/ttyACM0": "rx",
        "/dev/ttyACM3": "tx",
    }
    return static.get(port)


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


def check_upload_lock(env, target, source):
    """SCons action: check board lock before upload."""
    track = os.getenv("BALLOON_TRACK", "")

    # BLOCK if BALLOON_TRACK not set — no bypass allowed
    if not track:
        msg = (
            f"\n{'='*60}\n"
            f"PIO UPLOAD GUARD: REFUSED\n"
            f"BALLOON_TRACK env var not set. Upload BLOCKED.\n"
            f"This prevents unauthorized flashes from overwriting walk-test firmware.\n"
            f"\n"
            f"Set it before flashing:\n"
            f"  export BALLOON_TRACK=range-tests  (or speed-tests)\n"
            f"{'='*60}\n"
        )
        sys.stderr.write(msg)
        sys.exit(1)

    # Get upload port from PlatformIO config
    upload_port = env.GetProjectOption("upload_port", "")

    # If not in platformio.ini, check command-line override
    if not upload_port:
        for arg in sys.argv:
            if arg.startswith("--upload-port"):
                if "=" in arg:
                    upload_port = arg.split("=", 1)[1]
                # else next arg might be the port

    # If still no port, check env vars
    if not upload_port:
        upload_port = os.getenv("PLATFORMIO_UPLOAD_PORT", "")

    if not upload_port or "ttyACM" not in str(upload_port):
        # No serial upload port — could be network upload. Skip check.
        return

    resource = _resolve_port_to_resource(str(upload_port))
    if not resource:
        print(f"WARNING: Could not resolve lock resource for {upload_port}")
        return

    if not _lock_held_by_us(resource):
        msg = (
            f"\n{'='*60}\n"
            f"PIO UPLOAD GUARD: REFUSED\n"
            f"Track '{track}' does not hold the '{resource}' board lock.\n"
            f"Upload port: {upload_port} → resource: {resource}\n"
            f"\n"
            f"Acquire the lock FIRST:\n"
            f"  BALLOON_TRACK={track} python3 ~/repos/balloon-fresh/tools/"
            f"balloon-board-lock.py acquire {resource} --purpose 'firmware upload'\n"
            f"{'='*60}\n"
        )
        sys.stderr.write(msg)
        sys.exit(1)
    else:
        print(f"[LOCK OK] Track '{track}' holds '{resource}' lock for {upload_port}")


# ─── SCons hook registration ─────────────────────────────────────────────
# This runs when PlatformIO processes the extra_scripts directive.
Import("env")

# Hook before upload target
env.AddPreAction(
    "upload",
    check_upload_lock
)
