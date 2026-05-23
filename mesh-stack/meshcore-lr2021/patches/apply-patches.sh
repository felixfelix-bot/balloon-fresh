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

mkdir -p "$MESHCORE_DIR/variants/nicerf_lr2021"
cp -v "$SCRIPT_DIR/variant/platformio.ini" "$MESHCORE_DIR/variants/nicerf_lr2021/platformio.ini"
cp -v "$SCRIPT_DIR/variant/target.h" "$MESHCORE_DIR/variants/nicerf_lr2021/target.h"
cp -v "$SCRIPT_DIR/variant/target.cpp" "$MESHCORE_DIR/variants/nicerf_lr2021/target.cpp"
cp -v "$SCRIPT_DIR/variant/NiceRFLR2021Board.h" "$MESHCORE_DIR/variants/nicerf_lr2021/NiceRFLR2021Board.h"

echo "Done. Variant files copied to $MESHCORE_DIR"
