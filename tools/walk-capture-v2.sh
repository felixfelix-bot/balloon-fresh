#!/bin/bash
# Walk capture v2 — forwards TX GPS UTC to RX every 5s + captures RX log
# This eliminates laptop-vs-GPS time drift entirely.
# Usage: ./walk-capture-v2.sh [duration_seconds] [rx_port] [tx_port]
# Default: 600s walk, RX=/dev/ttyACM1, TX=/dev/ttyACM3

DURATION=${1:-600}
RX_PORT=${2:-/dev/ttyACM1}
TX_PORT=${3:-/dev/ttyACM3}
OUTDIR=~/repos/balloon-fresh/data/range-tests/20260725
mkdir -p "$OUTDIR"
OUTFILE="$OUTDIR/walk-gps-synced-$(date +%H%M%S).log"

echo "=== WALK CAPTURE v2 (GPS time forwarding) ==="
echo "Duration: ${DURATION}s"
echo "RX: $RX_PORT  TX: $TX_PORT"
echo "Output: $OUTFILE"
echo "GPS UTC forwarded from TX to RX every 5s"
echo ""

stty -F "$RX_PORT" 115200 raw -echo
stty -F "$TX_PORT" 115200 raw -echo

# Start RX capture in background
timeout "$DURATION" cat "$RX_PORT" > "$OUTFILE" 2>&1 &
CATPID=$!
echo "Capture PID: $CATPID"

# Push TX GPS UTC to RX every 5s
ELAPSED=0
SYNC_COUNT=0
while [ "$ELAPSED" -lt "$DURATION" ]; do
    # Read GPS UTC from TX serial
    GPS_UTC=$(timeout 2 cat "$TX_PORT" 2>&1 | grep -oP 'unix=\K[0-9]+' | head -1)
    
    if [ -n "$GPS_UTC" ]; then
        printf "SET_TIME %s\n" "$GPS_UTC" > "$RX_PORT"
        SYNC_COUNT=$((SYNC_COUNT + 1))
        echo "[$(date +%H:%M:%S)] GPS_UTC=$GPS_UTC forwarded to RX (sync #$SYNC_COUNT, ${ELAPSED}s)"
    else
        echo "[$(date +%H:%M:%S)] WARNING: no GPS UTC from TX (${ELAPSED}s)"
    fi
    sleep 5
    ELAPSED=$((ELAPSED + 5))
done

wait $CATPID 2>/dev/null

LINES=$(wc -l < "$OUTFILE")
PHASES=$(grep -c "PHASE_RESULT" "$OUTFILE")
PKTS=$(grep -c "PKT\|TIME_DIFF" "$OUTFILE")
echo ""
echo "=== CAPTURE COMPLETE ==="
echo "Sync pushes: $SYNC_COUNT"
echo "Lines: $LINES"
echo "Phases: $PHASES"
echo "File: $OUTFILE"
