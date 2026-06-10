#!/usr/bin/env bash
# Setup FLRC test project
# Copies board definition and variant into PlatformIO framework dirs
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

FRAMEWORK_DIR="$HOME/.platformio/packages/framework-arduinoespressif32"
VARIANTS_DIR="$FRAMEWORK_DIR/variants"
BOARDS_DIR="$FRAMEWORK_DIR/boards"

if [ ! -d "$FRAMEWORK_DIR" ]; then
    echo "ERROR: PlatformIO Arduino framework not found at $FRAMEWORK_DIR"
    echo "Run 'pio run' once first to install it."
    exit 1
fi

mkdir -p "$VARIANTS_DIR/esp32c3_supermini"
cp "$SCRIPT_DIR/variants/esp32c3_supermini/pins_arduino.h" \
   "$VARIANTS_DIR/esp32c3_supermini/pins_arduino.h"
echo "Installed variant: esp32c3_supermini"

mkdir -p "$BOARDS_DIR"
cp "$SCRIPT_DIR/boards/esp32c3_supermini.json" "$BOARDS_DIR/"
echo "Installed board: esp32c3_supermini.json"

echo "Setup complete. Run 'pio run -e flrc_tx' to build."
