#!/usr/bin/env bash

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVER_BIN="$PROJECT_ROOT/mcp-antenna/target/release/mcp-antenna"

export PATH="$HOME/.npm-global/bin:$PATH"

echo "=== Building mcp-antenna (release) ==="
cd "$PROJECT_ROOT/mcp-antenna"
cargo build --release

echo "=== Starting MCP gateway (background) ==="
cd "$PROJECT_ROOT"

# Start serve in background using the wrapped WebSocket shim
NODE_OPTIONS="--require cvmi-wrapped.js" \
  npx cvmi serve "$SERVER_BIN" > serve.log 2>&1 &
SERVE_PID=$!

echo "Gateway PID: $SERVE_PID"
echo "Waiting for gateway to start..."

# Wait until public key appears (gateway ready)
until grep -q "Public key:" serve.log; do
  sleep 1
done

echo "Gateway started. Extracting public key..."

PUBKEY=$(grep "Public key:" serve.log | tail -n1 | awk '{print $NF}')

if [ -z "$PUBKEY" ]; then
  echo "Failed to extract public key. Check serve.log"
  kill $SERVE_PID || true
  exit 1
fi

echo "Public key: $PUBKEY"

echo "=== Calling MCP server ==="
echo "--- Listing tools ---"
npx cvmi call "$PUBKEY"

echo ""
echo "--- Calling get_position ---"
npx cvmi call "$PUBKEY" get_position

echo ""
echo "--- Calling move_antenna (az=5, el=3) ---"
npx cvmi call "$PUBKEY" move_antenna azimuth_steps=5 elevation_steps=3

echo ""
echo "--- Calling get_position (after move) ---"
npx cvmi call "$PUBKEY" get_position

echo ""
echo "Stopping gateway..."
kill $SERVE_PID || true

echo "Done."
