#!/usr/bin/env bash
#
# pio-flash.sh — MANDATORY wrapper for pio upload with board lock enforcement.
#
# ALL tracks MUST use this instead of raw `pio run -t upload`.
# Checks that BALLOON_TRACK holds the flock for the target board before flashing.
#
# Usage:
#   BALLOON_TRACK=range-tests ./tools/pio-flash.sh rp2040-sweep-rx --upload-port /dev/ttyACM0
#   BALLOON_TRACK=speed-tests ./tools/pio-flash.sh rp2040-sweep-gps-tx --upload-port /dev/ttyACM3
#
# The script will REFUSE to flash if:
#   1. BALLOON_TRACK is not set
#   2. The target board lock is not held by your track
#
# To acquire a lock first:
#   BALLOON_TRACK=<track> python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire both

set -euo pipefail

LOCK_SCRIPT="$HOME/repos/balloon-fresh/tools/balloon-board-lock.py"

# ─── Check BALLOON_TRACK ─────────────────────────────────────────────────
if [ -z "${BALLOON_TRACK:-}" ]; then
    echo "============================================================" >&2
    echo "REFUSED: BALLOON_TRACK not set." >&2
    echo "" >&2
    echo "Set it first:" >&2
    echo "  export BALLOON_TRACK=range-tests  # or speed-tests" >&2
    echo "============================================================" >&2
    exit 1
fi

# ─── Parse args ──────────────────────────────────────────────────────────
ENV=""
UPLOAD_PORT=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --upload-port)
            UPLOAD_PORT="$2"
            shift 2
            ;;
        --upload-port=*)
            UPLOAD_PORT="${1#*=}"
            shift
            ;;
        *)
            if [ -z "$ENV" ]; then
                ENV="$1"
            fi
            shift
            ;;
    esac
done

if [ -z "$ENV" ]; then
    echo "Usage: BALLOON_TRACK=<track> $0 <env> --upload-port /dev/ttyACMx" >&2
    exit 1
fi

if [ -z "$UPLOAD_PORT" ]; then
    echo "ERROR: --upload-port is required. Specify which board to flash." >&2
    echo "  $0 $ENV --upload-port /dev/ttyACM0   # for RX board (8332)" >&2
    echo "  $0 $ENV --upload-port /dev/ttyACM3   # for TX board (F242D)" >&2
    exit 1
fi

# ─── Resolve port to lock resource ───────────────────────────────────────
RESOURCE=""
SERIAL_SHORT=$(udevadm info -q property -n "$UPLOAD_PORT" 2>/dev/null | grep ID_SERIAL_SHORT= | cut -d= -f2)

if echo "$SERIAL_SHORT" | grep -q "F242D"; then
    RESOURCE="tx"
elif echo "$SERIAL_SHORT" | grep -q "8332"; then
    RESOURCE="rx"
elif [ "$UPLOAD_PORT" = "/dev/ttyACM0" ]; then
    RESOURCE="rx"
elif [ "$UPLOAD_PORT" = "/dev/ttyACM3" ]; then
    RESOURCE="tx"
else
    echo "WARNING: Could not resolve lock resource for $UPLOAD_PORT" >&2
    echo "  Proceeding without lock check (unknown board)" >&2
    exec pio run -e "$ENV" -t upload --upload-port "$UPLOAD_PORT"
fi

# ─── Check lock using balloon-board-lock.py check ────────────────────────
# This returns exit 0 if BALLOON_TRACK holds the lock for $RESOURCE,
# exit 1 otherwise. Much more reliable than the old grep-based approach.
if ! python3 "$LOCK_SCRIPT" check "$RESOURCE" 2>/dev/null; then
    echo "============================================================" >&2
    echo "REFUSED: Board '$RESOURCE' ($UPLOAD_PORT) is not locked by track=$BALLOON_TRACK." >&2
    echo "" >&2
    echo "Acquire the lock first:" >&2
    echo "  BALLOON_TRACK=$BALLOON_TRACK python3 $LOCK_SCRIPT acquire $RESOURCE --purpose 'firmware upload'" >&2
    echo "============================================================" >&2
    exit 1
fi

echo "[LOCK OK] Track '$BALLOON_TRACK' holds '$RESOURCE' lock for $UPLOAD_PORT"

# ─── Flash ───────────────────────────────────────────────────────────────
exec pio run -e "$ENV" -t upload --upload-port "$UPLOAD_PORT"
