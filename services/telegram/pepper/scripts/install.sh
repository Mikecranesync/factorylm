#!/bin/bash
# PEPPER Installation Script
# FactoryLM Dual-Mode Telegram Bot System

set -e

echo "==================================="
echo "  PEPPER Installation Script"
echo "  FactoryLM Telegram Bot System"
echo "==================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Error: Please run as root"
    exit 1
fi

# Configuration
PEPPER_ROOT="/root/pepper"
PEPPER_STATE="/root/.pepper"
WATCHDOG_STATE="/root/.pepper-watchdog"
LOG_DIR="/var/log/pepper"

echo "[1/7] Creating directories..."
mkdir -p "$PEPPER_ROOT"
mkdir -p "$PEPPER_STATE/versions"
mkdir -p "$WATCHDOG_STATE/backups"
mkdir -p "$WATCHDOG_STATE/history"
mkdir -p "$LOG_DIR"

echo "[2/7] Copying PEPPER files..."
# Copy from repo to installation directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PEPPER_SRC="$(dirname "$SCRIPT_DIR")"

cp -r "$PEPPER_SRC"/* "$PEPPER_ROOT/"

echo "[3/7] Installing Python dependencies..."
pip3 install -r "$PEPPER_ROOT/requirements.txt"

echo "[4/7] Installing systemd services..."
cp "$PEPPER_ROOT/scripts/pepper.service" /etc/systemd/system/
cp "$PEPPER_ROOT/scripts/pepper-watchdog.service" /etc/systemd/system/
systemctl daemon-reload

echo "[5/7] Installing CLI..."
cp "$PEPPER_ROOT/scripts/pepper-cli" /usr/local/bin/pepper
chmod +x /usr/local/bin/pepper

echo "[6/7] Setting up environment..."
if [ ! -f "$PEPPER_ROOT/.env" ]; then
    cat > "$PEPPER_ROOT/.env" << 'EOF'
# PEPPER Environment Variables
# Fill in your tokens from Doppler or manually

# Bot Tokens
PEPPER_PRIME_TOKEN=
FACTORYLM_BOT_TOKEN=

# API Keys
GROQ_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=

# Optional
SENDGRID_API_KEY=
EOF
    echo "Created $PEPPER_ROOT/.env - Please fill in your tokens!"
fi

echo "[7/7] Creating initial version..."
# Create v0.0.0 as initial version
INITIAL_VERSION="$PEPPER_STATE/versions/v0.0.0"
mkdir -p "$INITIAL_VERSION/code"
cp -r "$PEPPER_ROOT"/* "$INITIAL_VERSION/code/" 2>/dev/null || true

cat > "$INITIAL_VERSION/manifest.json" << EOF
{
  "version": "v0.0.0",
  "created_at": "$(date -Iseconds)",
  "created_by": "install.sh",
  "git_commit": "initial",
  "changelog": ["Initial installation"],
  "rollback_safe": false
}
EOF

# Set up symlinks
ln -sf "$INITIAL_VERSION" "$PEPPER_STATE/current"

echo ""
echo "==================================="
echo "  Installation Complete!"
echo "==================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Edit environment file:"
echo "   nano $PEPPER_ROOT/.env"
echo ""
echo "2. Start PEPPER:"
echo "   systemctl enable --now pepper"
echo "   systemctl enable --now pepper-watchdog"
echo ""
echo "3. Check status:"
echo "   pepper status"
echo "   pepper health"
echo ""
echo "4. View logs:"
echo "   pepper logs -f"
echo ""
echo "Quick commands:"
echo "  pepper deploy          # Deploy new version"
echo "  pepper rollback        # Rollback to previous"
echo "  pepper status          # Show status"
echo ""
