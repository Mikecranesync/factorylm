"""Discord bot event handlers.

Extracted from services/discord-adapter/bot.py:372-406 on_ready lifecycle.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from factorylm.config import get_all_guild_ids
from factorylm.models import FactoryLMConfig

logger = logging.getLogger(__name__)


def setup_events(
    client: discord.Client,
    tree: app_commands.CommandTree,
    config: FactoryLMConfig,
) -> None:
    """Register event handlers on the Discord client."""
    guild_ids = get_all_guild_ids(config)
    # Fallback to legacy single guild
    if not guild_ids and config.discord.guild_id:
        guild_ids = [config.discord.guild_id]

    @client.event
    async def on_ready():
        # Sync commands to ALL configured guilds
        total_synced = 0
        for gid in guild_ids:
            guild_obj = discord.Object(id=gid)
            try:
                # Copy the primary guild's commands to this guild
                tree.copy_global_to(guild=guild_obj)
                synced = await tree.sync(guild=guild_obj)
                total_synced += len(synced)
                logger.info("Synced %d commands to guild %s", len(synced), gid)
            except discord.HTTPException as exc:
                logger.warning("Failed to sync commands to guild %s: %s", gid, exc)

        logger.info("Bot is online as %s", client.user)
        logger.info("  Guilds: %s", guild_ids)
        logger.info("  Total commands synced: %d across %d guilds", total_synced, len(guild_ids))
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
