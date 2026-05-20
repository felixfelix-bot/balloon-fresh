#!/usr/bin/env bash

set -e

echo "Checking for Node.js..."

if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
  echo "Node.js already installed: $(node -v)"
else
  echo "Installing Node.js (LTS)..."
  curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
  sudo apt install -y nodejs
fi

echo "Verifying Node installation..."
node -v
npm -v

echo "Checking for existing CVMI installation..."

if command -v cvmi >/dev/null 2>&1; then
  echo "CVMI already installed: $(cvmi --version || echo 'installed')"
else
  echo "Configuring user-level npm global directory..."
  mkdir -p "$HOME/.npm-global"
  npm config set prefix "$HOME/.npm-global"

  if ! grep -q 'npm-global/bin' "$HOME/.bashrc"; then
    echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> "$HOME/.bashrc"
  fi

  export PATH="$HOME/.npm-global/bin:$PATH"

  echo "Installing CVMI globally (user-level)..."
  npm install -g cvmi
fi

echo "Verifying CVMI installation..."
if command -v cvmi >/dev/null 2>&1; then
  cvmi --version
else
  echo "CVMI installed. Restart your shell or run: source ~/.bashrc"
fi

echo ""
echo "CVMI setup complete."
echo "Run: cvmi"
