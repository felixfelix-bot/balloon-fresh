#!/usr/bin/env bash

set -e

SERVER_BINARY="./mcp-antenna/target/release/mcp-antenna"

if [ ! -f "$SERVER_BINARY" ]; then
  echo "Error: MCP server binary not found at $SERVER_BINARY"
  echo "Run: cargo build --release -p mcp-antenna"
  exit 1
fi

echo "=== Testing MCP initialize handshake over stdio ==="
echo "Sending initialize request..."

echo '{"jsonrpc":"2.0","id":"1","method":"initialize","params":{}}' \
  | "$SERVER_BINARY"

echo ""
echo "=== Test complete ==="
