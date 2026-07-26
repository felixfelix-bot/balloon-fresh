#!/bin/bash
# GPS time sync service for balloon range tests.
# Reads GPS UTC from TX serial, forwards to RX every ~2 seconds.
# Runs as background daemon. Non-blocking — RX firmware handles SET_TIME
# in its main loop without interrupting radio reception.
#
# Usage: bash time-sync-daemon.sh [tx_port] [rx_port]
# Stop: kill $(cat /tmp/balloon-sync.pid)

TX_PORT=${1:-auto}
RX_PORT=${2:-auto}

# Auto-detect by serial number
if [ "$TX_PORT" = "auto" ]; then
    for p in /dev/ttyACM*; do
        [ -e "$p" ] || continue
        SN=$(udevadm info -q property -n "$p" 2>/dev/null | grep ID_SERIAL_SHORT= | cut -d= -f2)
        case "$SN" in *242D*) TX_PORT="$p" ;; esac
    done
fi
if [ "$RX_PORT" = "auto" ]; then
    for p in /dev/ttyACM*; do
        [ -e "$p" ] || continue
        SN=$(udevadm info -q property -n "$p" 2>/dev/null | grep ID_SERIAL_SHORT= | cut -d= -f2)
        case "$SN" in *8332*) RX_PORT="$p" ;; esac
    done
fi

if [ -z "$TX_PORT" ] || [ -z "$RX_PORT" ]; then
    echo "ERROR: Could not auto-detect boards"
    echo "TX=$TX_PORT RX=$RX_PORT"
    exit 1
fi

echo "$$" > /tmp/balloon-sync.pid
echo "=== TIME SYNC DAEMON ==="
echo "TX: $TX_PORT | RX: $RX_PORT"
echo "PID: $$ (kill with: kill \$(cat /tmp/balloon-sync.pid))"

stty -F "$RX_PORT" 115200 raw -echo
stty -F "$TX_PORT" 115200 raw -echo

SYNC_COUNT=0
while true; do
    # Read from TX, extract full 10-digit GPS UTC
    GPS_UTC=$(timeout 2 head -c 8192 "$TX_PORT" 2>/dev/null | grep -oP 'unix=\K[0-9]{10,}' | tail -1)
    
    if [ -n "$GPS_UTC" ]; then
        printf "SET_TIME %s\n" "$GPS_UTC" > "$RX_PORT"
        SYNC_COUNT=$((SYNC_COUNT + 1))
        [ $((SYNC_COUNT % 30)) -eq 0 ] && echo "[$(date +%H:%M:%S)] sync #$SYNC_COUNT GPS=$GPS_UTC"
    else
        # Fallback to laptop NTP time (Felix confirmed <5s accuracy)
        printf "SET_TIME %s\n" "$(date +%s)" > "$RX_PORT"
        SYNC_COUNT=$((SYNC_COUNT + 1))
        [ $((SYNC_COUNT % 30)) -eq 0 ] && echo "[$(date +%H:%M:%S)] sync #$SYNC_COUNT LAPTOP=$(date +%s) (GPS unavailable)"
    fi
done
