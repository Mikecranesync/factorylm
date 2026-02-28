"""Discord bot event handlers.

Extracted from services/discord-adapter/bot.py:372-406 on_ready lifecycle.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from factorylm.models import FactoryLMConfig

logger = logging.getLogger(__name__)


def setup_events(
    client: discord.Client,
    tree: app_commands.CommandTree,
    config: FactoryLMConfig,
) -> None:
    """Register event handlers on the Discord client."""
    guild = discord.Object(id=config.discord.guild_id)

    @client.event
    async def on_ready():
        # Sync commands to the configured guild only
        synced = await tree.sync(guild=guild)
        logger.info("Synced %d slash commands to guild %s", len(synced), config.discord.guild_id)
        logger.info("Bot is online as %s", client.user)
        logger.info("  Guild ID: %s", config.discord.guild_id)
        logger.info("  Agents: %s", list(config.discord.agents.keys()))
        logger.info(
            "  Relay: %s:%s", config.relay.host, config.relay.port
        )

    @tree.error
    async def on_application_command_error(
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ):
        logger.exception("Command error: %s", error)
        embed = discord.Embed(
            title="Command Error",
            description=str(error)[:200],
            color=discord.Color.red(),
        )
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.HTTPException:
            logger.warning("Failed to send error embed to user")
