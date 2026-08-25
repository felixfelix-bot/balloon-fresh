#!/usr/bin/env bash
# ============================================================
# create-range-test-zip.sh
#
# Build a minimal ZIP package for a range-test operator who just
# wants to flash + run TX/RX.  Publishable as a GitHub release asset.
#
# Usage:
#   cd firmware/e80-stm32-bench
#   bash tools/create-range-test-zip.sh
#
# Output:
#   ../e80-range-test-<sha7>.zip  (next to the e80-stm32-bench/ dir)
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FW_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$FW_DIR/../.." && pwd)"

SHA7="$(git -C "$REPO_ROOT" rev-parse --short=7 HEAD 2>/dev/null || echo unknown)"
STAGING="$(mktemp -d)/e80-range-test"
ZIP_NAME="e80-range-test-${SHA7}.zip"
ZIP_OUT="$FW_DIR/${ZIP_NAME}"

echo "=== E80 Range Test ZIP Builder ==="
echo "  Repo SHA7 : $SHA7"
echo "  Staging   : $STAGING"
echo "  Output    : $ZIP_OUT"
echo ""

mkdir -p "$STAGING"

# --- Top-level files -------------------------------------------------------
cp "$FW_DIR/Makefile"          "$STAGING/Makefile"
cp "$FW_DIR/CMakeLists.txt"    "$STAGING/CMakeLists.txt"

# --- tools/ (only what's needed for range tests) ---------------------------
mkdir -p "$STAGING/tools"
for f in \
    e80_bench_ctl.py \
    e80_detect.py \
    gps_stitch.py \
    merge_csvs.py \
    countdown.py
do
    cp "$FW_DIR/tools/$f" "$STAGING/tools/$f"
done

# --- cmake/ (toolchain files) ----------------------------------------------
mkdir -p "$STAGING/cmake"
cp "$FW_DIR/cmake/"* "$STAGING/cmake/"

# --- ld/ (linker scripts, needed by CMakeLists.txt) -----------------------
mkdir -p "$STAGING/ld"
cp "$FW_DIR/ld/"* "$STAGING/ld/"

# --- src/ (firmware source) ------------------------------------------------
cp -r "$FW_DIR/src" "$STAGING/src"
find "$STAGING/src" -name '*.o' -delete 2>/dev/null || true

# --- third_party/ (STM32 HAL + LR2021 driver) -----------------------------
cp -r "$FW_DIR/third_party" "$STAGING/third_party"

# --- configs/ (only outdoor-10.json preset) -------------------------------
mkdir -p "$STAGING/configs"
cp "$REPO_ROOT/configs/outdoor-10.json" "$STAGING/configs/"

# --- docs/ (only RANGE-TEST-GUIDE.md) -------------------------------------
mkdir -p "$STAGING/docs"
cp "$FW_DIR/docs/RANGE-TEST-GUIDE.md" "$STAGING/docs/"

# --- README-RANGE-TEST.txt (quick start) -----------------------------------
cat > "$STAGING/README-RANGE-TEST.txt" << 'QUICKSTART'
=================================================================
 E80 RANGE TEST — MINIMAL PACKAGE
=================================================================

This zip contains everything needed to flash an E80 board and run
a distributed LoRa / FLRC range test.

PREREQUISITES
------------
  Linux:  sudo apt install cmake arm-none-eabi-gcc openocd python3
  macOS:  brew install cmake gcc-arm-embedded openocd python3
  Windows: Install STM32CubeIDE or arm-none-eabi toolchain + openocd

  Python deps: pip install pyserial

QUICK START
-----------
  1. Unzip this archive.
  2. cd e80-range-test
  3. Plug in BOTH USB cables to your E80 board:
       - CH340 data port (serial)
       - CMSIS-DAP / Pico SWD probe (debug/flash)
  4. Flash the firmware (first time only):
       make flash
  5. TX operator runs:
       make tx
  6. RX operator runs (within 4 minutes):
       make rx
  7. After both finish, merge logs:
       make range-merge RX=rx-log.csv TX=tx-log.csv

WHAT'S INSIDE
-------------
  Makefile              - Convenience targets (flash, tx, rx, merge)
  CMakeLists.txt        - Firmware build config
  cmake/                - Toolchain file (arm-none-eabi)
  ld/                   - Linker scripts (STM32F103C8)
  src/                  - Firmware source code
  third_party/          - STM32 HAL + Semtech LR2021 driver
  tools/                - Python utilities (comms, GPS, CSV merge)
  configs/outdoor-10.json - Default range test config preset
  docs/RANGE-TEST-GUIDE.md - Full operator guide (read this!)

For the full guide, read:  docs/RANGE-TEST-GUIDE.md
=================================================================
QUICKSTART

# --- Build the zip ---------------------------------------------------------
echo "Packing zip..."
cd "$STAGING/.."
zip -r "$ZIP_OUT" e80-range-test \
    -x '*/__pycache__/*' \
    -x '*.o' \
    -x '*.pyc'

echo ""
echo "=== DONE ==="
echo "  File  : $ZIP_OUT"
echo "  Size  : $(du -h "$ZIP_OUT" | cut -f1)"
echo "  Files : $(unzip -l "$ZIP_OUT" | tail -1 | awk '{print $2}')"
echo ""
echo "Contents:"
unzip -l "$ZIP_OUT" | head -60

# Clean up
rm -rf "$STAGING"
