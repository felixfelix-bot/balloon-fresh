#!/bin/bash
# pre_flight_check.sh — Pre-flight checklist before walk test
#
# Verifies that TX + RX boards are alive, firmware matches, GPS is locked,
# and packets are actually flowing. Run BEFORE every outdoor walk test.
#
# Usage: ./pre_flight_check.sh <tx_port> <rx_port> [expected_build_id]
#   tx_port           Serial device for TX board (default /dev/ttyACM3)
#   rx_port           Serial device for RX board (default /dev/ttyACM0)
#   expected_build_id Expected git hash from FW_BOOT banner (optional)
#                     If omitted, build-mismatch checks are skipped (INFO only)
#
# Exit 0 = all checks passed
# Exit 1 = one or more checks failed

set -euo pipefail

TX_PORT="${1:-/dev/ttyACM3}"
RX_PORT="${2:-/dev/ttyACM0}"
EXPECTED_BUILD="${3:-}"

PASS=0
FAIL=0

# ── check(): record pass/fail, never exits (despite set -e) ───────────────
check() {
    local name="$1"
    local result="$2"
    if [ "$result" = "0" ]; then
        echo "  [PASS] $name"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] $name"
        FAIL=$((FAIL + 1))
    fi
}

# ── configure_port(): set raw 115200 baud ─────────────────────────────────
configure_port() {
    local port="$1"
    stty -F "$port" 115200 cs8 -cstopb -parenb raw -echo 2>/dev/null || true
}

# ── port_exists(): check device node exists ───────────────────────────────
port_exists() {
    [ -e "$1" ]
}

# ── read_quick(): read up to 2560 bytes (10×256) within timeout ───────────
# Outputs captured text on stdout. Returns 0 if any data read.
read_quick() {
    local port="$1"
    local secs="$2"
    configure_port "$port"
    local data
    data=$(timeout "$secs" dd if="$port" bs=256 count=10 2>/dev/null | strings || true)
    echo "$data"
    [ -n "$data" ]
}

# ── query_fw(): send FW_QUERY, capture boot banner ────────────────────────
# Sets global: FW_RESPONSE (raw FW_BOOT line, or empty)
query_fw() {
    local port="$1"
    configure_port "$port"

    # Send query command
    printf 'FW_QUERY\n' > "$port" 2>/dev/null || true

    # Read response — USB CDC buffers data between close/reopen
    local data
    data=$(timeout 5 dd if="$port" bs=256 count=20 2>/dev/null | strings || true)

    FW_RESPONSE=$(echo "$data" | grep -m1 "FW_BOOT" || true)
}

# ── extract_fw_hash(): pull hash=XXX from FW_BOOT line ────────────────────
extract_fw_hash() {
    echo "$1" | sed -n 's/.*hash=\([a-f0-9]*\).*/\1/p'
}

# ── extract_fw_tag(): pull tag=XXX from FW_BOOT line ──────────────────────
extract_fw_tag() {
    echo "$1" | sed -n 's/.*tag=\([A-Z0-9]*\).*/\1/p'
}

# ── extract_sats(): pull highest sats=N from multi-line text ──────────────
extract_sats() {
    echo "$1" | grep -o 'sats=[0-9]*' | head -20 | \
        sed 's/sats=//' | sort -rn | head -1
}

# ══════════════════════════════════════════════════════════════════════════
#  HEADER
# ══════════════════════════════════════════════════════════════════════════
echo "═══════════════════════════════════════════════════════════════"
echo "  PRE-FLIGHT CHECK — Walk Test Protocol"
echo "═══════════════════════════════════════════════════════════════"
echo "  TX Port:           $TX_PORT"
echo "  RX Port:           $RX_PORT"
if [ -n "$EXPECTED_BUILD" ]; then
    echo "  Expected build:    $EXPECTED_BUILD"
else
    echo "  Expected build:    (not specified — match checks skipped)"
fi
echo ""

# ══════════════════════════════════════════════════════════════════════════
#  CHECK 1: TX board alive
# ══════════════════════════════════════════════════════════════════════════
echo "[1/6] TX board alive?"
rc=0
port_exists "$TX_PORT" || rc=1
if [ "$rc" = "0" ]; then
    TX_DATA=$(read_quick "$TX_PORT" 5) || rc=1
    [ -n "$TX_DATA" ] || rc=1
fi
check "TX board responds on $TX_PORT" "$rc"

# ══════════════════════════════════════════════════════════════════════════
#  CHECK 2: RX board alive
# ══════════════════════════════════════════════════════════════════════════
echo "[2/6] RX board alive?"
rc=0
port_exists "$RX_PORT" || rc=1
if [ "$rc" = "0" ]; then
    RX_DATA=$(read_quick "$RX_PORT" 5) || rc=1
    [ -n "$RX_DATA" ] || rc=1
