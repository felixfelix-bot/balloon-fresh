#!/usr/bin/env bash

set -e

PORT="$1"

if [ -z "$PORT" ]; then
  echo "Usage: $0 /dev/ttyUSB0"
  exit 1
fi

if [ ! -e "$PORT" ]; then
  echo "ERROR: $PORT does not exist"
  exit 1
fi

echo "=== Preparing serial port $PORT ==="

# Stop ModemManager if running (common Ubuntu culprit)
if systemctl is-active --quiet ModemManager 2>/dev/null; then
  echo "Stopping ModemManager..."
  sudo systemctl stop ModemManager
fi

# Kill any processes using the port
if fuser "$PORT" >/dev/null 2>&1; then
  echo "Port is in use. Killing existing processes..."
  sudo fuser -k "$PORT" || true
  sleep 1
fi

echo "Resetting serial settings..."
sudo stty -F "$PORT" sane || true

echo "Configuring 115200 baud..."
sudo stty -F "$PORT" 115200 cs8 -cstopb -parenb -ixon -ixoff -crtscts raw -echo

CURRENT_SPEED=$(stty -F "$PORT" -a | grep -o 'speed [0-9]* baud' || true)

echo "Current serial speed:"
echo "$CURRENT_SPEED"

if [[ "$CURRENT_SPEED" != *"115200"* ]]; then
  echo "ERROR: Failed to set baud rate to 115200."
  exit 1
fi

echo
echo "Opening serial port: $PORT (115200 baud)"
echo "Type commands like:"
echo "  AZ 10"
echo "  EL -20"
echo "Press Ctrl+C to exit"
echo

# Start background reader
cat "$PORT" &
CAT_PID=$!

# Interactive loop
while true; do
  read -r CMD
  if [ -n "$CMD" ]; then
    echo "$CMD" > "$PORT"
  fi
done

# Cleanup (not normally reached)
kill $CAT_PID 2>/dev/null || true
