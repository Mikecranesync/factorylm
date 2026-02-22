"""
Daily progress scheduler for FactoryLM Discord bot.

Posts an auto-generated progress embed to a configured channel once per day,
showing recent git commits and a countdown to the Cosmos Cookoff deadline.
"""

import datetime
import logging
import subprocess

import discord
from discord.ext import tasks

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
