#!/usr/bin/env bash
# One-command Jarvis Node installer.
#
#   macOS  -> launchd LaunchAgent (com.factorylm.jarvis-node), KeepAlive
#   Linux  -> systemd --user unit (jarvis-node.service), Restart=always + linger
#
# Idempotent: re-running re-installs the service and restarts the node.
# Binds tailnet-only via run-node.sh. See README-DEPLOY.md for the Windows path.
#
#   curl/clone the repo, then:  ./install-node.sh
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${JARVIS_PORT:-8765}"
LABEL="com.factorylm.jarvis-node"

# Cluster node name (ALPHA/BRAVO/CHARLIE/PLC/TRAVEL/PI). First arg, else env, else
# a cleaned short hostname. Baked into the service env so the node self-identifies.
NODE_NAME="${1:-${JARVIS_MACHINE_NAME:-$(hostname -s 2>/dev/null || hostname)}}"

echo "==> Jarvis Node installer   (repo: $DIR, node: $NODE_NAME)"

# 1. Dependencies
PY="$(command -v python3 || command -v python)"
echo "==> Python: $PY ($("$PY" --version 2>&1))"
"$PY" -m pip install --user --quiet --disable-pip-version-check \
  fastapi uvicorn psutil mss 2>&1 | tail -1 || \
  echo "    (pip reported issues — continuing; deps may already be satisfied)"

chmod +x "$DIR/run-node.sh"

OS="$(uname -s)"
case "$OS" in
  Darwin)
    PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
    echo "==> macOS / launchd -> $PLIST"
    launchctl unload "$PLIST" 2>/dev/null || true
    pkill -f "uvicorn jarvis_node:app" 2>/dev/null || true
    sleep 1
    mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
    cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
    <array><string>$DIR/run-node.sh</string></array>
  <key>EnvironmentVariables</key>
    <dict><key>JARVIS_MACHINE_NAME</key><string>$NODE_NAME</string></dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/jarvis-node.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/jarvis-node.err</string>
</dict>
</plist>
PLISTEOF
    launchctl load "$PLIST"
    ;;
  Linux)
    UNIT="$HOME/.config/systemd/user/jarvis-node.service"
    echo "==> Linux / systemd --user -> $UNIT"
    pkill -f "uvicorn jarvis_node:app" 2>/dev/null || true
    mkdir -p "$(dirname "$UNIT")"
    cat > "$UNIT" <<UNITEOF
[Unit]
Description=Jarvis Node (FastAPI remote-control MCP, tailnet-only)
After=network-online.target

[Service]
Environment=JARVIS_MACHINE_NAME=$NODE_NAME
ExecStart=$DIR/run-node.sh
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
UNITEOF
    systemctl --user daemon-reload
    systemctl --user enable --now jarvis-node.service
    loginctl enable-linger "$USER" 2>/dev/null || true  # survive logout / boot
    ;;
  *)
    echo "Unsupported OS: $OS"
    echo "Windows: run start-jarvis-node.bat, or wrap it with NSSM / Task Scheduler."
    exit 1
    ;;
esac

# 2. Healthcheck
sleep 3
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
TS_BIN="$(command -v tailscale || echo /opt/homebrew/bin/tailscale)"
HOST="$("$TS_BIN" ip -4 2>/dev/null | head -1 || true)"
if [ -z "${HOST:-}" ] && [ -S /var/run/tailscale/tailscaled.sock ]; then
  HOST="$("$TS_BIN" --socket=/var/run/tailscale/tailscaled.sock ip -4 2>/dev/null | head -1 || true)"
fi
HOST="${HOST:-127.0.0.1}"
echo "==> Health: http://$HOST:$PORT/health"
if curl -s --max-time 5 "http://$HOST:$PORT/health"; then
  echo ""
  echo "✅ Jarvis Node up on http://$HOST:$PORT  (machine: $(hostname -s 2>/dev/null || hostname))"
else
  echo "❌ health check failed — check logs (macOS: ~/Library/Logs/jarvis-node.err ; Linux: journalctl --user -u jarvis-node)"
  exit 1
fi
