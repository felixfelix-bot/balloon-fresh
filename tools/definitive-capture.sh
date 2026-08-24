#!/bin/bash
# Definitive walk capture: sync + capture in ONE script.
# Background: reads TX GPS UTC, pushes SET_TIME to RX.
# Foreground: captures ALL RX output to log file.
# Auto-detects board serial numbers.
#
# Usage: bash definitive-capture.sh [duration_seconds]

DURATION=${1:-170}
OUTDIR=~/repos/balloon-fresh/data/range-tests/20260725
mkdir -p "$OUTDIR"
OUTFILE="$OUTDIR/definitive-$(date +%H%M%S).log"

# Auto-detect ports
TX_PORT=""; RX_PORT=""
for p in /dev/ttyACM0 /dev/ttyACM1 /dev/ttyACM2 /dev/ttyACM3; do
    [ -e "$p" ] || continue
    SN=$(udevadm info -q property -n "$p" 2>/dev/null | grep ID_SERIAL_SHORT= | cut -d= -f2)
    case "$SN" in *242D*) TX_PORT="$p" ;; *8332*) RX_PORT="$p" ;; esac
done

if [ -z "$TX_PORT" ] || [ -z "$RX_PORT" ]; then
    echo "ERROR: Cannot find boards. TX=$TX_PORT RX=$RX_PORT"
    exit 1
fi

echo "=== DEFINITIVE CAPTURE ==="
echo "TX: $TX_PORT | RX: $RX_PORT | Duration: ${DURATION}s"
echo "Output: $OUTFILE"
echo ""

stty -F "$RX_PORT" 115200 raw -echo
stty -F "$TX_PORT" 115200 raw -echo

# Background: sync loop — reads TX, writes SET_TIME to RX
(
    SYNC_COUNT=0
    END=$((SECONDS + DURATION))
    while [ $SECONDS -lt $END ]; do
        GPS_UTC=$(timeout 2 head -c 8192 "$TX_PORT" 2>/dev/null | grep -oP 'unix=\K[0-9]{10,}' | tail -1)
        if [ -n "$GPS_UTC" ]; then
            printf "SET_TIME %s\n" "$GPS_UTC" > "$RX_PORT"
            SYNC_COUNT=$((SYNC_COUNT + 1))
            [ $((SYNC_COUNT % 15)) -eq 0 ] && echo "  [sync #$SYNC_COUNT GPS=$GPS_UTC]" >&2
        fi
    done
    echo "  [sync done: $SYNC_COUNT pushes]" >&2
) &
SYNC_PID=$!

# Foreground: capture RX output
timeout "$DURATION" cat "$RX_PORT" > "$OUTFILE" 2>&1

wait $SYNC_PID 2>/dev/null

LINES=$(wc -l < "$OUTFILE")
PHASES=$(grep -c "PHASE_RESULT" "$OUTFILE")
DECODED=$(grep -c "rx=[1-9]" "$OUTFILE" 2>/dev/null || echo 0)

echo ""
echo "=== RESULTS ==="
echo "Lines: $LINES | Phases: $PHASES | Decoded: $DECODED"
echo "File: $OUTFILE"

# Show decoded phases summary
echo ""
echo "=== DECODED PHASES ==="
grep "PHASE_RESULT" "$OUTFILE" | awk '{
    rx=""; per=""; rssi=""; psize=""
    for(i=1;i<=NF;i++) { split($i,a,"=")
        if(a[1]=="rx") rx=a[2]; if(a[1]=="per") per=a[2]
        if(a[1]=="rssi_avg") rssi=a[2]; if(a[1]=="pktSize") psize=a[2]
    }
    if(rx+0 > 0) printf "OK  P%-3s %-24s %3sB rx=%-4s PER=%-7s RSSI=%s\n", $2, $3, psize, rx, per"%", rssi
}' | sort -t'P' -k2 -n | uniq

echo ""
echo "=== FAILED PHASES ==="
grep "PHASE_RESULT" "$OUTFILE" | awk '{
    rx=""; for(i=1;i<=NF;i++) { split($i,a,"="); if(a[1]=="rx") rx=a[2] }
    if(rx+0 == 0 && $3 !~ /SKIP/) printf "XX  P%-3s %-24s\n", $2, $3
}' | sort -t'P' -k2 -n | uniq | head -30
