#!/usr/bin/env bash
# ============================================================
# Open Brain Ingest — Charlie Node One-Shot Deploy
# ============================================================
# Run on Charlie Mac Mini:
#   bash scripts/deploy-charlie-brain.sh
#
# What this does:
#   1. Uses the existing ~/factorylm repo (pulls latest)
#   2. Creates a Python venv and installs dependencies
#   3. Prompts for env secrets (or reads existing ~/.env.brain)
#   4. Creates a macOS launchd plist (auto-start on boot)
#   5. Starts the brain ingest server on port 8500
#   6. Verifies health
# ============================================================
set -euo pipefail

REPO_DIR="$HOME/factorylm"
WORKTREE_DIR="$REPO_DIR/.claude/worktrees/feat-open-brain"
VENV_DIR="$HOME/brain-venv"
BRANCH="worktree-feat-open-brain"
PORT=8500
LOG="/tmp/brain-ingest.log"
PLIST_NAME="com.factorylm.brain-ingest"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
ENV_FILE="$HOME/.env.brain"

echo "============================================"
echo "  Open Brain Ingest — Charlie Deploy"
echo "============================================"
echo ""

# ----------------------------------------------------------
# 1. Repository — use existing clone
# ----------------------------------------------------------
echo "[1/6] Repository..."
if [ -d "$REPO_DIR/.git" ]; then
    echo "  Repo exists at $REPO_DIR, pulling latest..."
    git -C "$REPO_DIR" fetch origin "$BRANCH" 2>/dev/null || true
    git -C "$REPO_DIR" pull --ff-only 2>/dev/null || true
else
    echo "  ERROR: Expected repo at $REPO_DIR — clone it first:"
    echo "    gh repo clone Mikecranesync/factorylm $REPO_DIR"
    exit 1
fi

# Determine working directory (prefer worktree if it exists)
if [ -d "$WORKTREE_DIR/services/brain" ]; then
    WORK_DIR="$WORKTREE_DIR"
    echo "  Using worktree at $WORK_DIR"
else
    WORK_DIR="$REPO_DIR"
    echo "  Using repo root at $WORK_DIR"
fi
echo "  OK — $(git -C "$WORK_DIR" log --oneline -1)"
echo ""

# ----------------------------------------------------------
# 2. Python venv + dependencies
# ----------------------------------------------------------
echo "[2/6] Python venv + dependencies..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "  Created venv at $VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
pip install --quiet --upgrade pip 2>&1 | tail -1
pip install --quiet -r "$WORK_DIR/services/brain/requirements.txt" 2>&1 | tail -3
echo "  OK"
echo ""

# ----------------------------------------------------------
# 3. Environment secrets
# ----------------------------------------------------------
echo "[3/6] Environment secrets..."
if [ -f "$ENV_FILE" ]; then
    echo "  $ENV_FILE already exists, skipping (delete to regenerate)"
else
    echo "  No $ENV_FILE found. Enter secrets (or Ctrl-C to abort):"
    read -rp "  NEON_DATABASE_URL: " NEON_URL
    read -rp "  GEMINI_API_KEY:    " GEMINI_KEY
    read -rp "  GROQ_API_KEY:      " GROQ_KEY
    cat > "$ENV_FILE" <<SECRETS
export NEON_DATABASE_URL="$NEON_URL"
export GEMINI_API_KEY="$GEMINI_KEY"
export GROQ_API_KEY="$GROQ_KEY"
SECRETS
    chmod 600 "$ENV_FILE"
    echo "  Written to $ENV_FILE (mode 600)"
fi

# Source the env to get values for the plist
source "$ENV_FILE"
echo ""

# ----------------------------------------------------------
# 4. Create launchd plist (auto-start on boot)
# ----------------------------------------------------------
echo "[4/6] launchd service..."
mkdir -p "$HOME/Library/LaunchAgents"

PYTHON3="$VENV_DIR/bin/python3"

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
        <string>uvicorn</string>
        <string>services.brain.ingest:app</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>${PORT}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${WORK_DIR}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>NEON_DATABASE_URL</key>
        <string>${NEON_DATABASE_URL}</string>
        <key>GEMINI_API_KEY</key>
        <string>${GEMINI_API_KEY}</string>
        <key>GROQ_API_KEY</key>
        <string>${GROQ_API_KEY}</string>
        <key>PATH</key>
        <string>${VENV_DIR}/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/brain-ingest.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/brain-ingest.err</string>
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
echo "[5/6] Starting service..."
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"
echo "  Loaded $PLIST_NAME"
sleep 3
echo ""

# ----------------------------------------------------------
# 6. Health check
# ----------------------------------------------------------
echo "[6/6] Health check..."
if curl -sf "http://localhost:${PORT}/health"; then
    echo ""
    echo ""
    echo "============================================"
    echo "  BRAIN INGEST RUNNING ON CHARLIE"
    echo "  http://$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo localhost):${PORT}"
    echo "  Logs: tail -f $LOG"
    echo "  Stop: launchctl unload $PLIST_PATH"
    echo "============================================"
else
    echo "  HEALTH CHECK FAILED"
    echo "  Check logs: cat /tmp/brain-ingest.err"
    echo "  Try manual: source ~/.env.brain && cd $WORK_DIR && $PYTHON3 -m uvicorn services.brain.ingest:app --host 0.0.0.0 --port $PORT"
    exit 1
fi
