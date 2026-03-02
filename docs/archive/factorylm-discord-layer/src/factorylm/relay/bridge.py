"""Telegram <-> Discord message format bridge.

Handles markdown conversion, truncation, and embed building.
Truncation logic extracted from services/discord-adapter/bot.py:451-467 split_message().
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

# Severity → Discord embed color (decimal)
SEVERITY_COLORS = {
    "info": 0x2ECC71,       # green
    "warning": 0xF1C40F,    # yellow
    "critical": 0xE74C3C,   # red
}

DEFAULT_COLOR = 0x3498DB  # blue


class MessageBridge:
    """Converts messages between Telegram and Discord formats."""

    @staticmethod
    def telegram_to_discord(text: str) -> str:
        """Convert Telegram markdown to Discord markdown.

        Telegram:  *bold*  _italic_  `code`  ```pre```
        Discord:   **bold**  *italic*  `code`  ```pre```

        Also strips HTML tags.
        """
        # Strip HTML tags first
        text = re.sub(r"<[^>]+>", "", text)

        # Protect code blocks and inline code from further processing
        code_blocks: list[str] = []

        def _save_code_block(m: re.Match) -> str:
            code_blocks.append(m.group(0))
            return f"\x00CODE{len(code_blocks) - 1}\x00"

        text = re.sub(r"```[\s\S]*?```", _save_code_block, text)
        text = re.sub(r"`[^`]+`", _save_code_block, text)

        # Convert Telegram bold *text* → Discord bold **text**
        # Avoid matching ** (already Discord bold) or * in URLs
        text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"**\1**", text)

        # Convert Telegram italic _text_ → Discord italic *text*
        # Avoid matching __ (Discord underline) or _ in identifiers
        text = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"*\1*", text)

        # Restore code blocks
        for i, block in enumerate(code_blocks):
            text = text.replace(f"\x00CODE{i}\x00", block)

        return text

    @staticmethod
    def truncate(text: str, limit: int = 1900) -> str:
        """Truncate text to fit Discord's 2000-char limit.

        Extracted from split_message() in bot.py:451-467, refactored to:
        - Split on newline boundaries when possible
        - Append a suffix showing how many chars were omitted
        """
        if len(text) <= limit:
            return text

        # Try to split at a newline before the limit
        suffix_template = "\n...[truncated, {} chars omitted]"
        # Reserve space for suffix (max ~40 chars)
        cut_limit = limit - 45

        split_at = text.rfind("\n", 0, cut_limit)
        if split_at == -1:
            split_at = cut_limit

        truncated = text[:split_at]
        omitted = len(text) - len(truncated)
        suffix = suffix_template.format(omitted)

        return truncated + suffix

    @staticmethod
    def build_embed(
        title: str,
        description: str = "",
        color: int = DEFAULT_COLOR,
        fields: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Build a Discord embed payload dict.

        Args:
            title: Embed title.
            description: Embed description/body text.
            color: Embed color as integer.
            fields: List of {name, value, inline} dicts.

        Returns:
            Dict suitable for Discord webhook embed payload.
        """
        embed: dict[str, Any] = {"title": title, "color": color}
        if description:
            embed["description"] = description
        if fields:
            embed["fields"] = [
                {
                    "name": f.get("name", ""),
                    "value": f.get("value", ""),
                    "inline": f.get("inline", False),
                }
                for f in fields
            ]
        return embed

    @staticmethod
    def build_alert_embed(
        agent: str,
        message: str,
        severity: str = "info",
    ) -> dict[str, Any]:
        """Build an alert embed with severity-based color.

        Args:
            agent: Name of the agent sending the alert.
            message: Alert message body.
            severity: One of "info", "warning", "critical".

        Returns:
            Discord embed payload dict with timestamp and agent footer.
        """
        color = SEVERITY_COLORS.get(severity.lower(), DEFAULT_COLOR)
        now = datetime.now(timezone.utc).isoformat()

        return {
            "title": f"Alert: {severity.upper()}",
            "description": message,
            "color": color,
            "timestamp": now,
            "footer": {"text": f"Agent: {agent}"},
        }
