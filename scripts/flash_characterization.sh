#!/bin/bash
# flash_characterization.sh — Flash characterization firmware to both boards
#
# Usage:
#   ./scripts/flash_characterization.sh          # auto-detect ports
#   ./scripts/flash_characterization.sh --tx /dev/ttyACM0 --rx /dev/ttyACM2
#   ./scripts/flash_characterization.sh --skip-lock  # skip board lock
#
# Flashes:
#   TX board: rp2040-sweep-gps-tx (GPS-synced, fallback to millis())
#   RX board: rp2040-sweep-rx    (millis()-based, 14 phases, unique seq counting)
#
# Board mapping (STABLE — verify with serial number):
#   TX = F242D (serial E663B035977F242D), typically /dev/ttyACM3, HAS GPS
#   RX = 8332  (serial E663B035973B8332), typically /dev/ttyACM0, NO GPS
#
# After flashing, runs a quick serial test to verify both boards boot
# and print PHASE_START lines.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FIRMWARE_DIR="$PROJECT_DIR/firmware/rp2040"
LOCK_SCRIPT="$HOME/repos/balloon-fresh/tools/balloon-board-lock.py"

TX_PORT=""
RX_PORT=""
SKIP_LOCK=false
SKIP_FLASH=false
SKIP_TEST=false

# ANSI colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --tx PORT       TX board serial port (default: auto-detect)"
    echo "  --rx PORT       RX board serial port (default: auto-detect)"
    echo "  --skip-lock     Skip board lock acquisition"
    echo "  --skip-flash    Skip flashing (only run serial test)"
    echo "  --skip-test     Skip serial verification test"
    echo "  -h, --help      Show this help"
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --tx)        TX_PORT="$2"; shift 2 ;;
        --rx)        RX_PORT="$2"; shift 2 ;;
        --skip-lock) SKIP_LOCK=true; shift ;;
        --skip-flash) SKIP_FLASH=true; shift ;;
        --skip-test) SKIP_TEST=true; shift ;;
        -h|--help)   usage ;;
        *)           error "Unknown option: $1"; usage ;;
    esac
done

# ── Auto-detect board ports by serial number ─────────────────────────
# F242D = TX board (serial ...77F242D)
# 8332  = RX board (serial ...73B8332)
detect_ports() {
    info "Detecting board ports..."
    for port in /dev/ttyACM*; do
        [[ -e "$port" ]] || continue
        serial=$(udevadm info -q property -n "$port" 2>/dev/null | grep ID_SERIAL_SHORT | cut -d= -f2)
        model=$(udevadm info -q property -n "$port" 2>/dev/null | grep ID_MODEL= | head -1 | cut -d= -f2)

        # RP2040 Pico boards have "Pico" in model
        if [[ "$model" == *"Pico"* ]] || [[ "$serial" == E663* ]]; then
            if [[ "$serial" == *"F242D" ]] && [[ -z "$TX_PORT" ]]; then
                TX_PORT="$port"
                info "  TX board (F242D): $port (serial=$serial)"
            elif [[ "$serial" == *"8332" ]] && [[ -z "$RX_PORT" ]]; then
                RX_PORT="$port"
                info "  RX board (8332): $port (serial=$serial)"
            fi
        fi
    done

    if [[ -z "$TX_PORT" ]]; then
        warn "TX board not found. Available RP2040 devices:"
        for port in /dev/ttyACM*; do
            [[ -e "$port" ]] || continue
            serial=$(udevadm info -q property -n "$port" 2>/dev/null | grep ID_SERIAL_SHORT | cut -d= -f2)
            echo "    $port serial=$serial"
        done
    fi
    if [[ -z "$RX_PORT" ]]; then
        warn "RX board not found."
    fi
}

