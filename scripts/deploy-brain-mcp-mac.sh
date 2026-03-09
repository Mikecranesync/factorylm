#!/usr/bin/env bash
# ============================================================
# Open Brain MCP — Charlie Node One-Shot Deploy
# ============================================================
# Run on Charlie Mac Mini:
#   bash scripts/deploy-brain-mcp-mac.sh
#
# What this does:
#   1. Uses existing ~/factorylm repo (pulls latest)
#   2. Installs MCP + brain deps into ~/brain-venv
#   3. Reads secrets from ~/.env.brain + Doppler
#   4. Creates a macOS launchd plist (auto-start on boot)
#   5. Starts the brain MCP server on port 8501
#   6. Prevents Mac Mini from sleeping
#   7. Prints the claude mcp add command for other devices
# ============================================================
set -euo pipefail

REPO_DIR="$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)"
VENV_DIR="$HOME/brain-venv"
PORT=8501
LOG_DIR="/tmp/brain-mcp"
PLIST_NAME="com.factorylm.brain-mcp"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
ENV_FILE="$HOME/.env.brain"

echo "============================================"
echo "  Open Brain MCP — Charlie Deploy"
echo "============================================"
echo ""

# ----------------------------------------------------------
# 1. Repository
# ----------------------------------------------------------
echo "[1/7] Repository..."
if [ -d "$REPO_DIR/.git" ]; then
    echo "  Repo at $REPO_DIR"
    git -C "$REPO_DIR" pull --ff-only 2>/dev/null || true
else
    echo "  ERROR: Expected repo at $REPO_DIR"
    exit 1
fi
echo "  OK — $(git -C "$REPO_DIR" log --oneline -1)"
echo ""

# ----------------------------------------------------------
# 2. Python venv + dependencies
# ----------------------------------------------------------
echo "[2/7] Python venv + dependencies..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "  Created venv at $VENV_DIR"
fi
"$VENV_DIR/bin/python3" -m pip install --quiet --upgrade pip 2>&1 | tail -1
"$VENV_DIR/bin/python3" -m pip install --quiet -r "$REPO_DIR/services/brain/requirements.txt" 2>&1 | tail -3
echo "  OK"
echo ""

# ----------------------------------------------------------
# 3. Environment secrets
# ----------------------------------------------------------
echo "[3/7] Environment secrets..."
if [ ! -f "$ENV_FILE" ]; then
    echo "  ERROR: $ENV_FILE not found. Run deploy-charlie-brain.sh first."
    exit 1
fi
source "$ENV_FILE"
echo "  Loaded $ENV_FILE"

# Fetch BRAIN_ACCESS_KEY from Doppler
BRAIN_ACCESS_KEY=$(doppler secrets get BRAIN_ACCESS_KEY -p factorylm -c dev --plain 2>/dev/null || echo "")
if [ -z "$BRAIN_ACCESS_KEY" ]; then
    echo "  WARNING: BRAIN_ACCESS_KEY not found in Doppler. Server will run WITHOUT auth."
else
    echo "  BRAIN_ACCESS_KEY loaded from Doppler"
fi
echo ""

# ----------------------------------------------------------
# 4. Create launchd plist
# ----------------------------------------------------------
echo "[4/7] launchd service..."
mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$LOG_DIR"

PYTHON3="$VENV_DIR/bin/python3"
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "unknown")

cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON3}</string>
        <string>-m</string>
        <string>services.mcp.brain_server</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${REPO_DIR}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>MCP_HOST</key>
        <string>0.0.0.0</string>
        <key>MCP_PORT</key>
        <string>${PORT}</string>
        <key>MCP_TRANSPORT</key>
        <string>streamable-http</string>
        <key>BRAIN_ACCESS_KEY</key>
        <string>${BRAIN_ACCESS_KEY}</string>
        <key>NEON_DATABASE_URL</key>
        <string>${NEON_DATABASE_URL}</string>
        <key>GEMINI_API_KEY</key>
        <string>${GEMINI_API_KEY}</string>
        <key>GROQ_API_KEY</key>
        <string>${GROQ_API_KEY}</string>
        <key>PATH</key>
        <string>${VENV_DIR}/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/stderr.log</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
PLIST
echo "  Written to $PLIST_PATH"
echo ""

# ----------------------------------------------------------
# 5. Start (or restart) the service
# ----------------------------------------------------------
echo "[5/7] Starting service..."
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"
echo "  Loaded $PLIST_NAME"
sleep 3
echo ""

# ----------------------------------------------------------
# 6. Prevent sleep
# ----------------------------------------------------------
echo "[6/7] Preventing sleep..."
sudo pmset -a sleep 0 2>/dev/null && echo "  Sleep disabled" || echo "  WARNING: Could not disable sleep (need sudo)"
echo ""

# ----------------------------------------------------------
# 7. Health check + registration command
# ----------------------------------------------------------
echo "[7/7] Health check..."
if curl -sf "http://localhost:${PORT}/health" | python3 -m json.tool; then
    echo ""
    echo "============================================"
    echo "  BRAIN MCP RUNNING ON CHARLIE"
    echo "  http://${TAILSCALE_IP}:${PORT}/mcp"
    echo "  Logs: tail -f ${LOG_DIR}/stderr.log"
    echo "  Stop: launchctl unload $PLIST_PATH"
    echo "============================================"
    echo ""
    echo "Register on other devices:"
    echo ""
    echo "  claude mcp add --transport http open-brain \\"
    echo "    http://${TAILSCALE_IP}:${PORT}/mcp \\"
    if [ -n "$BRAIN_ACCESS_KEY" ]; then
        echo "    --header \"Authorization: Bearer ${BRAIN_ACCESS_KEY}\""
    else
        echo "    # No auth configured"
    fi
    echo ""
else
    echo "  HEALTH CHECK FAILED"
    echo "  Check logs: cat ${LOG_DIR}/stderr.log"
    echo "  Try manual: MCP_HOST=0.0.0.0 MCP_PORT=${PORT} MCP_TRANSPORT=streamable-http ${PYTHON3} -m services.mcp.brain_server"
    exit 1
fi
