#!/bin/bash
# verify_flash.sh — Post-flash firmware verification
#
# Reads the boot banner from a freshly flashed board and compares
# the git hash against the expected value.
#
# Usage: verify_flash.sh <port> <expected_hash> [board_name]
# Example: verify_flash.sh /dev/ttyACM0 abc123d tx
#
# Exit codes: 0 = match, 1 = mismatch, 2 = no response

set -euo pipefail

PORT="${1:?Usage: verify_flash.sh <port> <expected_hash> [board_name]}"
EXPECTED="${2:?Expected git hash required (7 chars)}"
BOARD="${3:-unknown}"

echo "=== FIRMWARE VERIFICATION ==="
echo "Port:     $PORT"
echo "Expected: $EXPECTED"
echo "Board:    $BOARD"

# Configure serial port
stty -F "$PORT" 115200 cs8 -cstopb -parenb raw -echo 2>/dev/null

# Send FW_QUERY command and read response
echo "FW_QUERY" > "$PORT"
sleep 0.5

# Read up to 3 seconds for response
BANNER=$(timeout 3 cat "$PORT" 2>/dev/null | grep -m1 "FW_BOOT" || true)

if [ -z "$BANNER" ]; then
    echo "RESULT: FAIL — no FW_BOOT banner received"
    echo "The board may not have the firmware integrity system yet."
    exit 2
fi

echo "Banner:   $BANNER"

# Extract hash from banner
ACTUAL=$(echo "$BANNER" | grep -oP 'hash=\K[a-f0-9]+' || echo "")

if [ -z "$ACTUAL" ]; then
    echo "RESULT: FAIL — could not parse hash from banner"
    exit 2
fi

echo "Actual:   $ACTUAL"

if [ "$ACTUAL" = "$EXPECTED" ]; then
    echo "RESULT: MATCH ✓"
    exit 0
else
    echo "RESULT: MISMATCH ✗ (expected $EXPECTED, got $ACTUAL)"
    exit 1
fi
