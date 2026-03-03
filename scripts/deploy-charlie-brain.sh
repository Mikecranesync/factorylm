#!/usr/bin/env bash
# ============================================================
# Open Brain Ingest — Charlie Node One-Shot Deploy
# ============================================================
# Run on Charlie Mac Mini:
#   curl -sL https://raw.githubusercontent.com/Mikecranesync/factorylm/worktree-feat-open-brain/scripts/deploy-charlie-brain.sh | bash
#
# Or if repo is already cloned:
#   bash scripts/deploy-charlie-brain.sh
#
# What this does:
#   1. Clones/updates the factorylm repo
#   2. Installs Python dependencies
#   3. Writes env secrets
#   4. Creates a macOS launchd plist (auto-start on boot)
#   5. Starts the brain ingest server on port 8500
#   6. Verifies health
# ============================================================
set -euo pipefail

REPO_DIR="$HOME/factorylm-monorepo"
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
# 1. Clone or update repo
# ----------------------------------------------------------
echo "[1/6] Repository..."
if [ -d "$REPO_DIR/.git" ]; then
    echo "  Repo exists, pulling latest..."
    cd "$REPO_DIR"
    git fetch origin "$BRANCH"
    git checkout "$BRANCH"
    git pull origin "$BRANCH"
else
    echo "  Cloning repo..."
    gh repo clone Mikecranesync/factorylm "$REPO_DIR"
    cd "$REPO_DIR"
    git checkout "$BRANCH"
fi
echo "  OK — $(git log --oneline -1)"
echo ""

# ----------------------------------------------------------
# 2. Install Python dependencies
# ----------------------------------------------------------
echo "[2/6] Python dependencies..."
python3 -m pip install --user --quiet \
    mem0ai fastapi uvicorn psycopg2-binary google-genai groq 2>&1 | tail -3
echo "  OK"
echo ""

# ----------------------------------------------------------
# 3. Write env file (secrets)
# ----------------------------------------------------------
echo "[3/6] Environment secrets..."
if [ -f "$ENV_FILE" ]; then
    echo "  $ENV_FILE already exists, skipping (delete to regenerate)"
else
    cat > "$ENV_FILE" <<'SECRETS'
export NEON_DATABASE_URL="postgresql://neondb_owner:npg_c3UNa4KOlCeL@ep-purple-hall-ahimeyn0-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require"
export GEMINI_API_KEY="AIzaSyCLcSmsEFkx5C_eGaATHvFRGYEBOHPPPbg"
export GROQ_API_KEY="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"
SECRETS
    chmod 600 "$ENV_FILE"
    echo "  Written to $ENV_FILE"
fi
echo ""

# ----------------------------------------------------------
# 4. Create launchd plist (auto-start on boot)
# ----------------------------------------------------------
echo "[4/6] launchd service..."
mkdir -p "$HOME/Library/LaunchAgents"

# Find python3 path
PYTHON3=$(which python3)

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
    <string>${REPO_DIR}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>NEON_DATABASE_URL</key>
        <string>postgresql://neondb_owner:npg_c3UNa4KOlCeL@ep-purple-hall-ahimeyn0-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require</string>
        <key>GEMINI_API_KEY</key>
        <string>AIzaSyCLcSmsEFkx5C_eGaATHvFRGYEBOHPPPbg</string>
        <key>GROQ_API_KEY</key>
        <string>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</string>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:${HOME}/.local/bin:${HOME}/Library/Python/3.9/bin:${HOME}/Library/Python/3.11/bin:${HOME}/Library/Python/3.12/bin</string>
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
# Unload if already loaded
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
    echo "  http://$(hostname -I 2>/dev/null || ipconfig getifaddr en1):${PORT}"
    echo "  Logs: tail -f $LOG"
    echo "  Stop: launchctl unload $PLIST_PATH"
    echo "============================================"
else
    echo "  HEALTH CHECK FAILED"
    echo "  Check logs: cat /tmp/brain-ingest.err"
    echo "  Try manual: source ~/.env.brain && cd $REPO_DIR && python3 -m uvicorn services.brain.ingest:app --host 0.0.0.0 --port $PORT"
    exit 1
fi
