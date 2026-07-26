#!/bin/bash
# Overnight stability monitor — runs walk captures in a loop
# Logs results to data/walk-tests/overnight-stability.log
# No LLM involvement — pure script

cd ~/repos/balloon-fresh
LOG=data/walk-tests/overnight-stability.log
echo "=== Overnight stability monitor started $(date -u) ===" >> "$LOG"

while true; do
    TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%S')
    RESULT=$(python3 tools/walk_capture.py 120 /dev/ttyACM1 2>&1)
    
    # Extract summary line
    DECODED=$(echo "$RESULT" | grep 'Total decoded' | awk '{print $4}')
    PHASES=$(echo "$RESULT" | grep 'Total phases' | awk '{print $4}')
    RSSI=$(echo "$RESULT" | grep 'RSSI range' | head -1)
    RECONNECTS=$(echo "$RESULT" | grep 'Reconnects' | awk '{print $3}')
    
    echo "$TIMESTAMP | phases=$PHASES decoded=$DECODED reconnects=$RECONNECTS $RSSI" >> "$LOG"
    
    # Alert if zero decode
    if [ "$DECODED" = "0" ]; then
        echo "$TIMESTAMP | *** ALERT: ZERO DECODE ***" >> "$LOG"
    fi
    
    # Sleep 60s between captures
    sleep 60
done
