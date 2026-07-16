#!/usr/bin/env python3
"""
balloon-board-lock.py -- Mutex lock for RP2040/ESP32 board access.

Prevents concurrent LLM sessions (speed-test, range-test, etc.) from
accessing the same physical boards simultaneously.

LOCK FILES: ~/.hermes/peripheral_locks/balloon-{tx,rx}.lock
STALE TIMEOUT: 15 minutes (auto-release if holder crashed)

USAGE:
    # Acquire TX board (blocks up to 120s)
    BALLOON_TRACK=speed-tests python3 balloon-board-lock.py acquire tx \\
        --purpose "flash timing diag" --timeout 120

    # Acquire both boards (for coordinated TX/RX tests)
    BALLOON_TRACK=speed-tests python3 balloon-board-lock.py acquire both \\
        --purpose "coordinated throughput test" --timeout 120

    # Release
    python3 balloon-board-lock.py release tx
    python3 balloon-board-lock.py release both --force

    # Status (who holds what)
    python3 balloon-board-lock.py status

EXIT CODES:
    0 = acquired / released / status shown
    1 = failed to acquire (timeout or held by other session)
    2 = invalid arguments
"""

import json
import os
import sys
import time
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

LOCK_DIR = Path.home() / ".hermes" / "peripheral_locks"
LOCK_DIR.mkdir(parents=True, exist_ok=True)

STALE_THRESHOLD = timedelta(minutes=15)


def _identity() -> dict:
    """Unique identity for this process/session."""
    return {
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "user": os.getenv("USER", "unknown"),
        "hermes_profile": os.getenv("HERMES_PROFILE", "manager"),
        "track": os.getenv("BALLOON_TRACK", "unknown"),
        "started": datetime.now(timezone.utc).isoformat(),
    }


def _lock_path(resource: str) -> Path:
    return LOCK_DIR / f"balloon-{resource}.lock"


def _get_resources(resource: str) -> list:
    if resource == "both":
        return ["tx", "rx"]
    return [resource]


def _read_lock(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _is_stale(data: dict) -> bool:
    """Check if lock is expired (TTL-based only, no PID check).

    Locks are held by LLM sessions across separate processes. The acquiring
    process exits immediately after writing the lock. Only the 15-min TTL
    timestamp determines staleness.
    """
    ts_str = data.get("timestamp", "")
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) - ts > STALE_THRESHOLD
    except (ValueError, TypeError):
        return True


