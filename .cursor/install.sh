#!/usr/bin/env bash
# FactoryLM — Cloud Agent install script.
# Idempotent: safe to run repeatedly. Sets up a Python 3.12 venv and installs
# the production Python components used for local development and testing:
#   - core/                 (LLM abstraction library)
#   - services/plc-modbus/  (PLC Modbus client + FastAPI service, with backend + dev extras)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VENV="$REPO_ROOT/.venv"
PY=python3.12

# The base image ships python3.12 but not the venv module; install it once.
if ! "$PY" -c 'import ensurepip' >/dev/null 2>&1; then
  echo "[install] Installing python3.12-venv system package..."
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3.12-venv
fi

# Create the virtualenv if it does not already exist.
if [ ! -x "$VENV/bin/python" ]; then
  echo "[install] Creating virtualenv at $VENV"
  "$PY" -m venv "$VENV"
fi

echo "[install] Upgrading pip"
"$VENV/bin/python" -m pip install --upgrade pip -q

echo "[install] Installing core + plc-modbus (editable)"
"$VENV/bin/pip" install -q \
  -e "core/[dev,otel]" \
  -e "services/plc-modbus/[backend,dev]"

echo "[install] Done. Python: $("$VENV/bin/python" --version)"
