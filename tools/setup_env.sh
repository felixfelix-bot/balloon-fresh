#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== ESP32 Pico-Balloon Tracker - Environment Setup ==="
echo "Project: $PROJECT_DIR"
echo ""

check_tool() {
    if command -v "$1" &>/dev/null; then
        echo "  [OK] $1: $(command -v "$1")"
        return 0
    else
        echo "  [MISSING] $1"
        return 1
    fi
}

echo "--- ESP-IDF ---"
if [ -f "$HOME/esp/esp-idf/export.sh" ]; then
    echo "  [OK] ESP-IDF found at ~/esp/esp-idf/"
    echo "  Run: source ~/esp/esp-idf/export.sh"
else
    echo "  [MISSING] ESP-IDF not found at ~/esp/esp-idf/"
    echo "  Install: git clone -b v5.4.1 --recursive https://github.com/espressif/esp-idf.git ~/esp/esp-idf"
    echo "  Then:    ~/esp/esp-idf/install.sh esp32c3 && source ~/esp/esp-idf/export.sh"
fi

echo ""
echo "--- Python Tools ---"
check_tool python3
check_tool pip

echo ""
echo "Installing Python packages..."
pip install --user skidl graphviz 2>/dev/null || echo "  [WARN] skidl install failed, may need virtualenv"

echo ""
echo "--- KiCad ---"
if command -v kicad &>/dev/null; then
    echo "  [OK] KiCad: $(command -v kicad)"
else
    echo "  [MISSING] KiCad"
    echo "  Ubuntu: sudo apt install kicad"
    echo "  Or download from: https://www.kicad.org/download/"
fi

echo ""
echo "--- Serial Tools ---"
pip install --user esptool 2>/dev/null || true
check_tool esptool.py || check_tool esptool

echo ""
echo "--- Ruff (Python Linter) ---"
pip install --user ruff 2>/dev/null || true
check_tool ruff

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To start developing:"
echo "  source ~/esp/esp-idf/export.sh"
echo "  cd $PROJECT_DIR/firmware && idf.py build"
