#!/usr/bin/env bash

set -e

echo "=== Installing Rust toolchain (rustup) ==="
if ! command -v rustup >/dev/null 2>&1; then
  curl https://sh.rustup.rs -sSf | sh -s -- -y
else
  echo "rustup already installed"
fi

# Ensure cargo environment exists
if [ -f "$HOME/.cargo/env" ]; then
  source "$HOME/.cargo/env"
else
  echo "Rust environment not found after installation."
  echo "Please open a new shell or ensure rustup installed correctly."
  exit 1
fi

echo "=== Installing espup ==="
if ! command -v espup >/dev/null 2>&1; then
  cargo install espup
else
  echo "espup already installed"
fi

echo "=== Installing ESP Rust toolchains ==="
espup install

if [ -f "$HOME/export-esp.sh" ]; then
  echo "=== Sourcing ESP Rust environment ==="
  source "$HOME/export-esp.sh"
else
  echo "export-esp.sh not found. espup may have failed."
  exit 1
fi

echo "=== Installation complete ==="
echo "To activate ESP-IDF in new shells, run:"
echo "  source ~/esp/esp-idf/export.sh"
echo "  source ~/export-esp.sh"