fi
check "RX board responds on $RX_PORT" "$rc"

# ══════════════════════════════════════════════════════════════════════════
#  CHECK 3: TX firmware build matches expected
# ══════════════════════════════════════════════════════════════════════════
echo "[3/6] TX FW_BUILD match?"
rc=0
if ! port_exists "$TX_PORT"; then
    rc=1
else
    query_fw "$TX_PORT"
    if [ -z "$FW_RESPONSE" ]; then
        echo "       (no FW_BOOT response from TX)"
        rc=1
    else
        TX_HASH=$(extract_fw_hash "$FW_RESPONSE")
        TX_TAG=$(extract_fw_tag "$FW_RESPONSE")
        echo "       TX: $FW_RESPONSE"
        if [ -n "$EXPECTED_BUILD" ]; then
            if [ "$TX_HASH" = "$EXPECTED_BUILD" ]; then
                : # match
            else
                echo "       Expected hash=$EXPECTED_BUILD, got hash=$TX_HASH"
                rc=1
            fi
        else
            echo "       (no expected build specified — INFO only)"
        fi
    fi
fi
check "TX firmware identity" "$rc"

# ══════════════════════════════════════════════════════════════════════════
#  CHECK 4: RX firmware build matches expected
# ══════════════════════════════════════════════════════════════════════════
echo "[4/6] RX FW_BUILD match?"
rc=0
if ! port_exists "$RX_PORT"; then
    rc=1
else
    query_fw "$RX_PORT"
    if [ -z "$FW_RESPONSE" ]; then
        echo "       (no FW_BOOT response from RX)"
        rc=1
    else
        RX_HASH=$(extract_fw_hash "$FW_RESPONSE")
        RX_TAG=$(extract_fw_tag "$FW_RESPONSE")
        echo "       RX: $FW_RESPONSE"
        if [ -n "$EXPECTED_BUILD" ]; then
            if [ "$RX_HASH" = "$EXPECTED_BUILD" ]; then
                : # match
            else
                echo "       Expected hash=$EXPECTED_BUILD, got hash=$RX_HASH"
                rc=1
            fi
        else
            echo "       (no expected build specified — INFO only)"
        fi
    fi
fi
check "RX firmware identity" "$rc"

# ══════════════════════════════════════════════════════════════════════════
#  CHECK 5: TX GPS locked (sats > 4)
# ══════════════════════════════════════════════════════════════════════════
echo "[5/6] TX GPS locked (sats > 4)?"
rc=0
if ! port_exists "$TX_PORT"; then
    rc=1
else
    # Read 8 seconds of TX output — GPS lines appear in burst output
    GPS_DATA=$(read_quick "$TX_PORT" 8) || true
    SATS=$(extract_sats "$GPS_DATA" || true)
    if [ -z "$SATS" ]; then
        echo "       (no 'sats=' found in TX output — GPS may still be acquiring)"
        rc=1
    elif [ "$SATS" -gt 4 ] 2>/dev/null; then
        echo "       sats=$SATS — GPS locked"
    else
        echo "       sats=$SATS — need >4 for lock"
        rc=1
    fi
fi
check "TX GPS lock" "$rc"

# ══════════════════════════════════════════════════════════════════════════
#  CHECK 6: RX receiving TX packets
# ══════════════════════════════════════════════════════════════════════════
echo "[6/6] RX receiving TX packets?"
rc=0
if ! port_exists "$RX_PORT"; then
    rc=1
else
    # Capture 10s of RX output, look for PKT or PHASE_RESULT lines
    RX_CAP=$(read_quick "$RX_PORT" 10) || true
    PKT_COUNT=$(echo "$RX_CAP" | grep -c 'PKT' || true)
    PHASE_COUNT=$(echo "$RX_CAP" | grep -c 'PHASE_RESULT' || true)
    if [ "$PKT_COUNT" -gt 0 ] 2>/dev/null || [ "$PHASE_COUNT" -gt 0 ] 2>/dev/null; then
        echo "       ${PKT_COUNT} PKT lines, ${PHASE_COUNT} PHASE_RESULT lines in 10s"
    else
        echo "       (no PKT or PHASE_RESULT in 10s capture — TX may be out of range/phase)"
        rc=1
    fi
fi
check "RX receiving TX packets" "$rc"

# ══════════════════════════════════════════════════════════════════════════
#  SUMMARY
# ══════════════════════════════════════════════════════════════════════════
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  RESULTS: $PASS passed, $FAIL failed"
echo "═══════════════════════════════════════════════════════════════"

if [ "$FAIL" -gt 0 ]; then
    echo ""
    echo "  ⚠  DO NOT START WALK TEST — fix failures above first."
    exit 1
fi

echo ""
echo "  ✅  ALL CHECKS PASSED — ready to walk."
echo "  Start capture:"
echo "    ./tools/walk_capture.sh"
exit 0
