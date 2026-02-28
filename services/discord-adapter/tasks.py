"""
Scheduled tasks for FactoryLM Discord bot.

DailyProgress — posts git commits + countdown to Cosmos Cookoff deadline.
DailyHealthReport — posts combined PLC / node / conveyor health embed at 7 AM ET.
"""

import asyncio
import datetime
import logging
import subprocess
from collections.abc import Callable, Coroutine
from typing import Any
from zoneinfo import ZoneInfo

import discord
from discord.ext import tasks

from channels import DiscordChannels
from embeds import build_health_report_embed, build_ops_hub_summary

logger = logging.getLogger("discord-adapter.tasks")

COOKOFF_DEADLINE = datetime.date(2026, 2, 26)


def _get_recent_commits(count: int = 5) -> list[str]:
    """Get recent git log one-liners via subprocess."""
    try:
        result = subprocess.run(
            ["git", "log", f"-{count}", "--oneline", "--no-decorate"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().splitlines()
    except Exception as e:
        logger.warning("Could not read git log: %s", e)
    return ["(no git history available)"]


def _days_until_deadline() -> int:
    return (COOKOFF_DEADLINE - datetime.date.today()).days


def build_progress_embed() -> discord.Embed:
    """Build the daily progress embed."""
    days_left = _days_until_deadline()

    if days_left > 0:
        title = f"Cosmos Cookoff — {days_left} day{'s' if days_left != 1 else ''} left"
        color = discord.Color.green() if days_left > 3 else discord.Color.yellow()
    elif days_left == 0:
        title = "Cosmos Cookoff — SUBMISSION DAY"
        color = discord.Color.red()
    else:
        title = "Cosmos Cookoff — Post-submission"
        color = discord.Color.light_grey()

    embed = discord.Embed(
        title=title,
        color=color,
        timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
    )

    commits = _get_recent_commits()
    commit_text = "\n".join(f"`{c}`" for c in commits)
    embed.add_field(name="Recent Commits", value=commit_text[:1024], inline=False)

    embed.set_footer(text="FactoryLM daily progress")
    return embed


class DailyProgress:
    """Manages the daily progress posting loop."""

    def __init__(self, client: discord.Client, channel_id: int) -> None:
        self.client = client
        self.channel_id = channel_id
        self._task = self._create_loop()

    def _create_loop(self):
        @tasks.loop(hours=24)
        async def _post():
            channel = self.client.get_channel(self.channel_id)
            if channel is None:
                logger.warning("Progress channel %s not found", self.channel_id)
                return
            embed = build_progress_embed()
            await channel.send(embed=embed)
            logger.info("Posted daily progress to #%s", channel.name)

        @_post.before_loop
        async def _wait_ready():
            await self.client.wait_until_ready()

        return _post

    def start(self) -> None:
        self._task.start()

    def stop(self) -> None:
        self._task.cancel()


# Type alias for the async fetch callables passed in from bot.py
FetchCallable = Callable[[], Coroutine[Any, Any, Any]]

# 7 AM Eastern (DST-aware)
_HEALTH_TIME = datetime.time(hour=7, tzinfo=ZoneInfo("America/New_York"))


class DailyHealthReport:
    """Posts a combined PLC / node / conveyor health report daily at 7 AM ET.

    Multi-channel routing:
    - If line_1_health is configured: full report there, compact summary to ops_hub
    - If only ops_hub is configured: full report goes directly to ops_hub
    - If neither is configured: logs warning and skips
    """

    def __init__(
        self,
        client: discord.Client,
        channels: DiscordChannels,
        fetch_nodes: FetchCallable,
        fetch_tags: FetchCallable,
        fetch_conveyor: FetchCallable,
        fetch_incidents: FetchCallable,
    ) -> None:
        self.client = client
        self.channels = channels
        self._fetch_nodes = fetch_nodes
        self._fetch_tags = fetch_tags
        self._fetch_conveyor = fetch_conveyor
        self._fetch_incidents = fetch_incidents
        self._task = self._create_loop()

    def _create_loop(self):
        @tasks.loop(time=_HEALTH_TIME)
        async def _post():
            nodes, tags, conveyor, incidents = await asyncio.gather(
                self._fetch_nodes(),
                self._fetch_tags(),
                self._fetch_conveyor(),
                self._fetch_incidents(),
            )

            ops_hub_id = self.channels.ops_hub
            detail_id = self.channels.line_1_health

            if detail_id:
                # Post full report to line-1-health
                detail_ch = self.client.get_channel(detail_id)
                if detail_ch is not None:
                    full_embed = build_health_report_embed(
                        nodes, tags, conveyor, incidents,
                        footer_extra="Posted from #factory-ops-hub",
                    )
                    await detail_ch.send(embed=full_embed)
                    logger.info("Full health report posted to #%s", detail_ch.name)
                else:
                    logger.warning("line_1_health channel %s not found", detail_id)

                # Post compact summary to ops_hub with pointer
                if ops_hub_id:
                    hub_ch = self.client.get_channel(ops_hub_id)
                    if hub_ch is not None:
                        summary = build_ops_hub_summary(
                            nodes, tags, conveyor, incidents,
                            detail_channel_id=detail_id,
                        )
                        await hub_ch.send(embed=summary)
                        logger.info("Health summary posted to #%s", hub_ch.name)
                    else:
                        logger.warning("ops_hub channel %s not found", ops_hub_id)

            elif ops_hub_id:
                # Only ops_hub configured — full report goes there
                hub_ch = self.client.get_channel(ops_hub_id)
                if hub_ch is not None:
                    full_embed = build_health_report_embed(nodes, tags, conveyor, incidents)
                    await hub_ch.send(embed=full_embed)
                    logger.info("Full health report posted to #%s", hub_ch.name)
                else:
                    logger.warning("ops_hub channel %s not found", ops_hub_id)

            else:
                logger.warning("No health report channels configured — skipping")

        @_post.before_loop
        async def _wait_ready():
            await self.client.wait_until_ready()

        return _post

    def start(self) -> None:
        self._task.start()

    def stop(self) -> None:
        self._task.cancel()
