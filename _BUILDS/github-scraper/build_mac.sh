#!/bin/bash
set -e

echo "=== Building GitHub Scraper for macOS ==="
echo

# ── Resolve monorepo root (two levels up from _BUILDS/github-scraper/) ──
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MONOREPO="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "Monorepo root: $MONOREPO"

# ── Check source files exist ──
if [ ! -f "$MONOREPO/apps/github-scraper/app.py" ]; then
    echo "ERROR: apps/github-scraper/app.py not found.  Are you on the right branch?"
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
    --name "GitHub-Scraper" \
    --onefile \
    --windowed \
    --collect-all nicegui \
    --exclude-module matplotlib \
    --exclude-module scipy \
    --exclude-module pandas \
    --exclude-module pymodbus \
    --exclude-module snap7 \
    --add-data "$MONOREPO/apps/github-scraper:github_scraper" \
    "$SCRIPT_DIR/main.py"

# ── Done ──
echo
if [ -f dist/GitHub-Scraper ] || [ -d dist/GitHub-Scraper.app ]; then
    echo "[3/3] SUCCESS!"
    ls -lh dist/GitHub-Scraper* 2>/dev/null
else
    echo "[3/3] FAILED — check the PyInstaller output above."
    exit 1
fi
