#!/usr/bin/env bash

set -e

echo "=== Installing ContextVM Gateway CLI ==="

# Install gateway CLI
curl -fsSL https://raw.githubusercontent.com/contextvm/gateway-cli/main/install.sh | bash

echo "=== Ensuring ~/.local/bin is in PATH ==="

# Add ~/.local/bin to PATH if not already present
if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$HOME/.bashrc"; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
    echo "Added ~/.local/bin to PATH in ~/.bashrc"
else
    echo "PATH already configured in ~/.bashrc"
fi

# Export for current session
export PATH="$HOME/.local/bin:$PATH"

echo "=== Verifying gateway installation ==="

if command -v gateway >/dev/null 2>&1; then
    echo "Gateway found at: $(which gateway)"
else
    echo "ERROR: gateway not found after installation"
    exit 1
fi

echo "=== Building mcp-antenna (release) ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT/mcp-antenna"

cargo build --release

echo "=== Running tests ==="

cargo test

echo "=== Setup complete ==="
echo "You can now run the gateway from:"
echo "  cd $PROJECT_ROOT"
echo "  gateway"
