#!/usr/bin/env bash
# Start LiteLLM Proxy for FactoryLM
# Loads secrets from Doppler (or .env fallback), runs proxy on :4000
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG="$REPO_ROOT/config/litellm_config.yaml"

if [ ! -f "$CONFIG" ]; then
  echo "ERROR: Config not found at $CONFIG"
  exit 1
fi

echo "Starting LiteLLM Proxy on :4000..."
echo "Config: $CONFIG"

# Try Doppler first, fall back to .env
if command -v doppler &>/dev/null && doppler secrets get DEEPSEEK_API_KEY -p factorylm -c dev --plain &>/dev/null 2>&1; then
  echo "Loading secrets from Doppler (factorylm/dev)"
  exec doppler run -p factorylm -c dev -- litellm --config "$CONFIG" --port 4000
else
  echo "Doppler unavailable — loading from environment/.env"
  if [ -f "$REPO_ROOT/.env" ]; then
    set -a
    source "$REPO_ROOT/.env"
    set +a
  fi
  exec litellm --config "$CONFIG" --port 4000
fi
