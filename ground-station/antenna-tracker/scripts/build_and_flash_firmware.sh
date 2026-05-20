#!/usr/bin/env bash

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIRMWARE_DIR="$PROJECT_ROOT/antenna-firmware"

echo "=== Building antenna firmware (release) ==="
cd "$FIRMWARE_DIR"
# Use all available CPU cores for Rust and ESP-IDF builds
export CMAKE_BUILD_PARALLEL_LEVEL="$(nproc)"
cargo build --release -j "$(nproc)"

echo "=== Flashing firmware to ESP32 ==="

# Serial port selection priority:
# 1. First CLI argument
# 2. ESP_PORT environment variable
# 3. Default /dev/ttyUSB1

if [ -n "$1" ]; then
  ESP_PORT="$1"
else
  ESP_PORT="${ESP_PORT:-/dev/ttyUSB1}"
fi

echo "Using serial port: $ESP_PORT"

# Requires espflash installed: cargo install espflash
espflash flash \
  --monitor \
  --baud 921600 \
  "$ESP_PORT" \
  target/release/antenna-firmware

echo "=== Done ==="
