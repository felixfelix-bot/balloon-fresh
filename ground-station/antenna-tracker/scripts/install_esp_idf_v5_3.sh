#!/usr/bin/env bash

set -e

echo "=== Installing ESP-IDF v5.3 (Rust-compatible) ==="

ESP_DIR="$HOME/esp"
IDF_DIR="$ESP_DIR/esp-idf"

mkdir -p "$ESP_DIR"
cd "$ESP_DIR"

if [ -d "$IDF_DIR" ]; then
  echo "Removing existing esp-idf directory..."
  rm -rf "$IDF_DIR"
fi

echo "Cloning ESP-IDF v5.3..."
git clone --recursive -b v5.3 https://github.com/espressif/esp-idf.git

cd esp-idf

echo "Ensuring all submodules are initialized..."
git submodule update --init --recursive

echo "Installing ESP32 toolchain..."
./install.sh esp32

echo ""
echo "=== ESP-IDF v5.3 Installation Complete ==="
echo "To activate it in your shell, run:"
echo "  source ~/esp/esp-idf/export.sh"
echo ""
echo "Verify with:"
echo "  idf.py --version"
