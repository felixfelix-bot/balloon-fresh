#!/bin/bash
# Retry C3 board acquisition until FIPS releases them.
# When acquired, flash + test SPI read fix (19f6443).
set -euo pipefail

export BALLOON_TRACK=balloon-mesh-wiring
LOCK_SCRIPT=~/repos/balloon-fresh/tools/balloon-board-lock.py
REPO=~/repos/balloon-fresh

ATTEMPTS=0
MAX_ATTEMPTS=80  # ~2h at 90s intervals

while [ $ATTEMPTS -lt $MAX_ATTEMPTS ]; do
    ATTEMPTS=$((ATTEMPTS + 1))
    
    # Check if boards are free
    STATUS=$(python3 "$LOCK_SCRIPT" status 2>&1)
    
    if echo "$STATUS" | grep -q "C3-A: FREE" && echo "$STATUS" | grep -q "C3-B: FREE"; then
        echo "[$(date -u +%H:%M:%S)] Boards FREE! Attempting acquire (attempt $ATTEMPTS)..."
        
        # Try to acquire both boards
        if python3 "$LOCK_SCRIPT" acquire both --purpose "SPI read fix test (19f6443)" --timeout 60 2>&1; then
            echo "[$(date -u +%H:%M:%S)] ACQUIRED! Starting flash + test..."
            
            # Flash + test
            source ~/esp/esp-idf/export.sh 2>/dev/null
            cd "$REPO"
            
            # Build the tracker firmware with SPI fix
            echo "Building tracker firmware with SPI read fix..."
            cd tracker/firmware
            idf.py build 2>&1 | tail -5
            
            # Flash c3-a
            echo "Flashing C3-A (/dev/ttyACM0)..."
            idf.py -p /dev/ttyACM0 flash 2>&1 | tail -10
            
            echo "SUCCESS: Flash complete. Monitor for SPI reads..."
            idf.py -p /dev/ttyACM0 monitor 2>&1 | head -50
            
            echo "DONE: SPI read fix tested."
            exit 0
        else
            echo "[$(date -u +%H:%M:%S)] Acquire failed (race condition). Retrying..."
        fi
    else
        # Still locked — show who holds them
        HOLDER=$(echo "$STATUS" | grep "C3-A:" | head -1)
        echo "[$(date -u +%H:%M:%S)] Attempt $ATTEMPTS/$MAX_ATTEMPTS — still locked: $HOLDER"
    fi
    
    sleep 90
done

echo "[$(date -u +%H:%M:%S)] Gave up after $MAX_ATTEMPTS attempts (~2h). Boards never freed."
exit 1
