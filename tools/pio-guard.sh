#!/bin/bash
# pio-guard.sh — PATH shim that intercepts `pio run -t upload` and `picotool`
# commands, checking that the caller holds the board lock.
#
# This makes it mechanically impossible for sub-managers to bypass the board
# lock by calling `pio run -e <env> -t upload` directly (instead of pio-flash.sh)
# or by calling `picotool` directly.
#
# INSTALL:
#   export PATH="$HOME/worktrees/balloon-speed-tests/tools/shims:$PATH"
#
# The shim directory contains symlinks:
#   tools/shims/pio       → ../pio-guard.sh
#   tools/shims/picotool  → ../pio-guard.sh
#
# The script auto-detects which tool it was invoked as via $0 basename.

set -euo pipefail

# ─── Resolve which tool we're impersonating ──────────────────────────────
SCRIPT_NAME="$(basename "$0")"
LOCK_DIR="$HOME/.hermes/peripheral_locks"

# ─── Board serial lookup (shared with balloon-board-lock.py) ─────────────
# TX: serial contains "F242D", RX: serial contains "8332"
resolve_resource_for_port() {
    local port="$1"
    python3 -c "
import subprocess, sys
try:
    r = subprocess.run(['udevadm', 'info', '-q', 'property', '-n', '$port'],
                       capture_output=True, text=True, timeout=5)
    for l in r.stdout.split('\n'):
        if 'ID_SERIAL_SHORT=' in l:
            sn = l.split('=', 1)[1]
            if 'F242D' in sn: print('tx'); break
            if '8332' in sn: print('rx'); break
except Exception:
    pass
" 2>/dev/null
}

# ─── Check board lock for all connected boards ───────────────────────────
check_board_lock() {
    # Require BALLOON_TRACK to be set
    local track="${BALLOON_TRACK:-}"
    if [ -z "$track" ]; then
        echo "============================================================" >&2
        echo "GUARD: BALLOON_TRACK not set. Upload/access BLOCKED." >&2
        echo "" >&2
        echo "Set it first:" >&2
        echo "  export BALLOON_TRACK=speed-tests  # or your track name" >&2
        echo "============================================================" >&2
        exit 1
    fi

    # Check each connected ACM port
    local found_board=false
    for port in /dev/ttyACM*; do
        [ -e "$port" ] || continue
        local resource
        resource="$(resolve_resource_for_port "$port")"
        if [ -n "$resource" ]; then
            found_board=true
            local lock_file="$LOCK_DIR/balloon-$resource.lock"
            if [ -f "$lock_file" ]; then
                local holder
                holder="$(python3 -c "import json; print(json.load(open('$lock_file')).get('track','unknown'))" 2>/dev/null || echo "unknown")"
                if [ "$holder" != "$track" ]; then
                    echo "============================================================" >&2
                    echo "GUARD: Board $resource ($port) locked by track='$holder'," >&2
                    echo "       not track='$track'. Access BLOCKED." >&2
                    echo "" >&2
                    echo "Acquire the lock first:" >&2
                    echo "  BALLOON_TRACK=$track python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire $resource" >&2
                    echo "============================================================" >&2
                    exit 1
                fi
                # Lock held by us — OK
            else
                # Board connected but no lock file — nobody holds the lock
                echo "============================================================" >&2
                echo "GUARD: Board $resource ($port) has NO lock held." >&2
                echo "       Access BLOCKED — acquire the lock first:" >&2
                echo "  BALLOON_TRACK=$track python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire $resource" >&2
                echo "============================================================" >&2
                exit 1
            fi
        fi
    done

    # If no balloon boards detected, warn but allow (user might be uploading
    # to an ESP32-S3 or other non-balloon board)
    if [ "$found_board" = false ]; then
        echo "GUARD: No balloon boards (F242D/8332) detected. Proceeding without lock check." >&2
    fi
}

# ─── pio interception ────────────────────────────────────────────────────
if [ "$SCRIPT_NAME" = "pio" ]; then
    CMD="${1:-}"
    shift || true

    # Only guard upload commands: `pio run ... -t upload`
    if [ "$CMD" = "run" ] && echo "$*" | grep -q "upload"; then
        check_board_lock
    fi

    # Pass through to real pio
    REAL_PIO="$HOME/.local/bin/pio"
    if [ ! -x "$REAL_PIO" ]; then
        # Fallback: search PATH excluding ourselves
        REAL_PIO="$(which -a pio 2>/dev/null | grep -v "$0" | head -1)"
        if [ -z "$REAL_PIO" ]; then
            echo "ERROR: Real pio not found on system (shim at $0 is active)" >&2
            exit 1
        fi
    fi
    exec "$REAL_PIO" "$CMD" "$@"

# ─── picotool interception ───────────────────────────────────────────────
elif [ "$SCRIPT_NAME" = "picotool" ]; then
    # picotool ALWAYS requires board access — check lock for ALL commands
    check_board_lock

    # Pass through to real picotool
    REAL_PICOTOOL="/usr/bin/picotool"
    if [ ! -x "$REAL_PICOTOOL" ]; then
        REAL_PICOTOOL="$(which -a picotool 2>/dev/null | grep -v "$0" | head -1)"
        if [ -z "$REAL_PICOTOOL" ]; then
            echo "ERROR: Real picotool not found on system (shim at $0 is active)" >&2
            exit 1
        fi
    fi
    exec "$REAL_PICOTOOL" "$@"

# ─── Unknown invocation ──────────────────────────────────────────────────
else
    echo "GUARD: Unknown invocation as '$SCRIPT_NAME'. This script should be" >&2
    echo "       symlinked as 'pio' or 'picotool' in tools/shims/." >&2
    exit 1
fi
