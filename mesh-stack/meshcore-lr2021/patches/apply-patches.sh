#!/bin/bash
set -euo pipefail

MESHCORE_DIR="${1:-MeshCore}"

if [ ! -d "$MESHCORE_DIR" ]; then
    echo "ERROR: MeshCore directory not found at $MESHCORE_DIR"
    echo "Usage: $0 <path_to_meshcore_checkout>"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Applying LR2021 variant patches to $MESHCORE_DIR ..."

cp -v "$SCRIPT_DIR/CustomLR2021.h" "$MESHCORE_DIR/src/helpers/radiolib/CustomLR2021.h"
cp -v "$SCRIPT_DIR/CustomLR2021Wrapper.h" "$MESHCORE_DIR/src/helpers/radiolib/CustomLR2021Wrapper.h"
cp -v "$SCRIPT_DIR/EspIdfHal.h" "$MESHCORE_DIR/variants/nicerf_lr2021/EspIdfHal.h"

mkdir -p "$MESHCORE_DIR/variants/nicerf_lr2021"
cp -v "$SCRIPT_DIR/variant/platformio.ini" "$MESHCORE_DIR/variants/nicerf_lr2021/platformio.ini"
cp -v "$SCRIPT_DIR/variant/target.h" "$MESHCORE_DIR/variants/nicerf_lr2021/target.h"
cp -v "$SCRIPT_DIR/variant/target.cpp" "$MESHCORE_DIR/variants/nicerf_lr2021/target.cpp"
cp -v "$SCRIPT_DIR/variant/NiceRFLR2021Board.h" "$MESHCORE_DIR/variants/nicerf_lr2021/NiceRFLR2021Board.h"

mkdir -p "$MESHCORE_DIR/boards"
cp -v "$SCRIPT_DIR/boards/esp32c3_supermini.json" "$MESHCORE_DIR/boards/esp32c3_supermini.json"

mkdir -p "$MESHCORE_DIR/variants/esp32c3_supermini"
cp -v "$SCRIPT_DIR/variant/esp32c3_supermini/pins_arduino.h" "$MESHCORE_DIR/variants/esp32c3_supermini/pins_arduino.h"

FRAMEWORK_VARIANTS_DIR="${HOME}/.platformio/packages/framework-arduinoespressif32/variants"
if [ -d "$FRAMEWORK_VARIANTS_DIR" ]; then
    mkdir -p "$FRAMEWORK_VARIANTS_DIR/esp32c3_supermini"
    cp -v "$SCRIPT_DIR/variant/esp32c3_supermini/pins_arduino.h" "$FRAMEWORK_VARIANTS_DIR/esp32c3_supermini/pins_arduino.h"
    echo "Copied pins_arduino.h to framework variants dir: $FRAMEWORK_VARIANTS_DIR/esp32c3_supermini/"
else
    echo "WARNING: Framework variants dir not found at $FRAMEWORK_VARIANTS_DIR"
    echo "You may need to copy pins_arduino.h there manually for the build to succeed."
fi

echo "Done. Variant + board files copied to $MESHCORE_DIR"
