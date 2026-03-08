#!/usr/bin/env bash
# ================================================================
# PLC Laptop WSL2 Setup Script
# Run INSIDE WSL Ubuntu: bash ~/factorylm/scripts/setup_wsl_plc.sh
# ================================================================
set -euo pipefail

echo "========================================="
echo "PLC Laptop WSL2 Setup"
echo "========================================="
echo ""

# Step 3: Upgrade Node to v22
echo "[1/5] Upgrading Node.js to v22..."
CURRENT_NODE=$(node --version 2>/dev/null || echo "none")
echo "  Current: $CURRENT_NODE"
if [[ "$CURRENT_NODE" != v22* ]]; then
    curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
    sudo apt install -y nodejs
    echo "  Installed: $(node --version)"
else
    echo "  Already v22, skipping."
fi

# Step 4: Install Claude Code
echo ""
echo "[2/5] Installing Claude Code..."
if ! command -v claude &>/dev/null || [[ "$(which claude)" == /mnt/c/* ]]; then
    sudo npm install -g @anthropic-ai/claude-code
    echo "  Installed: $(claude --version 2>/dev/null || echo 'check manually')"
else
    echo "  Already installed: $(claude --version 2>/dev/null)"
fi

# Step 5: Install Python PLC tools
echo ""
echo "[3/5] Installing Python PLC tools..."
pip3 install --user pymodbus requests fastmcp ollama qdrant-client pyyaml 2>/dev/null || \
    pip install --user pymodbus requests fastmcp ollama qdrant-client pyyaml
echo "  Done."

# Step 6: Install GitHub CLI
echo ""
echo "[4/5] Installing GitHub CLI..."
if ! command -v gh &>/dev/null; then
    sudo apt install -y gh
    echo "  Installed. Run 'gh auth login' manually to authenticate."
else
    echo "  Already installed: $(gh --version | head -1)"
fi

# Step 7: Set PLC env vars + boot alias
echo ""
echo "[5/5] Configuring environment..."
MARKER="# === PLC Laptop identity ==="
if ! grep -q "$MARKER" ~/.bashrc 2>/dev/null; then
    cat >> ~/.bashrc << 'ENVEOF'

# === PLC Laptop identity ===
export FACTORYLM_NODE="plclaptop"
export MODBUS_HOST="localhost"
export MODBUS_PORT=5020
export FACTORY_IO_HOST="localhost"
export PLC_REAL_HOST="192.168.1.100"
export PLC_REAL_PORT=502
export OLLAMA_HOST="http://localhost:11434"
export ANTHROPIC_MODEL="sonnet"

# Boot alias
alias factoryboot="cd ~/factorylm && claude"
ENVEOF
    echo "  Environment variables added to ~/.bashrc"
else
    echo "  Already configured, skipping."
fi

# Source it
source ~/.bashrc 2>/dev/null || true

echo ""
echo "========================================="
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Run: gh auth login"
echo "  2. Run: cd ~ && gh repo clone Mikecranesync/factorylm"
echo "  3. Run: cd ~/factorylm && git checkout feat/cosmos-cookoff-snapshot"
echo "  4. Run: factoryboot"
echo "========================================="
