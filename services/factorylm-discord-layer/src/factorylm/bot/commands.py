"""Discord bot slash commands.

Guild-only commands for the FactoryLM agent swarm:
- /relay <agent> <message> — post via relay daemon
- /status — relay daemon status
- /config show — ephemeral config overview (hides secrets)
- /fleet — agent fleet roster
"""

from __future__ import annotations

import logging

import aiohttp
import discord
from discord import app_commands

from factorylm.models import FactoryLMConfig

logger = logging.getLogger(__name__)

# Fleet roster for /fleet command
FLEET_TABLE = """\
```
Agent    | Machine                    | Role
---------|----------------------------|-----------------------
Tony     | Mac Mini (100.108.19.94)   | Boss agent, coordinator
Ultron   | DO VPS (100.68.120.99)     | Cloud reasoning, research
Jarvis   | Travel Laptop (100.83.251.23) | PLC/Modbus edge
Hetzner  | Hetzner (100.67.25.53)     | Batch compute (pending)
```"""


def create_commands(
    tree: app_commands.CommandTree,
    config: FactoryLMConfig,
) -> None:
    """Register all slash commands on the command tree.

    All commands are guild-only, scoped to config.discord.guild_id.
    """
    guild = discord.Object(id=config.discord.guild_id)
    relay_url = f"http://{config.relay.host}:{config.relay.port}"

    @tree.command(
        name="relay", description="Post a message to an agent's Discord channel", guild=guild
    )
    @app_commands.describe(agent="Agent name (e.g. tony, ultron)", message="Message to send")
    async def cmd_relay(interaction: discord.Interaction, agent: str, message: str):
        await interaction.response.defer(thinking=True)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{relay_url}/relay",
                    json={"agent": agent.lower(), "message": message},
                ) as resp:
                    data = await resp.json()

                    if resp.status == 202:
                        embed = discord.Embed(
                            title="Message Queued",
                            description=f"Sent to **{agent}** via relay",
                            color=discord.Color.green(),
                        )
                        embed.add_field(name="Queue Depth", value=str(data.get("queue_depth", 0)))
                    elif resp.status == 404:
                        embed = discord.Embed(
                            title="Unknown Agent",
                            description=data.get("error", "Agent not found"),
                            color=discord.Color.red(),
                        )
                        known = data.get("known_agents", [])
                        if known:
                            embed.add_field(name="Known Agents", value=", ".join(known))
                    else:
                        embed = discord.Embed(
                            title="Relay Error",
                            description=data.get("error", f"HTTP {resp.status}"),
                            color=discord.Color.red(),
                        )
        except aiohttp.ClientError:
            embed = discord.Embed(
                title="Relay Unreachable",
                description=f"Cannot connect to relay at {relay_url}",
                color=discord.Color.red(),
            )

        await interaction.followup.send(embed=embed)

    @tree.command(name="status", description="Check relay daemon status", guild=guild)
    async def cmd_status(interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{relay_url}/status") as resp:
                    data = await resp.json()

            embed = discord.Embed(
                title="Relay Status",
                color=discord.Color.green(),
            )
            embed.add_field(
                name="Uptime", value=f"{data.get('uptime_seconds', 0):.0f}s", inline=True
            )
            embed.add_field(
                name="Messages Relayed", value=str(data.get("messages_relayed", 0)), inline=True
            )
            embed.add_field(
                name="Queue Depth", value=str(data.get("queue_depth", 0)), inline=True
            )

            agents = data.get("agents", {})
            if agents:
                agent_lines = []
                for name, info in agents.items():
                    role = info.get("role", "")
                    agent_lines.append(f"**{name}**: {role}")
                embed.add_field(
                    name="Agents", value="\n".join(agent_lines), inline=False
                )
        except aiohttp.ClientError:
            embed = discord.Embed(
                title="Relay Unreachable",
                description=f"Cannot connect to relay at {relay_url}",
                color=discord.Color.red(),
            )

        await interaction.followup.send(embed=embed)

    config_group = app_commands.Group(
        name="config",
        description="Configuration commands",
        guild_ids=[config.discord.guild_id],
    )

    @config_group.command(name="show", description="Show current configuration (ephemeral)")
    async def cmd_config_show(interaction: discord.Interaction):
        embed = discord.Embed(
            title="FactoryLM Configuration",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="Guild ID", value=str(config.discord.guild_id), inline=True
        )
        embed.add_field(
            name="Relay", value=f"{config.relay.host}:{config.relay.port}", inline=True
        )
        embed.add_field(
            name="Log Level", value=config.relay.log_level, inline=True
        )

        # List agents WITHOUT webhook URLs (security)
        agent_lines = []
        for name, agent_cfg in config.discord.agents.items():
            agent_lines.append(f"**{name}**: ch={agent_cfg.channel_id}, {agent_cfg.machine}")
        if agent_lines:
            embed.add_field(
                name="Agents", value="\n".join(agent_lines), inline=False
            )

        # Ephemeral — only the caller sees it
        await interaction.response.send_message(embed=embed, ephemeral=True)

    tree.add_command(config_group)

    @tree.command(name="fleet", description="Show the FactoryLM agent fleet", guild=guild)
    async def cmd_fleet(interaction: discord.Interaction):
        embed = discord.Embed(
            title="FactoryLM Fleet",
            description=FLEET_TABLE,
            color=discord.Color.blue(),
        )
        await interaction.response.send_message(embed=embed)


def cli_main() -> None:
    """Entry point for factorylm-bot command."""
    import sys

    from factorylm.bot.events import setup_events
    from factorylm.config import ConfigError, get_bot_token, load_config

    try:
        config = load_config()
        token = get_bot_token(config)
    except ConfigError as exc:
        print(f"Config error: {exc}")
        sys.exit(1)

    logging.basicConfig(
        level=getattr(logging, config.relay.log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)

    create_commands(tree, config)
    setup_events(client, tree, config)

    client.run(token, log_handler=None)
