"""Configuration for PLC client."""

import os

PLC_TYPE = os.getenv("PLC_TYPE", "micro820")
PLC_HOST = os.getenv("PLC_HOST", "192.168.1.100")
PLC_PORT = int(os.getenv("PLC_PORT", "502"))
PLC_TIMEOUT = int(os.getenv("PLC_TIMEOUT", "5"))
