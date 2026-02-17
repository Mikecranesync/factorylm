"""Shared types for the OpenClaw toolkit."""

from __future__ import annotations

from enum import Enum


class Intent(str, Enum):
    """Message intent classification."""

    WIRING_RECONSTRUCT = "WIRING_RECONSTRUCT"
    KB_ENRICH_COMPONENT = "KB_ENRICH_COMPONENT"
    DIAGNOSE = "DIAGNOSE"
    STATUS = "STATUS"
    IO = "IO"
    GENERAL = "GENERAL"
