#!/usr/bin/env bash

set -e

echo "Checking for existing ContextVM Gateway installation..."

if command -v gateway &> /dev/null; then
    echo "Gateway already installed."
    gateway --version
else
    if [ -f "/usr/local/bin/gateway-cli" ]; then
        echo "Found existing gateway-cli binary. Creating symlink..."
        sudo ln -sf /usr/local/bin/gateway-cli /usr/local/bin/gateway
    elif [ -f "/usr/local/bin/gateway-cli-linux" ]; then
        echo "Found existing gateway-cli-linux binary. Creating symlink..."
        sudo ln -sf /usr/local/bin/gateway-cli-linux /usr/local/bin/gateway
    else
        echo "Installing ContextVM Gateway CLI..."
        curl -fsSL https://raw.githubusercontent.com/contextvm/gateway-cli/main/install.sh | bash
        if [ -f "/usr/local/bin/gateway-cli" ]; then
            sudo ln -sf /usr/local/bin/gateway-cli /usr/local/bin/gateway
        elif [ -f "/usr/local/bin/gateway-cli-linux" ]; then
            sudo ln -sf /usr/local/bin/gateway-cli-linux /usr/local/bin/gateway
        fi
    fi

    # Ensure /usr/local/bin is in PATH
    if [[ ":$PATH:" != *":/usr/local/bin:"* ]]; then
        echo "Adding /usr/local/bin to PATH in ~/.bashrc"
        echo 'export PATH="/usr/local/bin:$PATH"' >> ~/.bashrc
        export PATH="/usr/local/bin:$PATH"
    fi

    echo "Verifying gateway installation..."
    if ! command -v gateway &> /dev/null; then
        echo "Gateway still not found in PATH."
        exit 1
    fi

    gateway --version
fi

echo ""
echo "Installing CVMI developer CLI (optional but recommended)..."

# Install cvmi via npm if available and not already installed
if command -v npm &> /dev/null; then
    if command -v cvmi &> /dev/null; then
        echo "CVMI already installed."
    else
        npm install -g @contextvm/cvmi || true
    fi
else
    echo "npm not found. Skipping CVMI installation."
fi

echo ""
echo "ContextVM installation complete."
echo ""
echo "Next steps:"
echo "1. Create a contextgw.config.yml file"
echo "2. Add your Nostr private key (hex format)"
echo "3. Run: gateway"
