"""FactoryLM Discord bot — slash commands backed by local TagStore.

Extracted from services/discord-adapter/bot.py, adapted to read from
local SQLite instead of remote Matrix API.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

import discord
from discord import app_commands

from factorylm.cosmos.client import CosmosClient
from factorylm.cosmos.models import CosmosInsight
from factorylm.db.store import TagStore
from factorylm.discord.embeds import (
    build_about_embed,
    build_insight_embed,
    build_status_embed,
    build_tags_embed,
)

logger = logging.getLogger(__name__)

FAULT_CHOICES = [
    app_commands.Choice(name="Conveyor Jam", value="jam"),
    app_commands.Choice(name="Motor Overload", value="overload"),
    app_commands.Choice(name="Overheat", value="overheat"),
    app_commands.Choice(name="Sensor Failure", value="sensor"),
    app_commands.Choice(name="E-Stop", value="estop"),
    app_commands.Choice(name="Comm Loss", value="commloss"),
]

FAULT_TO_ERROR_CODE = {
    "jam": 3, "overload": 1, "overheat": 2,
    "sensor": 4, "estop": -1, "commloss": 5,
}


class FactoryLMBot:
    """Manages the Discord client, command tree, and TagStore reference."""

    def __init__(
        self,
        token: str,
        store: TagStore,
        bot_name: str = "FactoryLM",
        mention_only: bool = True,
    ) -> None:
        self.token = token
        self.store = store
        self.bot_name = bot_name
        self.mention_only = mention_only
        self.cosmos = CosmosClient()

        intents = discord.Intents.default()
        intents.message_content = True
        self.client = discord.Client(intents=intents)
        self.tree = app_commands.CommandTree(self.client)

        self._register_commands()
        self._register_events()

    def _register_commands(self) -> None:
        tree = self.tree

        @tree.command(name="tags", description="Show live PLC tag values")
        async def cmd_tags(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            tags = self.store.get_latest_tags()
            embed = build_tags_embed(tags)
            await interaction.followup.send(embed=embed)

        @tree.command(name="diagnose", description="AI-powered fault diagnosis via Cosmos Reason 2")
        @app_commands.describe(fault="Type of fault to diagnose")
        @app_commands.choices(fault=FAULT_CHOICES)
        async def cmd_diagnose(interaction: discord.Interaction, fault: app_commands.Choice[str]):
            await interaction.response.defer(thinking=True)
            error_code = FAULT_TO_ERROR_CODE.get(fault.value, 0)
            real_tags = self.store.get_latest_tags()
            if real_tags is not None:
                tags = dict(real_tags)
                tags["error_code"] = error_code
                data_source = "live"
            else:
                tags = {"error_code": error_code}
                data_source = "synthetic"

            loop = asyncio.get_running_loop()
            insight = await loop.run_in_executor(
                None,
                lambda: self.cosmos.analyze_incident(
                    incident_id=f"discord-{uuid.uuid4().hex[:8]}",
                    node_id="local",
                    tags=tags,
                ),
            )
            embed = build_insight_embed(insight, data_source=data_source)
            await interaction.followup.send(embed=embed)

        @tree.command(name="about", description="What is FactoryLM?")
        async def cmd_about(interaction: discord.Interaction):
            embed = build_about_embed()
            await interaction.response.send_message(embed=embed)

        @tree.command(name="status", description="Show system status")
        async def cmd_status(interaction: discord.Interaction):
            latest = self.store.get_latest(1)
            incidents = self.store.get_incidents(status="open", limit=5)
            desc = f"Tags: {len(latest)} snapshots | Open incidents: {len(incidents)}"
            embed = discord.Embed(
                title="FactoryLM Status",
                description=desc,
                color=discord.Color.green() if not incidents else discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed)

    def _register_events(self) -> None:
        @self.client.event
        async def on_ready():
            synced = await self.tree.sync()
            logger.info("%s online — synced %d commands", self.bot_name, len(synced))

        @self.client.event
        async def on_message(message: discord.Message):
            if message.author == self.client.user or message.author.bot:
                return
            if self.mention_only and self.client.user not in message.mentions:
                return
            # Acknowledge with a reaction
            await message.add_reaction("\U0001f44d")

    def run(self) -> None:
        """Start the bot (blocking)."""
        self.client.run(self.token, log_handler=None)

    async def start(self) -> None:
        """Start the bot (async)."""
        await self.client.start(self.token)

    async def close(self) -> None:
        """Gracefully close the bot."""
        await self.client.close()