# ── Board lock ────────────────────────────────────────────────────────
acquire_lock() {
    if [[ "$SKIP_LOCK" == "true" ]]; then
        warn "Skipping board lock (--skip-lock)"
        return 0
    fi

    if [[ ! -f "$LOCK_SCRIPT" ]]; then
        warn "Lock script not found at $LOCK_SCRIPT — continuing without lock"
        return 0
    fi

    info "Acquiring board locks (track=speed-tests)..."
    BALLOON_TRACK=speed-tests python3 "$LOCK_SCRIPT" acquire both \
        --purpose "Characterization firmware flash" || {
        error "Failed to acquire board lock. Use --skip-lock to override."
        exit 1
    }
}

release_lock() {
    if [[ "$SKIP_LOCK" == "true" ]]; then
        return 0
    fi
    if [[ ! -f "$LOCK_SCRIPT" ]]; then
        return 0
    fi
    info "Releasing board locks..."
    BALLOON_TRACK=speed-tests python3 "$LOCK_SCRIPT" release both 2>/dev/null || true
}

# ── Flash firmware ────────────────────────────────────────────────────
flash_board() {
    local env="$1"
    local port="$2"
    local label="$3"

    if [[ -z "$port" ]]; then
        error "$label port not specified — skipping"
        return 1
    fi

    info "Flashing $label ($env → $port)..."
    cd "$FIRMWARE_DIR"
    if pio run -e "$env" -t upload --upload-port "$port" 2>&1 | tail -5; then
        info "$label flash SUCCESS"
        return 0
    else
        error "$label flash FAILED"
        return 1
    fi
}

# ── Serial verification ──────────────────────────────────────────────
verify_serial() {
    local port="$1"
    local label="$2"
    local timeout_s="${3:-30}"

    if [[ -z "$port" ]]; then
        error "$label port not available — skipping verification"
        return 1
    fi

    info "Verifying $label serial output on $port (${timeout_s}s)..."

    # Configure port
    stty -F "$port" 115200 cs8 -cstopb -parenb raw -echo 2>/dev/null || true

    # Capture output and look for PHASE_START or STARTING
    local output
    output=$(timeout "$timeout_s" cat "$port" 2>/dev/null || true)

    if echo "$output" | grep -q "PHASE_START\|STARTING.*SWEEP\|===.*SWEEP"; then
        info "$label serial OK — found PHASE_START/STARTING"
        echo "$output" | grep -E "PHASE_START|STARTING|GPS|NMEA|NO_GPS" | head -5
        return 0
    else
        warn "$label: no PHASE_START found in ${timeout_s}s"
        echo "$output" | head -10
        return 1
    fi
}

# ── Main ──────────────────────────────────────────────────────────────
main() {
    echo "============================================"
    echo "  LR2021 Characterization Firmware Flash"
    echo "============================================"
    echo ""

    # Detect ports if not specified
    if [[ -z "$TX_PORT" ]] || [[ -z "$RX_PORT" ]]; then
        detect_ports
    fi

    if [[ -z "$TX_PORT" ]] && [[ -z "$RX_PORT" ]]; then
        error "No boards detected. Connect boards and retry."
        exit 1
    fi

    # Acquire lock
    acquire_lock

    # Trap to ensure lock release on exit
    trap release_lock EXIT

    # Flash
    if [[ "$SKIP_FLASH" == "false" ]]; then
        flash_board "rp2040-sweep-gps-tx" "$TX_PORT" "TX (F242D)" || true
        flash_board "rp2040-sweep-rx" "$RX_PORT" "RX (8332)" || true
    else
        warn "Skipping flash (--skip-flash)"
    fi

    echo ""

    # Wait for boards to boot
    info "Waiting 12s for boards to boot..."
    sleep 12

    # Verify serial
    if [[ "$SKIP_TEST" == "false" ]]; then
        echo ""
        verify_serial "$TX_PORT" "TX" 20 || true
        echo ""
        verify_serial "$RX_PORT" "RX" 20 || true
    else
        warn "Skipping serial test (--skip-test)"
    fi

    echo ""
    info "Done. Boards ready for characterization testing."
    echo ""
    echo "Capture data with:"
    echo "  python3 $PROJECT_DIR/tools/capture_sweep.py \\"
    echo "    --port $RX_PORT --distance 1 --los N \\"
    echo "    --duration 300 --output results.csv"
}

main "$@"
