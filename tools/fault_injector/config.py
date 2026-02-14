"""
Fault Injector Configuration
============================
All configuration via environment variables with sensible defaults.
"""

import os

# PLC Laptop (via Tailscale)
PLC_HOST = os.getenv("PLC_HOST", "100.72.2.99")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "502"))

# Services on PLC laptop
MATRIX_API = os.getenv("MATRIX_API", f"http://{PLC_HOST}:8000")
DEMO_UI = os.getenv("DEMO_UI", f"http://{PLC_HOST}:8080")
JARVIS_NODE = os.getenv("JARVIS_NODE", f"http://{PLC_HOST}:8765")

# SSH for remote commands (Factory I/O start/stop)
SSH_USER = os.getenv("SSH_USER", "hharp")
SSH_HOST = os.getenv("SSH_HOST", PLC_HOST)

# Factory I/O paths on PLC laptop
FACTORY_IO_EXE = os.getenv(
    "FACTORY_IO_EXE",
    r"C:\Program Files\Real Games\Factory IO\Factory IO.exe"
)
FACTORY_IO_SCENES = os.getenv(
    "FACTORY_IO_SCENES",
    r"C:\Users\hharp\Documents\Factory IO\My Scenes"
)

# Default scene
DEFAULT_SCENE = os.getenv("DEFAULT_SCENE", "Sorting by Height (Advanced)")

# Timing
FAULT_HOLD_SECONDS = int(os.getenv("FAULT_HOLD_SECONDS", "30"))
POLL_INTERVAL_MS = int(os.getenv("POLL_INTERVAL_MS", "500"))
