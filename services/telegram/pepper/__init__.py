"""
PEPPER Telegram Bot Gateway

A dual-mode Telegram bot system for FactoryLM:
- God Mode: Full access for internal team (Mike)
- Demo Mode: Guardrailed access for customers

Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "FactoryLM Team"

from .modes import UserMode, get_user_mode, ModeConfig
from .gateway import PepperGateway

__all__ = [
    "UserMode",
    "get_user_mode",
    "ModeConfig",
    "PepperGateway",
]
