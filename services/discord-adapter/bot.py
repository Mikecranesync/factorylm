"""
FactoryLM Discord Adapter — Cosmos Cookoff community bot.

Bridges Discord messages to the OpenClaw gateway so Jarvis can respond
in the NVIDIA Cosmos Cookoff Discord as Mike's presence.

Slash commands:
    /diagnose <fault>  — AI-powered fault diagnosis via Cosmos Reason 2
    /status            — Network health of all FactoryLM nodes
    /about             — What is FactoryLM?
    /tags              — Live PLC tag values from Matrix API
    /conveyor <action> — Live conveyor control (forward/reverse/stop/speed/status)

Usage:
    # With Doppler:
    doppler run --project factorylm --config dev -- python bot.py

    # Or with env vars:
    DISCORD_BOT_TOKEN=xxx python bot.py

Requires: discord.py, httpx
"""

import asyncio
import logging
import os
import sys
import uuid

import discord
from discord import app_commands
import httpx

from cosmos.client import CosmosClient
from embeds import (
    build_about_embed,
    build_conveyor_embed,
    build_insight_embed,
    build_status_embed,
    build_tags_embed,
)
from tasks import DailyProgress

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("discord-adapter")

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
GATEWAY_URL = os.getenv("OPENCLAW_GATEWAY_URL", "http://localhost:18800")
BOT_NAME = os.getenv("DISCORD_BOT_NAME", "FactoryLM")

# Channels the bot is allowed to respond in (empty = all)
ALLOWED_CHANNEL_IDS = [
    int(x) for x in os.getenv("DISCORD_ALLOWED_CHANNELS", "").split(",") if x.strip()
]

# If True, only respond when mentioned. If False, respond to all messages.
MENTION_ONLY = os.getenv("DISCORD_MENTION_ONLY", "true").lower() == "true"

# Channel for daily progress auto-posts (0 = disabled)
PROGRESS_CHANNEL_ID = int(os.getenv("DISCORD_PROGRESS_CHANNEL_ID", "0"))

# Conveyor relay on VPS
CONVEYOR_RELAY_URL = os.getenv("CONVEYOR_RELAY_URL", "http://100.68.120.99:8400")

# Matrix API on PLC Laptop (live tag snapshots from Modbus bridge)
MATRIX_API_URL = os.getenv("MATRIX_API_URL", "http://100.72.2.99:8001")

# Node health endpoints
HEALTH_NODES = {
    "PLC Laptop": "http://100.72.2.99:8765/health",
    "Travel Laptop": "http://100.83.251.23:8765/health",
    "VPS (Jarvis)": "http://100.68.120.99:8765/health",
}

# Fault type choices for /diagnose
FAULT_CHOICES = [
    app_commands.Choice(name="Conveyor Jam", value="jam"),
    app_commands.Choice(name="Motor Overload", value="overload"),
    app_commands.Choice(name="Overheat", value="overheat"),
    app_commands.Choice(name="Sensor Failure", value="sensor"),
    app_commands.Choice(name="E-Stop", value="estop"),
    app_commands.Choice(name="Comm Loss", value="commloss"),
]

# Map fault choice values to stub error codes used by CosmosClient
FAULT_TO_ERROR_CODE = {
    "jam": 3,
    "overload": 1,
    "overheat": 2,
    "sensor": 4,
    "estop": -1,
    "commloss": 5,
}

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Daily progress scheduler (initialized in on_ready if configured)
_daily_progress: DailyProgress | None = None


# ---------------------------------------------------------------------------
# Matrix API helper
# ---------------------------------------------------------------------------


