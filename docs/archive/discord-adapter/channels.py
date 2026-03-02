"""
Central Discord channel configuration for FactoryLM Ops Hub.

All channel IDs and routing logic live here — no more scattered os.getenv() calls.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger("discord-adapter.channels")

# Workflow → (primary_attr, fallback_attr) routing table
_ROUTING: dict[str, tuple[str, str | None]] = {
    "health_summary": ("ops_hub", None),
    "health_detail": ("line_1_health", "ops_hub"),
    "incident_toast": ("ops_hub", None),
    "incident": ("incidents", "ops_hub"),
    "maintenance": ("maintenance", "ops_hub"),
    "progress": ("progress", "ops_hub"),
}


@dataclass(frozen=True)
class DiscordChannels:
    """Immutable snapshot of all configured Discord channel IDs."""

    ops_hub: int = 0
    line_1_health: int = 0
    incidents: int = 0
    maintenance: int = 0
    progress: int = 0
    allowed_channels: list[int] | None = field(default=None)

    @classmethod
    def from_env(cls) -> DiscordChannels:
        """Build from environment variables (Doppler-injected or local .env)."""

        def _int(var: str, *aliases: str) -> int:
            for name in (var, *aliases):
                raw = os.getenv(name, "").strip()
                if raw:
                    try:
                        return int(raw)
                    except ValueError:
                        logger.warning("Invalid channel ID for %s: %r", name, raw)
            return 0

        # DISCORD_HEALTH_CHANNEL_ID is a legacy alias for ops_hub
        ops_hub = _int("DISCORD_OPS_HUB_CHANNEL_ID", "DISCORD_HEALTH_CHANNEL_ID")

        # Parse allowed channels list
        allowed_raw = os.getenv("DISCORD_ALLOWED_CHANNELS", "").strip()
        allowed: list[int] | None = None
        if allowed_raw:
            allowed = [int(x) for x in allowed_raw.split(",") if x.strip()]

        channels = cls(
            ops_hub=ops_hub,
            line_1_health=_int("DISCORD_LINE_1_HEALTH_CHANNEL_ID"),
            incidents=_int("DISCORD_INCIDENTS_CHANNEL_ID"),
            maintenance=_int("DISCORD_MAINTENANCE_CHANNEL_ID"),
            progress=_int("DISCORD_PROGRESS_CHANNEL_ID"),
            allowed_channels=allowed,
        )

        # Startup logging
        for name in ("ops_hub", "line_1_health", "incidents", "maintenance", "progress"):
            val = getattr(channels, name)
            if val:
                logger.info("Channel %s = %s", name, val)
            else:
                logger.debug("Channel %s not configured", name)

        return channels

    def get_target(self, workflow: str) -> int | None:
        """Return the target channel ID for a workflow, or None if nothing configured.

        Uses the routing table: primary channel first, then fallback.
        Unknown workflows default to ops_hub.
        """
        primary_attr, fallback_attr = _ROUTING.get(workflow, ("ops_hub", None))

        primary = getattr(self, primary_attr, 0)
        if primary:
            return primary

        if fallback_attr:
            fallback = getattr(self, fallback_attr, 0)
            if fallback:
                return fallback

        logger.warning("No channel configured for workflow %r", workflow)
        return None