def _write_lock(path: Path, purpose: str, identity: dict):
    data = {
        "locked": True,
        "resource": path.stem.replace("balloon-", ""),
        "purpose": purpose,
        "identity": identity,
        "pid": identity["pid"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "expires_after_min": STALE_THRESHOLD.total_seconds() / 60,
    }
    path.write_text(json.dumps(data, indent=2))


def _try_acquire_one(path: Path, purpose: str, identity: dict) -> bool:
    """Try to acquire one lock. Returns True on success."""
    existing = _read_lock(path)
    if existing is not None and existing.get("locked"):
        if _is_stale(existing):
            print(f"  Stale lock (held since {existing.get('timestamp')}), reclaiming", file=sys.stderr)
            _write_lock(path, purpose, identity)
            return True
        return False
    _write_lock(path, purpose, identity)
    return True


def _remove_lock(path: Path, identity: dict, force: bool = False) -> bool:
    """Remove lock. Returns True if removed."""
    if not path.exists():
        return True
    if force:
        path.unlink(missing_ok=True)
        return True
    existing = _read_lock(path)
    if existing is None:
        path.unlink(missing_ok=True)
        return True
    if _is_stale(existing):
        path.unlink(missing_ok=True)
        return True
    # Same track session can release its own locks
    holder_track = existing.get("identity", {}).get("track", "?")
    our_track = identity.get("track", "?")
    if holder_track != "unknown" and holder_track == our_track:
        path.unlink(missing_ok=True)
        return True
    return False


def acquire(resource: str, purpose: str, timeout_s: int) -> int:
    resources = _get_resources(resource)
    identity = _identity()
    deadline = time.monotonic() + timeout_s if timeout_s > 0 else 0

    while True:
        all_acquired = True
        for r in resources:
            path = _lock_path(r)
            if not _try_acquire_one(path, purpose, identity):
                all_acquired = False
                break

        if all_acquired:
            # Double-check race condition
            time.sleep(0.05)
            for r in resources:
                path = _lock_path(r)
                data = _read_lock(path)
                if data and data.get("pid") != identity["pid"]:
                    all_acquired = False
                    break

            if all_acquired:
                board_list = "+".join(resources)
                print(f"ACQUIRED: {board_list} (purpose: {purpose})")
                print(f"  PID={identity['pid']} track={identity['track']}")
                return 0

        # Failed -- release any partial locks
        for r in resources:
            path = _lock_path(r)
            _remove_lock(path, identity)

        if timeout_s > 0 and time.monotonic() >= deadline:
            for r in resources:
                path = _lock_path(r)
                data = _read_lock(path)
                if data and data.get("locked"):
                    holder_pid = data.get("pid", "?")
                    holder_purpose = data.get("purpose", "?")
                    holder_track = data.get("identity", {}).get("track", "?")
                    ts = data.get("timestamp", "?")
                    age = ""
                    try:
                        lock_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        age_min = (datetime.now(timezone.utc) - lock_time).total_seconds() / 60
                        age = f" ({age_min:.0f}min ago)"
                    except Exception:
                        pass
                    print(f"BLOCKED: {r} held by track={holder_track} PID={holder_pid} (purpose: {holder_purpose}){age}", file=sys.stderr)
            return 1

        if timeout_s > 0:
            remaining = deadline - time.monotonic()
            print(f"\r  Waiting for {resource}... ({remaining:.0f}s remaining)  ", end="", file=sys.stderr, flush=True)
        time.sleep(2)


def release(resource: str, force: bool) -> int:
    resources = _get_resources(resource)
    identity = _identity()
    released_any = False

    for r in resources:
        path = _lock_path(r)
        if _remove_lock(path, identity, force=force):
            tag = "force" if force else "ok"
            print(f"RELEASED ({tag}): {r}")
            released_any = True
        else:
            data = _read_lock(path)
            if data:
                holder_track = data.get("identity", {}).get("track", "?")
                print(f"SKIP: {r} held by track={holder_track} PID={data.get('pid', '?')} (not ours, not stale, use --force)", file=sys.stderr)
            else:
                print(f"SKIP: {r} not locked")

    return 0 if released_any else 1


def status() -> int:
    """Print status of all balloon board locks."""
    print("=== Balloon Board Lock Status ===")
    for resource in ["tx", "rx"]:
        path = _lock_path(resource)
        data = _read_lock(path)
        if data is None or not data.get("locked"):
            print(f"  {resource.upper()}: FREE")
            continue
        stale = _is_stale(data)
        pid = data.get("pid", "?")
        purpose = data.get("purpose", "?")
        track = data.get("identity", {}).get("track", "?")
        ts = data.get("timestamp", "?")
        flag = "STALE" if stale else "ACTIVE"
        print(f"  {resource.upper()}: LOCKED [{flag}] by track={track} PID={pid}")
        print(f"    purpose: {purpose}")
        print(f"    since:   {ts}")
    print()

    # Show connected boards
    print("Connected boards:")
    import subprocess
    try:
        result = subprocess.run(
            ["sh", "-c", "for d in /dev/ttyACM*; do echo \"$d: $(udevadm info -q property -n $d 2>/dev/null | grep -E 'ID_SERIAL_SHORT|ID_MODEL=' | head -2)\"; done"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.strip().split("\n"):
            if line:
                print(f"  {line}")
    except Exception:
        pass
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Balloon board mutex lock -- prevents concurrent LLM session conflicts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  BALLOON_TRACK=speed-tests %(prog)s acquire tx --purpose "flash single-batch firmware" --timeout 120
  BALLOON_TRACK=speed-tests %(prog)s acquire both --purpose "coordinated throughput test" --timeout 180
  %(prog)s release tx
  %(prog)s release both --force
  %(prog)s status
        """)
    parser.add_argument("action", choices=["acquire", "release", "status"],
                        help="Action to perform")
    parser.add_argument("resource", nargs="?", choices=["tx", "rx", "both"],
                        help="Which board(s) to lock/unlock")
    parser.add_argument("--purpose", default="unspecified",
                        help="Why you need the board (shown to other sessions)")
    parser.add_argument("--timeout", type=int, default=120,
                        help="Max seconds to wait for lock (default: 120)")
    parser.add_argument("--force", action="store_true",
                        help="Force release even if not ours")
    args = parser.parse_args()

    if args.action == "status":
        sys.exit(status())

    if not args.resource:
        print("Error: resource (tx/rx/both) required for acquire/release", file=sys.stderr)
        sys.exit(2)

    if args.action == "acquire":
        sys.exit(acquire(args.resource, args.purpose, args.timeout))
    elif args.action == "release":
        sys.exit(release(args.resource, args.force))


if __name__ == "__main__":
    main()
