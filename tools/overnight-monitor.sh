#!/bin/bash
# Overnight stability monitor — runs walk captures in a loop
# Uses make flash-tx/rx which handle board locks via pio-flash.sh
# Logs results to data/walk-tests/overnight-stability.log

cd ~/repos/balloon-fresh
LOG=data/walk-tests/overnight-stability.log
echo "=== Overnight stability monitor v2 started $(date -u) ===" >> "$LOG"

CYCLE=0
while true; do
    CYCLE=$((CYCLE + 1))
    TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%S')
    
    # Every 5 cycles, re-flash both boards to ensure fresh firmware
    if [ $((CYCLE % 5)) -eq 1 ]; then
        echo "$TIMESTAMP | Re-flashing both boards..." >> "$LOG"
        BALLOON_TRACK=overnight make flash-tx >> /dev/null 2>&1
        BALLOON_TRACK=overnight make flash-rx >> /dev/null 2>&1
        sleep 15  # wait for boot
    fi
    
    # Run 120s capture
    RESULT=$(python3 tools/walk_capture.py 120 /dev/ttyACM1 2>&1)
    
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
