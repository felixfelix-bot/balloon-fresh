#!/usr/bin/env python3
"""
board-lock-assert.py — Pre-flight assertion that board locks are held.

Call this at the TOP of every test script. Exits with error if the lock
is not held by the current track.

Usage:
    # Assert TX+RX locks held before proceeding
    python3 ~/repos/balloon-fresh/tools/board-lock-assert.py tx rx

    # In bash:
    python3 ~/repos/balloon-fresh/tools/board-lock-assert.py tx rx || exit 1

Exit codes:
    0 = all locks held by current track
    1 = one or more locks not held
"""

import sys
import os
from pathlib import Path

# Import the check from board-serial.py
sys.path.insert(0, str(Path.home() / "repos" / "balloon-fresh" / "tools"))
from board_serial import check_board_lock

PORT_MAP = {
    "tx": "/dev/ttyACM0",
    "rx": "/dev/ttyACM2",
}

def main():
    track = os.getenv("BALLOON_TRACK")
    if not track:
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"REFUSED: BALLOON_TRACK environment variable not set.", file=sys.stderr)
        print(f"Set it before running any board script:", file=sys.stderr)
        print(f"  export BALLOON_TRACK=speed-tests  # or range-tests, etc", file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: board-lock-assert.py tx [rx] [board-a] ...", file=sys.stderr)
        sys.exit(2)

    resources = sys.argv[1:]
    all_ok = True

    for r in resources:
        port = PORT_MAP.get(r)
        if port is None:
            print(f"SKIP: unknown resource '{r}' (known: {', '.join(PORT_MAP.keys())})", file=sys.stderr)
            continue

        if not check_board_lock(port):
            all_ok = False

    if all_ok:
        track = os.getenv("BALLOON_TRACK", "unknown")
        print(f"OK: locks held for {', '.join(resources)} (track={track})")
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
