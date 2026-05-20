#!/usr/bin/env bash

set -e

echo "=== Installing espup using stable host toolchain ==="

# Ensure cargo env is loaded
if [ -f "$HOME/.cargo/env" ]; then
  source "$HOME/.cargo/env"
else
  echo "Rust environment not found. Install rustup first."
  exit 1
fi

echo "=== Installing espup with stable toolchain override ==="
cargo +stable install espup

echo "=== Running espup install ==="
espup install

if [ -f "$HOME/export-esp.sh" ]; then
  echo "=== ESP Rust toolchain installed successfully ==="
  echo "Activate it with:"
  echo "  source ~/export-esp.sh"
  echo ""
  echo "Verify with:"
  echo "  rustup toolchain list"
else
  echo "ESP Rust environment file not found. Installation may have failed."
  exit 1
fi
