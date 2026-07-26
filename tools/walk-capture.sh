#!/bin/bash
# Walk capture script — pushes SET_TIME to RX every 5s + captures full log
# Usage: ./walk-capture.sh [duration_seconds]
# Default: 600s (10 min walk). Use 1800 for 30 min.

DURATION=${1:-600}
PORT=${2:-/dev/ttyACM1}
OUTDIR=~/repos/balloon-fresh/data/range-tests/20260725
mkdir -p "$OUTDIR"
OUTFILE="$OUTDIR/walk-capture-$(date +%H%M%S).log"

echo "=== WALK CAPTURE ==="
echo "Duration: ${DURATION}s"
echo "Port: $PORT"
echo "Output: $OUTFILE"
echo "SET_TIME pushed every 5s"
echo ""

stty -F "$PORT" 115200 raw -echo

# Start capture in background
timeout "$DURATION" cat "$PORT" > "$OUTFILE" 2>&1 &
CATPID=$!
echo "Capture PID: $CATPID"

# Push SET_TIME every 5s for entire duration
ELAPSED=0
while [ "$ELAPSED" -lt "$DURATION" ]; do
    UTC=$(date +%s)
    printf "SET_TIME %s\n" "$UTC" > "$PORT"
    echo "[$(date +%H:%M:%S)] SET_TIME $UTC pushed (${ELAPSED}s elapsed)"
    sleep 5
    ELAPSED=$((ELAPSED + 5))
done

# Wait for capture to finish
wait $CATPID 2>/dev/null

LINES=$(wc -l < "$OUTFILE")
PHASES=$(grep -c "PHASE_RESULT" "$OUTFILE")
PKTS=$(grep -c "PKT\|TIME_DIFF" "$OUTFILE")
echo ""
echo "=== CAPTURE COMPLETE ==="
echo "Lines: $LINES"
echo "Phases: $PHASES"
echo "Packet/TIME_DIFF lines: $PKTS"
echo "File: $OUTFILE"
