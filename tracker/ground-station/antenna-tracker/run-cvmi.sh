#!/usr/bin/env bash

# Ensure we are in the project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Preload WebSocket shim and run cvmi
NODE_OPTIONS="--require ${SCRIPT_DIR}/cvmi-wrapped.js" \
  npx cvmi serve ./mcp-antenna/target/release/mcp-antenna
