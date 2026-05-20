#!/usr/bin/env bash

set -e

echo "=== Installing Deno (if not present) ==="

if ! command -v deno >/dev/null 2>&1; then
  curl -fsSL https://deno.land/install.sh | sh
fi

echo "=== Ensuring Deno is in PATH ==="

if ! grep -q '.deno/bin' "$HOME/.bashrc"; then
  echo 'export PATH="$HOME/.deno/bin:$PATH"' >> "$HOME/.bashrc"
fi

export PATH="$HOME/.deno/bin:$PATH"

echo "Deno version:"
deno --version

echo ""
echo "=== Creating CVMI alias ==="

if ! grep -q 'alias cvmi=' "$HOME/.bashrc"; then
  echo 'alias cvmi="deno run -A jsr:@contextvm/cvmi"' >> "$HOME/.bashrc"
fi

alias cvmi="deno run -A jsr:@contextvm/cvmi"

echo ""
echo "=== Testing CVMI ==="
cvmi --help

echo ""
echo "=== Usage ==="
echo "1. Start your server in another terminal:"
echo "   gateway-cli"
echo ""
echo "2. Discover servers:"
echo "   cvmi discover"
echo ""
echo "3. Call your server:"
echo "   cvmi call <PUBKEY>"
echo ""
echo "4. Call a tool:"
echo "   cvmi call <PUBKEY> <tool> param=value"

echo ""
echo "Setup complete. Open a new terminal to use the cvmi alias persistently."
