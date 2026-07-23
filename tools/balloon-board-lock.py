#!/usr/bin/env python3
"""
balloon-board-lock.py -- OS-enforced mutex lock for board access.

Uses flock(2) for TRUE mutual exclusion. A sentinel daemon process holds the
flock open for the duration of the lock. The sentinel monitors the caller's
process tree and auto-releases when the Hermes session dies.

This replaces the old TTL-based approach which had a fatal flaw: locks expired
(15 min) while sessions were still actively using the boards, allowing another
session to reclaim a "stale" lock mid-test.

LOCK FILES: ~/.hermes/peripheral_locks/balloon-{tx,rx,board-a,board-b,board-c}.lock

RESOURCES:
    tx, rx       — RP2040 boards (speed-tests, range-tests)
    board-a      — ESP32-S3 board A (MAC 94:a9:90:2e:37:7c, TollGate-B96D80)
    board-b      — ESP32-S3 board B (MAC fc:01:2c:c5:50:50, TollGate-C0E9CA)
    board-c      — ESP32-S3 board C (MAC 20:6e:f1:98:d7:08, display board)
    all-s3       — All 3 ESP32-S3 boards (board-a + board-b + board-c)
    both         — TX + RX (RP2040 pair)
    all          — All boards (tx + rx + board-a + board-b + board-c)

USAGE:
    # Acquire TX board (blocks up to 120s)
    BALLOON_TRACK=speed-tests python3 balloon-board-lock.py acquire tx \\
        --purpose "flash timing diag" --timeout 120

    # Acquire both RP2040 boards (for coordinated TX/RX tests)
    BALLOON_TRACK=speed-tests python3 balloon-board-lock.py acquire both \\
        --purpose "coordinated throughput test" --timeout 120

    # Release
    BALLOON_TRACK=speed-tests python3 balloon-board-lock.py release tx
    python3 balloon-board-lock.py release both --force

    # Status (who holds what)
    python3 balloon-board-lock.py status

EXIT CODES:
    0 = acquired / released / status shown
    1 = failed to acquire (timeout or held by other session)
    2 = invalid arguments
"""

import ctypes
import ctypes.util
import fcntl
import json
import os
import signal
import sys
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path

LOCK_DIR = Path.home() / ".hermes" / "peripheral_locks"
LOCK_DIR.mkdir(parents=True, exist_ok=True)

# Linux prctl constants
PR_SET_PDEATHSIG = 1
PR_SET_NAME = 15


def _prctl(option, value):
    """Call prctl(2) — used for parent-death signal."""
    libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    libc.prctl.restype = ctypes.c_int
    return libc.prctl(option, value, 0, 0, 0)


def _get_grandparent_pid():
    """Walk up to find the Hermes session PID (skip ephemeral shells).

    Process tree: Hermes agent → bash -c "..." → python3 balloon-board-lock.py
    We want the Hermes agent PID so the sentinel can monitor it.
    """
    pid = os.getpid()
    ppid = os.getppid()
    gpids = [pid, ppid]
    try:
        with open(f"/proc/{ppid}/stat") as f:
            stat = f.read().split()
            gppid = int(stat[3])  # 4th field = ppid
            gpids.append(gppid)
        # Walk one more level up
        with open(f"/proc/{gppid}/stat") as f:
            stat = f.read().split()
            ggppid = int(stat[3])
            gpids.append(ggppid)
    except (FileNotFoundError, ValueError, IndexError):
        pass
    # Return the highest ancestor we found (most likely the Hermes process)
    return gpids[-1] if len(gpids) > 2 else ppid


def _identity():
    return {
        "track": os.getenv("BALLOON_TRACK", "unknown"),
        "pid": os.getpid(),
    }


def _lock_path(resource: str) -> Path:
    return LOCK_DIR / f"balloon-{resource}.lock"


def _get_resources(resource: str) -> list:
    if resource == "both":
        return ["tx", "rx"]
    if resource == "all-s3":
        return ["board-a", "board-b", "board-c"]
    if resource == "all":
        return ["tx", "rx", "board-a", "board-b", "board-c"]
    return [resource]