async def _fetch_matrix_tags() -> dict | None:
    """Fetch the latest PLC tag snapshot from Matrix API.

    Returns the most recent snapshot dict, or None on any failure.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
            resp = await http.get(f"{MATRIX_API_URL}/api/tags", params={"limit": 1})
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    return data[0]
                if isinstance(data, dict) and data:
                    return data
            return None
    except Exception:
        logger.debug("Matrix API unreachable at %s", MATRIX_API_URL)
        return None


# ---------------------------------------------------------------------------
# Slash commands
# ---------------------------------------------------------------------------


@tree.command(name="diagnose", description="AI-powered fault diagnosis via Cosmos Reason 2")
@app_commands.describe(fault="Type of fault to diagnose")
@app_commands.choices(fault=FAULT_CHOICES)
async def cmd_diagnose(interaction: discord.Interaction, fault: app_commands.Choice[str]):
    await interaction.response.defer(thinking=True)

    cosmos = CosmosClient()
    error_code = FAULT_TO_ERROR_CODE.get(fault.value, 0)

    # Try real PLC tags first, fall back to synthetic
    real_tags = await _fetch_matrix_tags()
    if real_tags is not None:
        tags = dict(real_tags)
        tags["error_code"] = error_code  # Override to match selected fault
        data_source = "live"
    else:
        # Synthetic fallback — mimics PLC data for the chosen fault
        tags = {"error_code": error_code}
        if fault.value == "estop":
            tags["e_stop"] = True
        elif fault.value == "overload":
            tags["motor_current"] = 12.4
            tags["motor_speed"] = 85
        elif fault.value == "overheat":
            tags["temperature"] = 87.3
        data_source = "synthetic"

    insight = cosmos.analyze_incident(
        incident_id=f"discord-{uuid.uuid4().hex[:8]}",
        node_id="factory-io-line-1",
        tags=tags,
    )

    embed = build_insight_embed(insight, data_source=data_source)
    await interaction.followup.send(embed=embed)


@tree.command(name="status", description="Check FactoryLM network node health")
async def cmd_status(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    nodes: dict[str, dict] = {}
    async with httpx.AsyncClient(timeout=5.0) as http:
        for name, url in HEALTH_NODES.items():
            try:
                resp = await http.get(url)
                nodes[name] = {
                    "url": url,
                    "up": resp.status_code == 200,
                    "latency_ms": int(resp.elapsed.total_seconds() * 1000),
                    "error": None,
                }
            except httpx.ConnectError:
                nodes[name] = {"url": url, "up": False, "latency_ms": None, "error": "Connection refused"}
            except httpx.TimeoutException:
                nodes[name] = {"url": url, "up": False, "latency_ms": None, "error": "Timeout"}
            except Exception as e:
                nodes[name] = {"url": url, "up": False, "latency_ms": None, "error": str(e)[:80]}

    embed = build_status_embed(nodes)
    await interaction.followup.send(embed=embed)


@tree.command(name="about", description="What is FactoryLM?")
async def cmd_about(interaction: discord.Interaction):
    embed = build_about_embed()
    await interaction.response.send_message(embed=embed)


@tree.command(name="tags", description="Show live PLC tag values from the factory floor")
async def cmd_tags(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    tags = await _fetch_matrix_tags()
    embed = build_tags_embed(tags, MATRIX_API_URL)
    await interaction.followup.send(embed=embed)


# ---------------------------------------------------------------------------
# /conveyor — Live conveyor control
# ---------------------------------------------------------------------------

conveyor_group = app_commands.Group(name="conveyor", description="Control the live conveyor belt")


async def _relay_command(action: str, value: float | None = None) -> dict:
    """Send a command to the conveyor relay and return the JSON response."""
    body: dict = {"action": action}
    if value is not None:
        body["value"] = value
    async with httpx.AsyncClient(timeout=10.0) as http:
        resp = await http.post(f"{CONVEYOR_RELAY_URL}/api/command", json=body)
        return resp.json() if resp.status_code == 200 else {"success": False, "message": resp.text[:200]}


async def _relay_status() -> dict:
    """Fetch conveyor status from the relay."""
    async with httpx.AsyncClient(timeout=5.0) as http:
        resp = await http.get(f"{CONVEYOR_RELAY_URL}/api/status")
        return resp.json() if resp.status_code == 200 else {"runState": "offline"}


@conveyor_group.command(name="forward", description="Start conveyor belt forward")
async def cmd_conveyor_forward(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    result = await _relay_command("forward")
    embed = build_conveyor_embed("forward", result, CONVEYOR_RELAY_URL)
    await interaction.followup.send(embed=embed)


@conveyor_group.command(name="reverse", description="Start conveyor belt in reverse")
async def cmd_conveyor_reverse(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    result = await _relay_command("reverse")
    embed = build_conveyor_embed("reverse", result, CONVEYOR_RELAY_URL)
    await interaction.followup.send(embed=embed)


@conveyor_group.command(name="stop", description="Stop the conveyor belt")
async def cmd_conveyor_stop(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    result = await _relay_command("stop")
    embed = build_conveyor_embed("stop", result, CONVEYOR_RELAY_URL)
    await interaction.followup.send(embed=embed)


@conveyor_group.command(name="speed", description="Set conveyor speed (1-60 Hz)")
@app_commands.describe(hz="Speed in Hz (1-60)")
async def cmd_conveyor_speed(interaction: discord.Interaction, hz: int):
    if hz < 1 or hz > 60:
        await interaction.response.send_message("Speed must be between 1 and 60 Hz.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    result = await _relay_command("set_speed", float(hz))
    embed = build_conveyor_embed("set_speed", result, CONVEYOR_RELAY_URL, speed=hz)
    await interaction.followup.send(embed=embed)


@conveyor_group.command(name="status", description="Show current conveyor state")
async def cmd_conveyor_status(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    try:
        status = await _relay_status()
    except Exception:
        status = {"runState": "offline", "error": "Cannot reach relay"}
    embed = build_conveyor_embed("status", status, CONVEYOR_RELAY_URL)
    await interaction.followup.send(embed=embed)


tree.add_command(conveyor_group)


# ---------------------------------------------------------------------------
# Gateway forwarding (existing @mention handler)
# ---------------------------------------------------------------------------


async def forward_to_gateway(user_id: str, username: str, text: str, channel_id: str) -> str:
    """Forward a message to the OpenClaw gateway and return the reply."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as http:
            resp = await http.post(
                f"{GATEWAY_URL}/api/message",
                json={
                    "channel": "discord",
                    "user_id": user_id,
                    "username": username,
                    "text": text,
                    "channel_id": channel_id,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("reply", data.get("response", ""))
            logger.warning("Gateway returned %s: %s", resp.status_code, resp.text[:200])
            return ""
    except httpx.ConnectError:
        logger.error("Cannot connect to OpenClaw gateway at %s", GATEWAY_URL)
        return ""
    except Exception:
        logger.exception("Error forwarding to gateway")
        return ""


@client.event
async def on_ready():
    global _daily_progress

    # Sync slash commands to all guilds
    synced = await tree.sync()
    logger.info("Synced %d slash commands", len(synced))

    logger.info("%s is online as %s", BOT_NAME, client.user)
    logger.info("   Gateway: %s", GATEWAY_URL)
    logger.info("   Matrix API: %s", MATRIX_API_URL)
    logger.info("   Mention-only: %s", MENTION_ONLY)
    logger.info("   Guilds: %s", [g.name for g in client.guilds])

    # Start daily progress scheduler if configured
    if PROGRESS_CHANNEL_ID and _daily_progress is None:
        _daily_progress = DailyProgress(client, PROGRESS_CHANNEL_ID)
        _daily_progress.start()
        logger.info("   Daily progress posting to channel %s", PROGRESS_CHANNEL_ID)


@client.event
async def on_message(message: discord.Message):
    # Never reply to ourselves
    if message.author == client.user:
        return

    # Skip bot messages
    if message.author.bot:
        return

    # Channel filter
    if ALLOWED_CHANNEL_IDS and message.channel.id not in ALLOWED_CHANNEL_IDS:
        return

    # Mention filter
    if MENTION_ONLY and client.user not in message.mentions:
        return

    # Strip the mention from the message text
    text = message.content
    if client.user:
        text = text.replace(f"<@{client.user.id}>", "").strip()

    if not text:
        return

    # Show typing indicator while processing
    async with message.channel.typing():
        reply = await forward_to_gateway(
            user_id=str(message.author.id),
            username=str(message.author),
            text=text,
            channel_id=str(message.channel.id),
        )

    if reply:
        # Discord has a 2000 char limit — split if needed
        for chunk in split_message(reply):
            await message.reply(chunk)
    else:
        await message.add_reaction("\u274c")


def split_message(text: str, limit: int = 1900) -> list[str]:
    """Split a long message into chunks that fit Discord's 2000-char limit."""
    if len(text) <= limit:
        return [text]

    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        # Try to split at a newline
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


def main():
    if not DISCORD_TOKEN:
        logger.error("DISCORD_BOT_TOKEN not set. Get one from https://discord.com/developers/applications")
        sys.exit(1)

    logger.info("Starting %s Discord adapter...", BOT_NAME)
    client.run(DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
