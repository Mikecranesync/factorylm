#!/usr/bin/env python3
"""PLC Reader — standalone launcher.

Works in two modes:
  1. Development: resolves monorepo paths relative to this file
  2. PyInstaller frozen: finds bundled data via sys._MEIPASS

Usage (dev):
    python _BUILDS/plc-reader/main.py

Usage (frozen .exe / .app):
    dist/PLC-Reader
"""

import os
import runpy
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))

if getattr(sys, "frozen", False):
    # ── PyInstaller bundle ──
    _BASE = sys._MEIPASS  # type: ignore[attr-defined]
    # PLC drivers bundled under plc_lib/
    sys.path.insert(0, os.path.join(_BASE, "plc_lib"))
    _APP_FILE = os.path.join(_BASE, "plc_reader", "app.py")
else:
    # ── Development (running from source) ──
    _MONOREPO = os.path.abspath(os.path.join(_HERE, "..", ".."))
    _APP_FILE = os.path.join(_MONOREPO, "apps", "plc-reader", "app.py")
    # PLC drivers — app.py also adds this, but we do it first for clarity
    sys.path.insert(0, os.path.join(_MONOREPO, "packages", "factorylm-cli", "src"))

if not os.path.isfile(_APP_FILE):
    print(f"ERROR: Cannot find app.py at {_APP_FILE}", file=sys.stderr)
    sys.exit(1)

# Run the app as __main__ so its `if __name__ == '__main__': ui.run(...)` fires
runpy.run_path(_APP_FILE, run_name="__main__")
