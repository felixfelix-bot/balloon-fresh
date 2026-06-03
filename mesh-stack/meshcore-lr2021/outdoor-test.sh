#!/usr/bin/env bash
# Outdoor test helper for MeshCore companion node
#
# Usage:
#   ./outdoor-test.sh prep       — sync clock, send advert, ready to disconnect
#   ./outdoor-test.sh check      — reconnect after outdoor test, check results
#   ./outdoor-test.sh monitor    — live monitor while connected (Ctrl+C to stop)
#
# Prerequisites: meshcore-cli installed (pipx install meshcore-cli)
#                 companion_radio_usb flashed on ESP32-C3 SuperMini

set -euo pipefail

PORT="${MESHCLI_PORT:-/dev/ttyACM2}"
BAUD="${MESHCLI_BAUD:-115200}"

find_port() {
    for f in /dev/serial/by-id/usb-esp32*; do
        if [ -e "$f" ]; then
            PORT="$f"
            return
        fi
    done
    for f in /dev/ttyACM*; do
        if [ -e "$f" ]; then
            PORT="$f"
            return
        fi
    done
}

do_prep() {
    echo "=== MeshCore Outdoor Test Prep ==="
    echo "Port: $PORT"
    echo ""

    echo "--- Syncing clock ---"
    meshcli -s "$PORT" -b "$BAUD" clock sync 2>&1

    echo ""
    echo "--- Sending advert ---"
    meshcli -s "$PORT" -b "$BAUD" advert 2>&1

    echo ""
    echo "--- Sending flood advert ---"
    meshcli -s "$PORT" -b "$BAUD" floodadv 2>&1

    echo ""
    echo "--- Current node info ---"
    meshcli -s "$PORT" -b "$BAUD" -j infos 2>&1

    echo ""
    echo "=== READY ==="
    echo "1. Disconnect USB from laptop"
    echo "2. Connect to USB battery pack"
    echo "3. Place outdoors (balcony/window/rooftop) for 30+ minutes"
    echo "4. Bring back, reconnect to laptop"
    echo "5. Run: ./outdoor-test.sh check"
}

do_check() {
    echo "=== MeshCore Outdoor Test Results ==="
    echo "Port: $PORT"
    echo ""

    local ts
    ts=$(date +%Y%m%d_%H%M%S)

    echo "--- Node info ---"
    meshcli -s "$PORT" -b "$BAUD" -j infos 2>&1 | tee "logs/outdoor_${ts}_infos.json"

    echo ""
    echo "--- Contact list (discovered nodes) ---"
    meshcli -s "$PORT" -b "$BAUD" -j contacts 2>&1 | tee "logs/outdoor_${ts}_contacts.json"

    echo ""
    echo "--- Sync messages ---"
    meshcli -s "$PORT" -b "$BAUD" sync_msgs 2>&1 | tee "logs/outdoor_${ts}_msgs.log"

    echo ""
    echo "--- Send advert + check again ---"
    meshcli -s "$PORT" -b "$BAUD" advert 2>&1
    sleep 5
    meshcli -s "$PORT" -b "$BAUD" -j contacts 2>&1 | tee "logs/outdoor_${ts}_contacts2.json"

    echo ""
    echo "=== Results saved to logs/outdoor_${ts}_* ==="
}

do_monitor() {
    echo "=== Live Monitoring (Ctrl+C to stop) ==="
    echo "Port: $PORT"
    echo ""
    timeout "${1:-600}" meshcli -s "$PORT" -b "$BAUD" msgs_subscribe 2>&1 | tee "logs/outdoor_$(date +%Y%m%d_%H%M%S)_monitor.log"
    echo "Monitor ended."
}

mkdir -p logs

if [ $# -lt 1 ]; then
    echo "Usage: $0 {prep|check|monitor [seconds]}"
    echo ""
    echo "  prep      Sync clock, send adverts, prepare for outdoor test"
    echo "  check     Reconnect and check for discovered nodes"
    echo "  monitor   Live message monitor (default 600s)"
    echo ""
    echo "Environment:"
    echo "  MESHCLI_PORT   Serial port (default: /dev/ttyACM2)"
    echo "  MESHCLI_BAUD   Baud rate (default: 115200)"
    exit 1
fi

find_port

case "$1" in
    prep)   do_prep ;;
    check)  do_check ;;
    monitor) do_monitor "${2:-}" ;;
    *)      echo "Unknown command: $1"; exit 1 ;;
esac
