#!/bin/bash
# Bench test: flash tracker + ground station, verify TX→RX
# Uses the router mutex from physical-router-test-automation
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCK_DIR="${LOCK_DIR:-/home/c03rad0r/physical-router-test-automation/locks}"
LOCK_FILE="$LOCK_DIR/balloon-bench.lock"

TRACKER_PORT="${TRACKER_PORT:-/dev/ttyACM0}"
GS_PORT="${GS_PORT:-/dev/ttyACM1}"
IDF_PATH="${IDF_PATH:-$HOME/esp/esp-idf}"

FIRMWARE_DIR="$SCRIPT_DIR/../tracker/firmware"
GS_DIR="$SCRIPT_DIR/../tracker/ground-station/receiver"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[FAIL]${NC} $*"; }

acquire_lock() {
    mkdir -p "$LOCK_DIR"
    if [ -f "$LOCK_FILE" ]; then
        existing=$(cat "$LOCK_FILE" 2>/dev/null)
        error "Boards locked by another session:"
        error "$existing"
        error "Use LOCK_DIR=/tmp balloon-bench-test.sh or remove $LOCK_FILE"
        exit 1
    fi
    cat > "$LOCK_FILE" <<EOF
locked: true
session: $(whoami)@$(hostname)
timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)
phase: balloon-bench-test
tracker_port: $TRACKER_PORT
gs_port: $GS_PORT
EOF
    info "Lock acquired: $LOCK_FILE"
}

release_lock() {
    rm -f "$LOCK_FILE"
    info "Lock released"
}

cleanup() {
    release_lock
    [ -n "$GS_MONITOR_PID" ] && kill $GS_MONITOR_PID 2>/dev/null
    [ -n "$TRACKER_MONITOR_PID" ] && kill $TRACKER_MONITOR_PID 2>/dev/null
}
trap cleanup EXIT

check_ports() {
    info "Checking serial ports..."
    if [ ! -e "$TRACKER_PORT" ]; then
        error "Tracker port $TRACKER_PORT not found"
        ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || true
        exit 1
    fi
    if [ ! -e "$GS_PORT" ]; then
        error "Ground station port $GS_PORT not found"
        ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || true
        exit 1
    fi
    info "Tracker: $TRACKER_PORT"
    info "Ground station: $GS_PORT"
}

build_firmware() {
    info "Building tracker firmware..."
    source "$IDF_PATH/export.sh" 2>/dev/null
    cd "$FIRMWARE_DIR"
    idf.py build 2>&1 | tail -3

    info "Building ground station firmware..."
    cd "$GS_DIR"
    idf.py build 2>&1 | tail -3
}

flash_boards() {
    info "Flashing tracker to $TRACKER_PORT..."
    cd "$FIRMWARE_DIR"
    idf.py -p "$TRACKER_PORT" flash 2>&1 | tail -5

    info "Flashing ground station to $GS_PORT..."
    cd "$GS_DIR"
    idf.py -p "$GS_PORT" flash 2>&1 | tail -5
}

monitor_gs() {
    info "Starting ground station monitor on $GS_PORT..."
    python3 -c "
import serial, sys, time, json
ser = serial.Serial('$GS_PORT', 115200, timeout=1)
start = time.time()
while time.time() - start < 120:
    line = ser.readline().decode('utf-8', errors='replace').strip()
    if not line:
        continue
    print(line)
    sys.stdout.flush()
    if 'telemetry' in line and 'type' in line:
        try:
            j = json.loads(line)
            if j.get('type') == 'telemetry':
                print(f'\n=== BENCH TEST PASSED ===')
                print(f'  Seq: {j.get(\"seq\")}')
                print(f'  RSSI: {j.get(\"rssi\")} dBm')
                print(f'  SNR: {j.get(\"snr\")} dB')
                print(f'  Voltage: {j.get(\"voltage_mv\")} mV')
                sys.exit(0)
        except:
            pass
print('\n=== BENCH TEST FAILED: No telemetry received in 120s ===')
sys.exit(1)
" &
    GS_MONITOR_PID=$!
}

wait_for_result() {
    info "Waiting for telemetry (up to 120s)..."
    wait $GS_MONITOR_PID
    result=$?
    if [ $result -eq 0 ]; then
        info "BENCH TEST PASSED"
        exit 0
    else
        error "BENCH TEST FAILED"
        exit 1
    fi
}

# Main
acquire_lock
check_ports

if [ "$1" = "--flash-only" ]; then
    flash_boards
    exit 0
fi

if [ "$1" = "--build-only" ]; then
    build_firmware
    exit 0
fi

build_firmware
flash_boards
monitor_gs
wait_for_result