def _read_metadata(path: Path) -> dict | None:
    """Read lock file metadata (JSON content)."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
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


def _is_locked(path: Path) -> bool:
    """Check if the flock is actually held by testing LOCK_EX | LOCK_NB.

    This is the authoritative check — flock is OS-enforced.
    """
    if not path.exists():
        return False
    fd = None
    try:
        fd = os.open(str(path), os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # We got the lock → nobody was holding it
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False
        except BlockingIOError:
            return True
    except OSError:
        return False
    finally:
        if fd is not None:
            os.close(fd)


def _start_sentinel(fd: int, path: Path, metadata: dict):
    """Fork a sentinel daemon that holds the flock and monitors the caller.

    The sentinel:
    1. Holds the flock via its inherited fd
    2. Monitors the caller process (Hermes agent PID)
    3. Exits when the caller dies → fd closes → flock released
    4. Writes metadata to the lock file
    """
    monitor_pid = metadata.get("monitor_pid", 0)

    sentinel_pid = os.fork()
    if sentinel_pid != 0:
        # Parent: return the sentinel PID
        return sentinel_pid

    # CHILD — sentinel daemon
    os.setsid()  # Detach from controlling terminal
    os.umask(0)

    # Set process name for easy identification
    try:
        resource = metadata.get("resource", "?")
        _prctl(PR_SET_NAME, 0)  # Clear
    except Exception:
        pass

    # Write metadata to lock file
    metadata["sentinel_pid"] = os.getpid()
    metadata["started"] = datetime.now(timezone.utc).isoformat()
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
        os.write(fd, json.dumps(metadata, indent=2).encode())
    except OSError:
        pass

    # Monitor loop: check if the Hermes process is still alive
    # Also serve as a heartbeat — our existence means the lock is held
    while True:
        time.sleep(10)
        if monitor_pid > 0 and not _pid_alive(monitor_pid):
            # Caller process died → release the lock
            break

    # Cleanup: truncate metadata, close fd (releases flock)
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
    except OSError:
        pass
    os.close(fd)
    os._exit(0)


def acquire(resource: str, purpose: str, timeout_s: int) -> int:
    resources = _get_resources(resource)
    identity = _identity()
    monitor_pid = _get_grandparent_pid()

    # First, try to acquire ALL needed resources
    held_fds = []
    held_paths = []
    held_sentinels = []

    deadline = time.monotonic() + timeout_s if timeout_s > 0 else 0

    while True:
        all_ok = True
        # Clean up any previous partial acquisitions
        for fd, spath, spid in zip(held_fds, held_paths, held_sentinels):
            if spid:
                try:
                    os.kill(spid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
            os.close(fd)
        held_fds = []
        held_paths = []
        held_sentinels = []

        for r in resources:
            path = _lock_path(r)

            # Ensure lock file exists
            path.touch()

            fd = os.open(str(path), os.O_RDWR)

            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Got the lock!
            except BlockingIOError:
                # Check if it's truly locked or just stale metadata
                all_ok = False
                os.close(fd)

                # Read who holds it for the error message
                data = _read_metadata(path)
                if data:
                    holder_track = data.get("track", "?")
                    holder_purpose = data.get("purpose", "?")
                    sentinel_pid = data.get("sentinel_pid", "?")
                    print(f"BLOCKED: {r} held by track={holder_track} "
                          f"sentinel={sentinel_pid} (purpose: {holder_purpose})",
                          file=sys.stderr)

                # Break to retry loop
                break

            # We have the flock. Start sentinel to hold it.
            metadata = {
                "resource": r,
                "track": identity["track"],
                "purpose": purpose,
                "monitor_pid": monitor_pid,
                "acquired": datetime.now(timezone.utc).isoformat(),
            }
            sentinel_pid = _start_sentinel(fd, path, metadata)
            held_fds.append(fd)
            held_paths.append(path)
            held_sentinels.append(sentinel_pid)

        if all_ok:
            board_list = "+".join(resources)
            print(f"ACQUIRED: {board_list} (purpose: {purpose})")
            print(f"  track={identity['track']} monitor_pid={monitor_pid}")
            for r, spid in zip(resources, held_sentinels):
                print(f"  {r}: sentinel PID={spid}")
            # Close our parent copies — sentinels hold their own fd copies
            for fd in held_fds:
                try:
                    os.close(fd)
                except OSError:
                    pass
            return 0

        if timeout_s > 0 and time.monotonic() >= deadline:
            return 1

        if timeout_s > 0:
            remaining = deadline - time.monotonic()
            print(f"\r  Waiting for {resource}... ({remaining:.0f}s remaining)  ",
                  end="", file=sys.stderr, flush=True)
        time.sleep(2)


def release(resource: str, force: bool) -> int:
    resources = _get_resources(resource)
    identity = _identity()
    released_any = False

    for r in resources:
        path = _lock_path(r)
        data = _read_metadata(path)

        if data is None:
            print(f"FREE: {r} (no lock file)")
            released_any = True
            continue

        sentinel_pid = data.get("sentinel_pid")
        holder_track = data.get("track", "?")

        if not force and holder_track != "unknown" and holder_track != identity["track"]:
            print(f"SKIP: {r} held by track={holder_track} "
                  f"(not ours, use --force)", file=sys.stderr)
            continue

        # Kill the sentinel → fd closes → flock released
        if sentinel_pid:
            try:
                os.kill(sentinel_pid, signal.SIGTERM)
                # Wait briefly for cleanup
                time.sleep(0.3)
                print(f"RELEASED: {r} (killed sentinel {sentinel_pid})")
                released_any = True
            except ProcessLookupError:
                # Sentinel already dead — check if flock is truly free
                if _is_locked(path):
                    print(f"STALE: {r} metadata says sentinel dead but flock held — use --force",
                          file=sys.stderr)
                else:
                    print(f"RELEASED: {r} (sentinel already dead, flock was free)")
                    released_any = True
        else:
            # No sentinel PID in metadata — try force-unlock
            if force:
                fd = os.open(str(path), os.O_RDWR)
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(fd, fcntl.LOCK_UN)
                    print(f"RELEASED: {r} (force — flock was free)")
                    released_any = True
                except BlockingIOError:
                    print(f"BLOCKED: {r} flock held by unknown process — cannot force-release",
                          file=sys.stderr)
                os.close(fd)
            else:
                print(f"SKIP: {r} no sentinel PID in metadata (use --force)",
                      file=sys.stderr)

    return 0 if released_any else 1


def status() -> int:
    """Print status of all balloon board locks."""
    print("=== Balloon Board Lock Status (flock-based) ===")
    for resource in ["tx", "rx", "board-a", "board-b", "board-c"]:
        path = _lock_path(resource)
        locked = _is_locked(path)
        data = _read_metadata(path)

        if not locked:
            print(f"  {resource.upper()}: FREE")
            # Clean up stale metadata
            if data and data.get("sentinel_pid"):
                if not _pid_alive(data["sentinel_pid"]):
                    try:
                        path.write_text("")
                    except OSError:
                        pass
            continue

        # Lock is held
        track = data.get("track", "?") if data else "?"
        purpose = data.get("purpose", "?") if data else "?"
        sentinel_pid = data.get("sentinel_pid", "?") if data else "?"
        acquired = data.get("acquired", "?") if data else "?"

        sentinel_alive = _pid_alive(data["sentinel_pid"]) if data and data.get("sentinel_pid") else False

        if not sentinel_alive:
            print(f"  {resource.upper()}: LOCKED [ORPHANED — sentinel dead but flock held?!]")
        else:
            age = ""
            try:
                acq = datetime.fromisoformat(acquired.replace("Z", "+00:00"))
                age_min = (datetime.now(timezone.utc) - acq).total_seconds() / 60
                age = f" ({age_min:.1f}min)"
            except Exception:
                pass
            print(f"  {resource.upper()}: LOCKED by track={track}{age}")
            print(f"    purpose:      {purpose}")
            print(f"    sentinel:     {sentinel_pid}")
            print(f"    acquired:     {acquired}")

    print()

    # Show connected boards
    print("Connected boards:")
    import subprocess
    try:
        result = subprocess.run(
            ["sh", "-c",
             'for d in /dev/ttyACM*; do echo "$d: $(udevadm info -q property -n $d 2>/dev/null '
             '| grep -E \'ID_SERIAL_SHORT|ID_MODEL=\' | head -2)"; done'],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.strip().split("\n"):
            if line:
                print(f"  {line}")
    except Exception:
        pass

    # Show running sentinels
    try:
        result = subprocess.run(
            ["sh", "-c", "ps aux | grep 'balloon-board-lock' | grep -v grep | head -10"],
            capture_output=True, text=True, timeout=5,
        )
        sentinels = [l for l in result.stdout.strip().split("\n") if l]
        if sentinels:
            print(f"\nRunning sentinel processes:")
            for s in sentinels:
                print(f"  {s}")
    except Exception:
        pass

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Balloon board mutex lock (flock-based) — prevents concurrent board access",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  BALLOON_TRACK=speed-tests %(prog)s acquire tx --purpose "flash single-batch firmware" --timeout 120
  BALLOON_TRACK=speed-tests %(prog)s acquire both --purpose "coordinated throughput test" --timeout 180
  BALLOON_TRACK=range-tests %(prog)s release tx
  %(prog)s release both --force
  %(prog)s status
        """)
    parser.add_argument("action", choices=["acquire", "release", "status"],
                        help="Action to perform")
    parser.add_argument("resource", nargs="?",
                        choices=["tx", "rx", "both", "board-a", "board-b", "board-c", "all-s3", "all"],
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
