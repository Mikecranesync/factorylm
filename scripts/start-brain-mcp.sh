#!/usr/bin/env bash
set -euo pipefail

DOPPLER="/c/Users/hharp/scoop/shims/doppler.exe"
PYTHON="/c/Users/hharp/AppData/Local/Microsoft/WindowsApps/python.exe"

if [ ! -x "$DOPPLER" ]; then
    echo "ERROR: doppler not found at $DOPPLER" >&2
    exit 1
fi

# Fetch GEMINI_API_KEY from factorylm/dev (different project than openclaw/dev)
GEMINI_API_KEY=$("$DOPPLER" secrets get GEMINI_API_KEY -p factorylm -c dev --plain)
export GEMINI_API_KEY

# doppler run injects NEON_DATABASE_URL + GROQ_API_KEY from openclaw/dev
exec "$DOPPLER" run -p openclaw -c dev -- "$PYTHON" -m services.mcp.brain_server
