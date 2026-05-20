#!/usr/bin/env bash

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVER_DIR="$PROJECT_ROOT/mcp-antenna"
SERVER_BIN="$SERVER_DIR/target/release/mcp-antenna"

echo "=== Ensuring Deno is available ==="

if ! command -v deno >/dev/null 2>&1; then
  echo "Deno not found. Installing..."
  curl -fsSL https://deno.land/install.sh | sh
fi

# Ensure PATH for this session
export PATH="$HOME/.deno/bin:$PATH"

echo "Using Deno: $(deno --version | head -n 1)"

echo ""
echo "=== Building mcp-antenna (release) ==="

cd "$SERVER_DIR"
cargo build --release

if [ ! -f "$SERVER_BIN" ]; then
  echo "Error: build completed but binary not found at $SERVER_BIN"
  exit 1
fi

echo ""
echo "=== Launching MCP Gateway via CVMI ==="
echo "Binary: $SERVER_BIN"
echo ""
echo "Press Ctrl+C to stop the gateway."
echo ""

cd "$PROJECT_ROOT"
deno run -A npm:cvmi serve "$SERVER_BIN"
