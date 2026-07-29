#!/usr/bin/env bash
#
# pio-flash.sh — MANDATORY wrapper for pio/idf upload with board lock enforcement.
#
# ALL tracks MUST use this instead of raw `pio run -t upload` or `idf.py flash`.
# Checks that BALLOON_TRACK holds the flock for the target board before flashing.
#
# Usage:
#   BALLOON_TRACK=range-tests ./tools/pio-flash.sh rp2040-sweep-rx --upload-port /dev/ttyACM3
#   BALLOON_TRACK=speed-tests ./tools/pio-flash.sh rp2040-sweep-gps-tx --upload-port /dev/ttyACM3
#   BALLOON_TRACK=c3-tests ./tools/pio-flash.sh tracker --upload-port /dev/ttyACM0 --idf
#   BALLOON_TRACK=c3-tests ./tools/pio-flash.sh tracker --upload-port /dev/ttyACM1 --idf
#
# The script will REFUSE to flash if:
#   1. BALLOON_TRACK is not set
#   2. The target board lock is not held by your track
#   3. The port cannot be resolved to a known board (ADR-025: no unknown-board bypass)
#
# To acquire a lock first:
#   BALLOON_TRACK=<track> python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire c3-a
#   BALLOON_TRACK=<track> python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire tx
#
# Flags:
#   --upload-port PATH   Serial device (required)
#   --idf                Use `idf.py -p <port> flash` instead of `pio run -t upload`
#   --dry-run            Print the command that would run, but don't execute it

set -euo pipefail

# Overridable for testing; defaults to the canonical lock script.
LOCK_SCRIPT="${PIO_FLASH_LOCK_SCRIPT:-$HOME/repos/balloon-fresh/tools/balloon-board-lock.py}"

# ─── Check BALLOON_TRACK ─────────────────────────────────────────────────
if [ -z "${BALLOON_TRACK:-}" ]; then
    echo "============================================================" >&2
    echo "REFUSED: BALLOON_TRACK not set." >&2
    echo "" >&2
    echo "Set it first:" >&2
    echo "  export BALLOON_TRACK=range-tests  # or speed-tests, c3-tests" >&2
    echo "============================================================" >&2
    exit 1
fi

# ─── Parse args ──────────────────────────────────────────────────────────
ENV=""
UPLOAD_PORT=""
IDF_MODE=0
DRY_RUN=0

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
        --idf)
            IDF_MODE=1
            shift
            ;;
        --dry-run)
            DRY_RUN=1
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
    echo "Usage: BALLOON_TRACK=<track> $0 <env> --upload-port /dev/ttyACMx [--idf] [--dry-run]" >&2
    exit 1
fi

if [ -z "$UPLOAD_PORT" ]; then
    echo "ERROR: --upload-port is required. Specify which board to flash." >&2
    echo "  $0 $ENV --upload-port /dev/ttyACM0 --idf   # c3-a (ESP32-C3, MAC ...96:DC)" >&2
    echo "  $0 $ENV --upload-port /dev/ttyACM1 --idf   # c3-b (ESP32-C3, MAC ...C6:98)" >&2
    echo "  $0 $ENV --upload-port /dev/ttyACM3         # tx   (RP2040, serial F242D)" >&2
    exit 1
fi

# ─── Resolve port to lock resource ───────────────────────────────────────
# Two mechanisms:
#   1. udevadm ID_SERIAL_SHORT — works for RP2040 (serial F242D/8332) AND
#      ESP32-C3 (USB CDC serial = MAC, e.g. B0:A6:04:00:96:DC)
#   2. Fallback port-number map (only when udev can't identify the device)
#
# RP2040 serials:   tx=F242D, rx=8332
# ESP32-C3 MACs:    c3-a=...96:DC (/dev/ttyACM0), c3-b=...C6:98 (/dev/ttyACM1)
RESOURCE=""
SERIAL_SHORT="$(udevadm info -q property -n "$UPLOAD_PORT" 2>/dev/null | grep ID_SERIAL_SHORT= | cut -d= -f2 || true)"

if echo "$SERIAL_SHORT" | grep -q "F242D"; then
    RESOURCE="tx"
elif echo "$SERIAL_SHORT" | grep -q "8332"; then
    RESOURCE="rx"
# ESP32-C3 MAC-based identification (ADR-025). Uppercase for case-insensitive match.
elif echo "${SERIAL_SHORT^^}" | grep -q "96:DC"; then
    RESOURCE="c3-a"
elif echo "${SERIAL_SHORT^^}" | grep -q "C6:98"; then
    RESOURCE="c3-b"
fi

# Fallback: port-number map when udev can't resolve the device identity.
# NOTE: ttyACM0 was previously mapped to "rx" (RP2040). Per ADR-025 it is now
# c3-a (ESP32-C3). RP2040 boards should still resolve via serial (F242D/8332).
if [ -z "$RESOURCE" ]; then
    case "$UPLOAD_PORT" in
        /dev/ttyACM0) RESOURCE="c3-a" ;;
        /dev/ttyACM1) RESOURCE="c3-b" ;;
        /dev/ttyACM3) RESOURCE="tx" ;;
        *)
            echo "============================================================" >&2
            echo "REFUSED: Cannot resolve board for $UPLOAD_PORT" >&2
            echo "         (no udev serial, no port-number match)." >&2
            echo "  ADR-025 requires ALL hardware access to be locked." >&2
            echo "  Known ports:" >&2
            echo "    /dev/ttyACM0 -> c3-a   /dev/ttyACM1 -> c3-b   /dev/ttyACM3 -> tx" >&2
            echo "============================================================" >&2
            exit 1
            ;;
    esac
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
if [ "$IDF_MODE" = "1" ]; then
    CMD=(idf.py -p "$UPLOAD_PORT" flash)
else
    CMD=(pio run -e "$ENV" -t upload --upload-port "$UPLOAD_PORT")
fi

if [ "$DRY_RUN" = "1" ]; then
    echo "[DRY-RUN] Would execute: ${CMD[*]}"
    exit 0
fi

exec "${CMD[@]}"
