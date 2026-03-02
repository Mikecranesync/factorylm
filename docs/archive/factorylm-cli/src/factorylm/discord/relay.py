"""Agent relay — posts to Discord channels via webhooks.

Each agent (Tony, Ultron, Jarvis, etc.) gets a dedicated Discord channel.
The relay uses Discord webhooks to post messages as the agent's name,
keeping all coordination visible and auditable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import aiohttp
import discord

logger = logging.getLogger(__name__)


@dataclass
class RelayMessage:
    """A message to post to an agent's Discord channel."""

    agent: str
    content: str = ""
    embed: discord.Embed | None = None


class AgentRelay:
    """Posts messages to Discord channels via webhooks.

    One webhook per agent channel, plus optional webhooks for
    #alerts and #dispatch-log.
    """

    def __init__(
        self,
        agent_webhooks: dict[str, str] | None = None,
        alerts_webhook: str = "",
        dispatch_webhook: str = "",
    ) -> None:
        self.agent_webhooks: dict[str, str] = {
            k: v for k, v in (agent_webhooks or {}).items() if v
        }
        self.alerts_webhook = alerts_webhook
        self.dispatch_webhook = dispatch_webhook
        self._session: aiohttp.ClientSession | None = None

    @property
    def configured_agents(self) -> list[str]:
        """Return list of agent names with configured webhooks."""
        return list(self.agent_webhooks.keys())

    @property
    def has_alerts(self) -> bool:
        return bool(self.alerts_webhook)

    @property
    def has_dispatch(self) -> bool:
        return bool(self.dispatch_webhook)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def post(self, message: RelayMessage) -> bool:
        """Post a message to an agent's channel via webhook.

        Returns True if the message was sent successfully.
        """
        url = self.agent_webhooks.get(message.agent)
        if not url:
            logger.warning("No webhook configured for agent '%s'", message.agent)
            return False

        return await self._send_webhook(
            url,
            content=message.content,
            embed=message.embed,
            username=message.agent.capitalize(),
        )

    async def post_alert(self, embed: discord.Embed) -> bool:
        """Post an alert embed to the #alerts channel."""
        if not self.alerts_webhook:
            logger.debug("No alerts webhook configured — skipping alert post")
            return False

        return await self._send_webhook(
            self.alerts_webhook,
            embed=embed,
            username="FactoryLM Alerts",
        )

    async def post_dispatch(self, embed: discord.Embed) -> bool:
        """Post a dispatch embed to the #dispatch-log channel."""
        if not self.dispatch_webhook:
            logger.debug("No dispatch webhook configured — skipping dispatch post")
            return False

        return await self._send_webhook(
            self.dispatch_webhook,
            embed=embed,
            username="Dispatch Log",
        )

    async def _send_webhook(
        self,
        url: str,
        *,
        content: str = "",
        embed: discord.Embed | None = None,
        username: str = "FactoryLM",
    ) -> bool:
        """Send a message via Discord webhook."""
        try:
            session = await self._get_session()
            webhook = discord.Webhook.from_url(url, session=session)
            kwargs: dict[str, Any] = {"username": username, "wait": True}
            if content:
                kwargs["content"] = content
            if embed:
                kwargs["embed"] = embed
            await webhook.send(**kwargs)
            return True
        except Exception:
            logger.exception("Failed to send webhook to %s", url[:50])
            return False

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
