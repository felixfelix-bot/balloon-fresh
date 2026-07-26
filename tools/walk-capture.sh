#!/bin/bash
# walk-capture.sh — RX capture with periodic laptop re-sync
# Usage: ./walk-capture.sh /dev/ttyACM4 600
#   $1 = RX serial port (default: /dev/ttyACM4)
#   $2 = duration seconds (default: 600)
#
# Sends SET_TIME to RX every 10 seconds to eliminate drift.
# Captures all RX output to timestamped log file.

PORT="${1:-/dev/ttyACM4}"
DURATION="${2:-600}"
DATE=$(date +%Y%m%d)
TIME=$(date +%H%M%S)
DATADIR="$HOME/repos/balloon-fresh/data/range-tests/$DATE"
OUTFILE="$DATADIR/walk-test-${TIME}.log"

mkdir -p "$DATADIR"
stty -F "$PORT" 115200 raw -echo 2>/dev/null

echo "=== Walk Test Capture ==="
echo "Port: $PORT"
echo "Duration: ${DURATION}s"
echo "Output: $OUTFILE"
echo "Re-sync interval: 10s"
echo ""

# Background re-sync loop
(
    END=$((SECONDS + DURATION))
    while [ $SECONDS -lt $END ]; do
        NOW=$(date +%s)
        printf "SET_TIME %s\n" "$NOW" > "$PORT"
        sleep 10
    done
) &
RESYNC_PID=$!

# Capture RX output
echo "Capture started at $(date)"
timeout "$DURATION" cat "$PORT" > "$OUTFILE" 2>/dev/null
echo "Capture ended at $(date)"

# Stop re-sync
kill $RESYNC_PID 2>/dev/null
wait $RESYNC_PID 2>/dev/null

# Summary
echo ""
echo "=== Summary ==="
echo "Lines: $(wc -l < "$OUTFILE")"
echo "Phase results: $(grep -c 'PHASE_RESULT' "$OUTFILE")"
echo "CRC errors: $(grep -c 'APP_CRC_FAIL' "$OUTFILE")"
echo "Sync found: $(grep -c 'SYNC_OFFSET' "$OUTFILE")"
echo ""
echo "Decoded phases:"
grep 'PHASE_RESULT' "$OUTFILE" | grep -v 'rx=0' | head -14
