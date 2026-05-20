#!/usr/bin/env bash

set -e

echo "=== Ensuring cargo environment is loaded ==="
if [ -f "$HOME/.cargo/env" ]; then
  source "$HOME/.cargo/env"
else
  echo "Rust environment not found. Please install rustup first."
  exit 1
fi

echo "=== Installing espup (ESP Rust tool manager) ==="
if ! command -v espup >/dev/null 2>&1; then
  cargo install espup
else
  echo "espup already installed"
fi

echo "=== Installing ESP Rust toolchains ==="
espup install

if [ -f "$HOME/export-esp.sh" ]; then
  echo "=== ESP Rust toolchain installed successfully ==="
  echo "To activate it in this shell, run:"
  echo "  source ~/export-esp.sh"
else
  echo "ESP Rust environment file not found. Installation may have failed."
  exit 1
fi
