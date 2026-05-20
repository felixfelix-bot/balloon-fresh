#!/usr/bin/env bash

set -e

echo "=== Ensuring Deno is installed ==="

if ! command -v deno >/dev/null 2>&1; then
  echo "Deno not found. Installing..."
  curl -fsSL https://deno.land/install.sh | sh
fi

# Ensure PATH for this session
export PATH="$HOME/.deno/bin:$PATH"

echo "Deno version:"
deno --version

echo ""
echo "=== IMPORTANT ==="
echo "1. Start gateway in another terminal:"
echo "   gateway-cli"
echo "2. Copy the LONG HEX pubkey printed in logs"
echo ""

read -p "Paste your server pubkey here: " PUBKEY

echo ""
echo "=== Discovering servers (optional) ==="
deno run -A jsr:@contextvm/cvmi discover || true

echo ""
echo "=== Listing available tools on server ==="
deno run -A jsr:@contextvm/cvmi call "$PUBKEY"

echo ""
echo "=== If you want to call a tool, use: ==="
echo "deno run -A jsr:@contextvm/cvmi call $PUBKEY <tool> param=value"

echo ""
echo "Done."
