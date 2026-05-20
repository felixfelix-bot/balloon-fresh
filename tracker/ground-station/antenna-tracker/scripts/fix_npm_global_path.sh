#!/usr/bin/env bash

set -e

NPM_PREFIX="$(npm config get prefix)"
NPM_BIN="$NPM_PREFIX/bin"

echo "Detected npm global bin directory: $NPM_BIN"

# Add to .bashrc if not already present
if ! grep -q "$NPM_BIN" "$HOME/.bashrc"; then
  echo "Adding $NPM_BIN to PATH in ~/.bashrc"
  echo "export PATH=\"$NPM_BIN:\$PATH\"" >> "$HOME/.bashrc"
else
  echo "PATH already configured in ~/.bashrc"
fi

# Export for current session
export PATH="$NPM_BIN:$PATH"

echo ""
echo "Updated PATH for this session."
echo "You can verify with:"
echo "  which cvmi"
