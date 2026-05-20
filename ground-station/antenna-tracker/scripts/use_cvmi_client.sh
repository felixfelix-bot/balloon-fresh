#!/usr/bin/env bash

set -e

echo "=== Checking for Deno ==="

if ! command -v deno >/dev/null 2>&1; then
  echo "Deno not found. Installing..."
  curl -fsSL https://deno.land/install.sh | sh
  export PATH="$HOME/.deno/bin:$PATH"
else
  echo "Deno found: $(deno --version | head -n 1)"
fi

echo ""
echo "=== Discovering ContextVM servers on relays ==="
echo "(Make sure gateway-cli is running in another terminal)"
echo ""

deno run -A jsr:@contextvm/cvmi discover

echo ""
echo "=== To call a server ==="
echo "Replace <PUBKEY> with the hex pubkey shown in your gateway logs"
echo ""
echo "Example:"
echo "deno run -A jsr:@contextvm/cvmi call <PUBKEY>"
echo ""
echo "To call a specific tool:"
echo "deno run -A jsr:@contextvm/cvmi call <PUBKEY> <tool> param=value"
echo ""
echo "Example (replace with real tool name):"
echo "deno run -A jsr:@contextvm/cvmi call <PUBKEY> get_position"
