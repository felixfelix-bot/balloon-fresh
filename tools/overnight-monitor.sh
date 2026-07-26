#!/bin/bash
# Overnight stability monitor v3 — auto-detect RX board, NO re-flashing
# Re-flashing causes port re-enumeration which breaks capture.
# Logs results to data/walk-tests/overnight-stability.log

cd ~/repos/balloon-fresh
LOG=data/walk-tests/overnight-stability.log
RX_SERIAL="E663B035973B8332"
echo "=== Overnight stability monitor v3 started $(date -u) ===" >> "$LOG"

find_rx_port() {
    for p in /dev/ttyACM*; do
        [ -e "$p" ] || continue
        SN=$(udevadm info -q property -n "$p" 2>/dev/null | grep ID_SERIAL_SHORT | cut -d= -f2)
        if [ "$SN" = "$RX_SERIAL" ]; then
            echo "$p"
            return
        fi
    done
}

CYCLE=0
while true; do
    CYCLE=$((CYCLE + 1))
    TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%S')
    
    RX_PORT=$(find_rx_port)
    if [ -z "$RX_PORT" ]; then
        echo "$TIMESTAMP | cycle=$CYCLE RX BOARD NOT FOUND" >> "$LOG"
        sleep 30
        continue
    fi
    
    # Run 120s capture
    RESULT=$(python3 tools/walk_capture.py 120 "$RX_PORT" 2>&1)
    
    DECODED=$(echo "$RESULT" | grep 'Total decoded' | awk '{print $4}')
    PHASES=$(echo "$RESULT" | grep 'Total phases' | awk '{print $4}')
    RSSI=$(echo "$RESULT" | grep 'RSSI range' | head -1)
    RECONNECTS=$(echo "$RESULT" | grep 'Reconnects' | awk '{print $3}')
    
    echo "$TIMESTAMP | cycle=$CYCLE phases=$PHASES decoded=$DECODED reconnects=$RECONNECTS $RSSI" >> "$LOG"
    
    if [ "$DECODED" = "0" ]; then
        echo "$TIMESTAMP | *** ALERT: ZERO DECODE ***" >> "$LOG"
        # Force re-flash on next cycle
        CYCLE=$((CYCLE - 1))  # trigger re-flash condition
    fi
    
    sleep 30
done
