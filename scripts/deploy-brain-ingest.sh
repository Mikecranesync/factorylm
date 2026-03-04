#!/usr/bin/env bash
# Deploy Open Brain Ingest Server to VPS
# Run from the VPS: bash /opt/openclaw/scripts/deploy-brain-ingest.sh
set -euo pipefail

VENV=/opt/openclaw/brain-venv
SERVICE=brain-ingest

echo "=== Open Brain Ingest Deploy ==="

# 1. Create venv if missing
if [ ! -d "$VENV" ]; then
    echo "Creating venv at $VENV..."
    python3 -m venv "$VENV"
fi

# 2. Install deps
echo "Installing dependencies..."
"$VENV/bin/pip" install --upgrade pip
"$VENV/bin/pip" install -r /opt/openclaw/services/brain/requirements.txt

# 3. Check env file
if [ ! -f /opt/openclaw/.env.brain ]; then
    echo ""
    echo "WARNING: /opt/openclaw/.env.brain not found!"
    echo "Create it with:"
    echo "  NEON_DATABASE_URL=..."
    echo "  GEMINI_API_KEY=..."
    echo "  GROQ_API_KEY=..."
    echo "  BRAIN_ACCESS_KEY=...  (optional)"
    echo ""
fi

# 4. Install systemd service
echo "Installing systemd service..."
cp /opt/openclaw/scripts/brain-ingest.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable "$SERVICE"
systemctl restart "$SERVICE"

# 5. Verify
sleep 2
echo ""
echo "=== Service Status ==="
systemctl status "$SERVICE" --no-pager -l | head -15
echo ""
echo "=== Health Check ==="
curl -sf http://localhost:8500/health && echo "" || echo "HEALTH CHECK FAILED"
echo ""
echo "=== Done ==="
