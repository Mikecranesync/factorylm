"""
PEPPER Persona System

Multi-persona architecture for context-aware AI behavior:
- SOUL_GOD.md: Pepper Prime for Mike (unrestricted)
- SOUL_DEMO.md: Pepper for customers (guardrails)

Each persona defines identity, voice, capabilities, and boundaries.
"""

from .models import Persona, UserMode
from .loader import PersonaLoader
from .formatter import ResponseFormatter

__all__ = [
    "Persona",
    "UserMode",
    "PersonaLoader",
    "ResponseFormatter",
]
