#!/usr/bin/env python3
"""
board-lock-monitor.py — Cron monitor for balloon board locks.

Runs every 5 minutes via cron/Hermes scheduler. Reads lock metadata,
computes age, detects stale locks (>2h), and writes a JSON status file.

Output:
    ~/.hermes/peripheral_locks/board-lock-monitor.json

Exit codes:
    0 = normal (no stale locks)
    1 = stale lock detected (held >2h)

Usage:
    python3 ~/repos/balloon-fresh/tools/board-lock-monitor.py
    python3 ~/repos/balloon-fresh/tools/board-lock-monitor.py --stale-threshold 180
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

LOCK_DIR = Path.home() / ".hermes" / "peripheral_locks"
OUTPUT_FILE = LOCK_DIR / "board-lock-monitor.json"

# Resources to monitor
RESOURCES = ["tx", "rx", "board-a", "board-b", "board-c"]

# Default stale threshold: 2 hours = 120 minutes
DEFAULT_STALE_THRESHOLD_MIN = 120


def _read_metadata(path: Path) -> dict | None:
    """Read lock file metadata (JSON content). Returns None if empty/corrupt."""
    if not path.exists():
        return None
    try:
        content = path.read_text().strip()
        if not content:
            return None
        return json.loads(content)
    except (json.JSONDecodeError, OSError):
        return None


def _pid_alive(pid: int) -> bool:
    """Check if a process is alive."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # Alive but not ours
    except (TypeError, ValueError):
        return False


def _compute_age_minutes(acquired_iso: str) -> float | None:
    """Compute age in minutes from an ISO timestamp."""
    try:
        # Handle both with and without timezone suffix
        ts = acquired_iso.replace("Z", "+00:00")
        acq = datetime.fromisoformat(ts)
        if acq.tzinfo is None:
            acq = acq.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - acq).total_seconds() / 60.0
    except (ValueError, TypeError):
        return None


def check_all_locks(stale_threshold_min: int) -> dict:
    """Check all board locks and return a status report."""
    now = datetime.now(timezone.utc)
    locks = []
    stale_detected = False

    for resource in RESOURCES:
        lock_path = LOCK_DIR / f"balloon-{resource}.lock"
        metadata = _read_metadata(lock_path)

        if not metadata or not metadata.get("track"):
            # Lock is free (no metadata or empty)
            locks.append({
                "resource": resource,
                "status": "free",
            })
            continue

        holder = metadata.get("track", "unknown")
        purpose = metadata.get("purpose", "unknown")
        sentinel_pid = metadata.get("sentinel_pid")
        acquired = metadata.get("acquired", "")
        device_locked = metadata.get("device_locked", False)
        device_path = metadata.get("device_path")

        age_min = _compute_age_minutes(acquired) if acquired else None
        sentinel_alive = _pid_alive(sentinel_pid) if sentinel_pid else False

        entry = {
            "resource": resource,
            "status": "locked",
            "holder": holder,
            "purpose": purpose,
            "sentinel_pid": sentinel_pid,
            "sentinel_alive": sentinel_alive,
            "acquired_at": acquired,
            "age_minutes": round(age_min, 1) if age_min is not None else None,
            "device_locked": device_locked,
            "device_path": device_path,
        }

        # Determine if stale
        is_stale = False
        stale_reason = None

        if not sentinel_alive and sentinel_pid:
            # Sentinel died but metadata remains — orphaned lock
            is_stale = True
            stale_reason = "orphaned_sentinel"
        elif age_min is not None and age_min > stale_threshold_min:
            # Held too long
            is_stale = True
            stale_reason = f"held_{age_min:.0f}min_exceeds_{stale_threshold_min}min"

        if is_stale:
            entry["stale"] = True
            entry["stale_reason"] = stale_reason
            stale_detected = True
        else:
            entry["stale"] = False

        locks.append(entry)

    report = {
        "timestamp": now.isoformat(),
        "stale_threshold_min": stale_threshold_min,
        "stale_detected": stale_detected,
        "locked_count": sum(1 for l in locks if l.get("status") == "locked"),
        "free_count": sum(1 for l in locks if l.get("status") == "free"),
        "stale_count": sum(1 for l in locks if l.get("stale")),
        "locks": locks,
    }

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Monitor balloon board locks — detect stale locks for cron alerting",
    )
    parser.add_argument("--stale-threshold", type=int, default=DEFAULT_STALE_THRESHOLD_MIN,
                        help=f"Stale threshold in minutes (default: {DEFAULT_STALE_THRESHOLD_MIN})")
    parser.add_argument("--json", action="store_true",
                        help="Print JSON report to stdout (in addition to file)")
    args = parser.parse_args()

    report = check_all_locks(args.stale_threshold)

    # Write JSON output file
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    try:
        OUTPUT_FILE.write_text(json.dumps(report, indent=2) + "\n")
    except OSError as e:
        print(f"ERROR: Could not write {OUTPUT_FILE}: {e}", file=sys.stderr)

    # Print summary
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        ts = report["timestamp"][:19]
        print(f"[{ts}] Board Lock Monitor")
        print(f"  Locked: {report['locked_count']}  Free: {report['free_count']}  Stale: {report['stale_count']}")
        for entry in report["locks"]:
            if entry["status"] == "locked":
                stale_marker = " ⚠️ STALE" if entry.get("stale") else ""
                age = f" ({entry['age_minutes']}min)" if entry.get("age_minutes") is not None else ""
                print(f"  {entry['resource'].upper()}: held by {entry['holder']}{age}{stale_marker}")
                if entry.get("stale"):
                    print(f"    REASON: {entry.get('stale_reason', '?')}")

    if report["stale_detected"]:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
