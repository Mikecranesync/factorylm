#!/usr/bin/env bash
# Start LiteLLM Proxy for FactoryLM
# Uses python3.12 to avoid uvloop breakage on 3.14
# Loads secrets from Doppler (or .env fallback), runs proxy on :4000
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG="$REPO_ROOT/config/litellm_config.yaml"
PYTHON="${FACTORYLM_PYTHON:-python3.12}"

if [ ! -f "$CONFIG" ]; then
  echo "ERROR: Config not found at $CONFIG"
  exit 1
fi

echo "Starting LiteLLM Proxy on :4000..."
echo "Config: $CONFIG"
echo "Python: $($PYTHON --version 2>&1)"

# Build the python startup command (inline script avoids -m litellm issues)
PYCMD="
from litellm.proxy.proxy_server import app, initialize
import uvicorn, asyncio
asyncio.run(initialize(config='$CONFIG', telemetry=False))
uvicorn.run(app, host='0.0.0.0', port=4000, loop='asyncio')
"

# Try Doppler first, fall back to .env
if command -v doppler &>/dev/null && doppler secrets get DEEPSEEK_API_KEY --plain &>/dev/null 2>&1; then
  echo "Loading secrets from Doppler (factorylm/dev)"
  exec doppler run -- $PYTHON -c "$PYCMD"
else
  echo "Doppler unavailable — loading from environment/.env"
  if [ -f "$REPO_ROOT/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$REPO_ROOT/.env"
    set +a
  fi
  exec $PYTHON -c "$PYCMD"
fi
