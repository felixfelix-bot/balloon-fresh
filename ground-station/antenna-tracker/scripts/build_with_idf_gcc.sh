#!/usr/bin/env bash

set -e

echo "=== Building with ESP-IDF GCC (13.2.0) ==="

# Ensure run from repo root
if [ ! -d "antenna-firmware" ]; then
  echo "Error: Run this script from the antenna-tracker repository root."
  exit 1
fi

echo "=== Loading ESP-IDF environment ==="
source "$HOME/esp/esp-idf/export.sh"

echo "=== Loading ESP Rust environment ==="
source "$HOME/export-esp.sh"

echo "=== Forcing ESP-IDF GCC toolchain ==="
export IDF_GCC_DIR="$HOME/.espressif/tools/xtensa-esp-elf/esp-13.2.0_20240530/xtensa-esp-elf/bin"

export CC="$IDF_GCC_DIR/xtensa-esp32-elf-gcc"
export CXX="$IDF_GCC_DIR/xtensa-esp32-elf-g++"

echo "Using CC: $CC"
echo "Using CXX: $CXX"

echo "=== Cleaning previous build ==="
make clean

echo "=== Building firmware ==="
make build

echo "=== Build finished ==="
