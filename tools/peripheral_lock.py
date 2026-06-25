#!/usr/bin/env python3
"""
peripheral_lock.py — File-based advisory locking for hardware peripherals.

Generalizes the physical-router-test-automation/lib/router_lock.py pattern
to support ANY peripheral (ESP32 boards, RP2040, LR2021 modules, etc).

Prevents concurrent subagent/worker sessions from accessing the same
physical peripheral simultaneously. Uses simple key-value lock files with
stale detection (auto-release after 2 hours).

Usage as context manager:
    with PeripheralLock("rp2040", "speed-test") as lock:
        # RP2040 is exclusively locked for this session
        ...
    # lock released automatically

Manual usage:
    lock = PeripheralLock("esp32-c3-tx")
    lock.acquire(phase="range-test", session="subagent-1")
    try:
        ...
    finally:
        lock.release()

CLI:
    python3 peripheral_lock.py list                    # show all locks
    python3 peripheral_lock.py acquire rp2040 --phase "speed-test"
    python3 peripheral_lock.py release rp2040
    python3 peripheral_lock.py status                  # JSON status of all
"""

import os
import json
import platform
import sys
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

LOCK_DIR = Path.home() / ".hermes" / "peripheral_locks"
STALE_THRESHOLD = timedelta(hours=2)


def _session_id() -> str:
    return f"{os.getenv('USER', 'unknown')}@{platform.node()}"


def _git_branch(cwd: str = None) -> str:
    import subprocess
    try:
        r = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5, cwd=cwd or os.getcwd()
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return "unknown"


class PeripheralLock:
    """File-based advisory lock for a single peripheral."""

    def __init__(self, peripheral_id: str, lock_dir: Path = None):
        self.peripheral_id = peripheral_id
        self._lock_dir = lock_dir or LOCK_DIR
        self._lock_dir.mkdir(parents=True, exist_ok=True)
        self._lock_path = self._lock_dir / f"{peripheral_id}.lock"
        self._held = False

    @property
    def lock_path(self) -> Path:
        return self._lock_path

    def acquire(self, phase: str = "unknown", session: str = None,
                timeout_s: float = 0) -> bool:
        """
        Acquire the lock. Returns True if acquired.
        If timeout_s > 0, waits up to timeout_s seconds for the lock.
        Raises RuntimeError if lock is held by another session and not stale.
        """
        if self._held:
            return True

        session = session or _session_id()
        deadline = datetime.now(timezone.utc) + timedelta(seconds=timeout_s)

        while True:
            existing = self._read_lock()
            if existing is None or not existing.get("locked"):
                break

            # Check if stale
            if self._is_stale(existing):
                print(f"WARNING: Stale lock on {self.peripheral_id} "
                      f"(held since {existing.get('timestamp')}), overwriting",
                      file=sys.stderr)
                break

            # Check if we already hold it
            if existing.get("session") == session:
                self._held = True
                return True

            # Still locked by someone else
            if datetime.now(timezone.utc) >= deadline:
                holder = existing.get("session", "?")
                hold_phase = existing.get("phase", "?")
                if timeout_s > 0:
                    return False
                raise RuntimeError(
                    f"Peripheral '{self.peripheral_id}' is locked by "
                    f"{holder} (phase: {hold_phase}). "
                    f"Use PeripheralLock('{self.peripheral_id}').release() "
                    f"or wait for stale timeout ({STALE_THRESHOLD})."
                )

            import time
            time.sleep(1)

        # Write the lock
        data = {
            "locked": "true",
            "peripheral": self.peripheral_id,
            "session": session,
            "phase": phase,
            "branch": _git_branch(),
            "pid": os.getpid(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._lock_path.write_text(json.dumps(data, indent=2))
        self._held = True
        return True

    def release(self):
        """Release the lock."""
        if not self._held:
            return
        if self._lock_path.exists():
            existing = self._read_lock()
            if existing and existing.get("session") == _session_id():
                self._lock_path.unlink()
        self._held = False

    def _read_lock(self) -> dict | None:
        if not self._lock_path.exists():
            return None
        try:
            return json.loads(self._lock_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def _is_stale(self, data: dict) -> bool:
        ts_str = data.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) - ts > STALE_THRESHOLD
        except (ValueError, TypeError):
            return True

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()


def list_locks() -> dict:
    """Return status of all peripheral locks."""
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    locks = {}
    for f in LOCK_DIR.glob("*.lock"):
        try:
            data = json.loads(f.read_text())
            peripheral = data.get("peripheral", f.stem)
            stale = False
            ts_str = data.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                stale = datetime.now(timezone.utc) - ts > STALE_THRESHOLD
            except:
                stale = True
            locks[peripheral] = {
                "locked": data.get("locked") == "true",
                "session": data.get("session"),
                "phase": data.get("phase"),
                "pid": data.get("pid"),
                "timestamp": ts_str,
                "stale": stale,
                "lock_file": str(f),
            }
        except Exception:
            locks[f.stem] = {"locked": False, "error": "corrupt lock file"}
    return locks


def detect_peripherals() -> dict:
    """Detect connected peripherals via USB/serial."""
    import glob
    peripherals = {}

    # Serial ports
    serial_ports = glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")
    for port in serial_ports:
        peripherals[port] = {"type": "serial", "port": port}

    # USB devices (via lsusb)
    import subprocess
    try:
        r = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            if "2e8a:" in line:  # Raspberry Pi / RP2040
                peripherals["rp2040"] = {"type": "rp2040", "usb": line.strip()}
            elif "303a:" in line or "1a86:" in line or "10c4:" in line:
                peripherals["esp32"] = {"type": "esp32", "usb": line.strip()}
    except:
        pass

    return peripherals


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Peripheral lock manager")
    parser.add_argument("action", choices=["list", "acquire", "release", "status", "detect"],
                        help="Action to perform")
    parser.add_argument("peripheral", nargs="?", help="Peripheral ID")
    parser.add_argument("--phase", default="unknown", help="Phase/description")
    parser.add_argument("--timeout", type=float, default=0, help="Wait timeout (seconds)")
    args = parser.parse_args()

    if args.action == "list":
        locks = list_locks()
        if not locks:
            print("No peripheral locks.")
        for p, d in locks.items():
            status = "🔒 LOCKED" if d.get("locked") else "🔓 free"
            stale = " (STALE)" if d.get("stale") else ""
            print(f"  {status}{stale} {p}: {d.get('session', '?')} "
                  f"({d.get('phase', '?')})")
    elif args.action == "status":
        print(json.dumps({"locks": list_locks(), "peripherals": detect_peripherals()},
                         indent=2))
    elif args.action == "detect":
        periphs = detect_peripherals()
        if not periphs:
            print("No peripherals detected.")
        for name, info in periphs.items():
            print(f"  {name}: {info}")
    elif args.action == "acquire":
        if not args.peripheral:
            print("Error: peripheral ID required"); sys.exit(1)
        lock = PeripheralLock(args.peripheral)
        if lock.acquire(phase=args.phase, timeout_s=args.timeout):
            print(f"Acquired lock on {args.peripheral} ({lock.lock_path})")
        else:
            print(f"Failed to acquire lock on {args.peripheral} (timeout)")
            sys.exit(1)
    elif args.action == "release":
        if not args.peripheral:
            print("Error: peripheral ID required"); sys.exit(1)
        lock = PeripheralLock(args.peripheral)
        lock.release()
        print(f"Released lock on {args.peripheral}")
