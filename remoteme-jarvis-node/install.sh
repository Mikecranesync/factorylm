#!/usr/bin/env bash
set -e
echo "=== Jarvis Node Installer (macOS/Linux) ==="

# Check Python
command -v python3 >/dev/null 2>&1 || { echo "ERROR: Python 3 not found"; exit 1; }

# Install deps
echo "Installing dependencies..."
pip3 install fastapi uvicorn psutil mss --break-system-packages 2>/dev/null || pip3 install fastapi uvicorn psutil mss

# Generate token if not set
if [ -z "$JARVIS_TOKEN" ]; then
    TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    echo ""
    echo "WARNING: JARVIS_TOKEN not set. Generated one:"
    echo "  export JARVIS_TOKEN=$TOKEN"
    echo ""
    echo "Add to your ~/.zshrc or ~/.bashrc to persist."
    export JARVIS_TOKEN=$TOKEN
fi

# Get Tailscale IP
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "")
if [ -z "$TAILSCALE_IP" ]; then
    echo "WARNING: Tailscale not detected. Binding to 127.0.0.1 (local only)"
    TAILSCALE_IP="127.0.0.1"
else
    echo "Tailscale IP: $TAILSCALE_IP"
fi

echo ""
echo "Starting Jarvis Node on $TAILSCALE_IP:8765..."
python3 -m uvicorn jarvis_node:app --host "$TAILSCALE_IP" --port 8765
