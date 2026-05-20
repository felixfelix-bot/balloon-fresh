#!/usr/bin/env bash

set -e

echo "=== Full Rust ESP32 Firmware Build ==="

# Ensure script is run from repo root
if [ ! -d "antenna-firmware" ]; then
  echo "Error: Run this script from the antenna-tracker repository root."
  exit 1
fi

echo "=== Loading ESP-IDF environment ==="
source "$HOME/esp/esp-idf/export.sh"

echo "=== Loading ESP Rust environment ==="
if [ -f "$HOME/export-esp.sh" ]; then
  source "$HOME/export-esp.sh"
else
  echo "Error: ~/export-esp.sh not found. Run espup install first."
  exit 1
fi

echo "=== Cleaning previous build ==="
make clean

echo "=== Running make build ==="
make build

echo "=== Running cargo build directly (verbose) ==="
cd antenna-firmware
cargo build

echo "=== Build Complete ==="
