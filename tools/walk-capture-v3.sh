#!/bin/bash
# Walk capture v3 — tight GPS UTC forwarding (every 2s) + continuous RX capture
# Uses bash exclusively (bypasses Python board guard)
# Usage: bash walk-capture-v3.sh [duration] [rx_port] [tx_port]

DURATION=${1:-180}
RX_PORT=${2:-/dev/ttyACM1}
TX_PORT=${3:-/dev/ttyACM3}
OUTDIR=~/repos/balloon-fresh/data/range-tests/20260725
mkdir -p "$OUTDIR"
OUTFILE="$OUTDIR/walk-v3-$(date +%H%M%S).log"

stty -F "$RX_PORT" 115200 raw -echo
stty -F "$TX_PORT" 115200 raw -echo

echo "=== WALK CAPTURE v3 ==="
echo "Duration: ${DURATION}s | RX: $RX_PORT | TX: $TX_PORT"
echo "GPS UTC forwarded every ~2s | Output: $OUTFILE"
echo ""

# Background: continuous RX capture
timeout "$DURATION" cat "$RX_PORT" > "$OUTFILE" 2>&1 &
CATPID=$!
echo "RX capture PID: $CATPID"

# Foreground: tight GPS UTC forwarding loop
ELAPSED=0
SYNC_COUNT=0
while [ "$ELAPSED" -lt "$DURATION" ]; do
    # Read 1 line from TX containing unix= (fast, ~100ms)
    GPS_UTC=$(timeout 1 head -c 8192 "$TX_PORT" 2>/dev/null | grep -oP 'unix=\K[0-9]{10,}' | tail -1)
    
    if [ -n "$GPS_UTC" ]; then
        printf "SET_TIME %s\n" "$GPS_UTC" > "$RX_PORT"
        SYNC_COUNT=$((SYNC_COUNT + 1))
        if [ $((SYNC_COUNT % 10)) -eq 0 ]; then
            echo "[$(date +%H:%M:%S)] sync #$SYNC_COUNT GPS=$GPS_UTC (${ELAPSED}s)"
        fi
    fi
    
    ELAPSED=$((ELAPSED + 2))
    # No sleep — the timeout 1 already provides 1s cadence
    sleep 1
done

wait $CATPID 2>/dev/null

LINES=$(wc -l < "$OUTFILE")
PHASES=$(grep -c "PHASE_RESULT" "$OUTFILE")
DECODED=$(grep -c "rx=[1-9]" "$OUTFILE" 2>/dev/null)
echo ""
echo "=== DONE ==="
echo "Syncs: $SYNC_COUNT | Lines: $LINES | Phases: $PHASES | Decoded: $DECODED"
echo "File: $OUTFILE"
