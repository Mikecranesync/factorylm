#!/bin/bash
set -e

echo "=== Building PLC Reader for macOS ==="
echo

# ── Resolve monorepo root (two levels up from _BUILDS/plc-reader/) ──
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MONOREPO="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "Monorepo root: $MONOREPO"

# ── Check source files exist ──
if [ ! -f "$MONOREPO/apps/plc-reader/app.py" ]; then
    echo "ERROR: apps/plc-reader/app.py not found.  Are you on the right branch?"
    exit 1
fi
if [ ! -f "$MONOREPO/packages/factorylm-cli/src/factorylm/plc/__init__.py" ]; then
    echo "ERROR: packages/factorylm-cli/src/factorylm/plc/ not found."
    exit 1
fi

# ── Install dependencies ──
echo
echo "[1/3] Installing dependencies..."
pip install -r "$SCRIPT_DIR/requirements.txt"
pip install pyinstaller

# ── Build ──
echo
echo "[2/3] Running PyInstaller..."
python -m PyInstaller \
    --name "PLC-Reader" \
    --onefile \
    --windowed \
    --collect-all nicegui \
    --exclude-module matplotlib \
    --exclude-module scipy \
    --exclude-module pandas \
    --add-data "$MONOREPO/apps/plc-reader:plc_reader" \
    --add-data "$MONOREPO/packages/factorylm-cli/src:plc_lib" \
    "$SCRIPT_DIR/main.py"

# ── Done ──
echo
if [ -f dist/PLC-Reader ] || [ -d dist/PLC-Reader.app ]; then
    echo "[3/3] SUCCESS!"
    ls -lh dist/PLC-Reader* 2>/dev/null
else
    echo "[3/3] FAILED — check the PyInstaller output above."
    exit 1
fi
