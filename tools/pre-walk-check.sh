#!/bin/bash
# Pre-walk checklist — verifies everything is ready
# Run this BEFORE every walk test.
set -e

echo "=== PRE-WALK CHECK ==="

# 1. Check board symlinks
for dev in /dev/balloon-tx /dev/balloon-rx; do
    if [ ! -e "$dev" ]; then
        echo "FAIL: $dev not found"
        exit 1
    fi
    echo "OK: $dev exists"
done

# 2. Read RX boot banner via FW_QUERY
stty -F /dev/balloon-rx 115200 cs8 -cstopb -parenb raw -echo
echo "FW_QUERY" > /dev/balloon-rx
BANNER=$(timeout 3 cat /dev/balloon-rx | grep -m1 "FW_BOOT" || true)
if [ -z "$BANNER" ]; then
    echo "FAIL: No FW_BOOT response from RX"
    exit 1
fi
echo "OK: RX $BANNER"

# 3. Check TX has GPS lock (read first few lines from TX)
stty -F /dev/balloon-tx 115200 cs8 -cstopb -parenb raw -echo
TXOUT=$(timeout 5 cat /dev/balloon-tx | head -5 || true)
echo "TX output: $TXOUT"
# Look for sats= and fix= in output

# 4. Create data directory
DATE=$(date -u +%Y-%m-%d)
DATADIR="data/walk-$DATE"
mkdir -p "$DATADIR/plots"
echo "OK: Data directory $DATADIR"

# 5. Copy metadata template
if [ -f "data/metadata-template.json" ]; then
    cp data/metadata-template.json "$DATADIR/metadata.json"
    # Fill in date
    sed -i "s/\"date\": \"\"/\"date\": \"$DATE\"/" "$DATADIR/metadata.json"
    echo "OK: metadata.json created from template"
fi

# 6. Send SET_TIME to both boards
echo "SET_TIME $(date +%s)" > /dev/balloon-rx
echo "SET_TIME $(date +%s)" > /dev/balloon-tx
echo "OK: Time sync sent to both boards"

echo ""
echo "=== READY TO WALK ==="
echo "Start capture:"
echo "  python3 scripts/sweep_capture.py --port /dev/balloon-rx --distance 0 --env outdoor --cycles 999 --out $DATADIR/capture-rx.txt"
echo "Start phone GPS recording now."
