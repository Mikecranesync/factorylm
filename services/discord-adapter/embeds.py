"""
Rich Discord embed builders for FactoryLM bot.

Formats CosmosInsight results, node health status, and about info
as color-coded Discord embeds.
"""

import datetime

import discord

from cosmos.models import CosmosInsight


def _confidence_color(confidence: float) -> discord.Color:
    """Return green >0.8, yellow >0.6, red otherwise."""
    if confidence > 0.8:
        return discord.Color.green()
    if confidence > 0.6:
        return discord.Color.yellow()
    return discord.Color.red()


def _confidence_bar(confidence: float) -> str:
    """Render a visual confidence bar like [========--] 82%."""
    filled = round(confidence * 10)
    return f"[{'=' * filled}{'-' * (10 - filled)}] {confidence:.0%}"


def build_insight_embed(insight: CosmosInsight) -> discord.Embed:
    """Format a CosmosInsight as a color-coded Discord embed."""
    embed = discord.Embed(
        title=f"Diagnosis: {insight.summary[:80]}",
        color=_confidence_color(insight.confidence),
        timestamp=insight.timestamp,
    )
    embed.add_field(name="Root Cause", value=insight.root_cause[:1024], inline=False)
    embed.add_field(name="Confidence", value=_confidence_bar(insight.confidence), inline=True)
    embed.add_field(name="Model", value=f"`{insight.cosmos_model}`", inline=True)

    if insight.reasoning:
        # Truncate to embed field limit
        embed.add_field(name="Reasoning", value=insight.reasoning[:1024], inline=False)

    if insight.suggested_checks:
        checks = "\n".join(f"- {c}" for c in insight.suggested_checks[:10])
        embed.add_field(name="Suggested Checks", value=checks[:1024], inline=False)

    embed.set_footer(
        text=f"Incident {insight.incident_id} | Node {insight.node_id}"
    )
    return embed


def build_status_embed(nodes: dict[str, dict]) -> discord.Embed:
    """Format node health results as an embed with green/red indicators.

    nodes: {name: {"url": str, "up": bool, "latency_ms": int | None, "error": str | None}}
    """
    all_up = all(n["up"] for n in nodes.values())
    embed = discord.Embed(
        title="FactoryLM Network Status",
        color=discord.Color.green() if all_up else discord.Color.red(),
        timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
    )

    for name, info in nodes.items():
        if info["up"]:
            latency = f" ({info['latency_ms']}ms)" if info.get("latency_ms") is not None else ""
            value = f"\U0001f7e2 Online{latency}"
        else:
            reason = f" — {info['error']}" if info.get("error") else ""
            value = f"\U0001f534 Offline{reason}"
        embed.add_field(name=name, value=value, inline=False)

    up_count = sum(1 for n in nodes.values() if n["up"])
    embed.set_footer(text=f"{up_count}/{len(nodes)} nodes online")
    return embed


def build_conveyor_embed(
    action: str, result: dict, relay_url: str, speed: int | None = None
) -> discord.Embed:
    """Build an embed showing the result of a conveyor command."""
    success = result.get("success", False)
    status = result.get("status") or result  # status query returns data directly

    run_state = status.get("runState", "unknown")
    direction = status.get("direction", "-")
    actual_hz = status.get("actualHz")
    command_hz = status.get("commandHz")

    # Title based on action
    titles = {
        "forward": "Conveyor: Forward",
        "reverse": "Conveyor: Reverse",
        "stop": "Conveyor: Stopped",
        "set_speed": f"Conveyor: Speed set to {speed} Hz" if speed else "Conveyor: Speed updated",
        "status": "Conveyor Status",
    }
    title = titles.get(action, f"Conveyor: {action}")

    # Color based on state
    if run_state == "running":
        color = discord.Color.green()
    elif run_state == "stopped":
        color = discord.Color.greyple()
    elif run_state == "fault":
        color = discord.Color.red()
    else:
        color = discord.Color.dark_grey()

    embed = discord.Embed(
        title=title,
        color=color,
        timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
    )

    # State field
    state_text = run_state.capitalize()
    if run_state == "running":
        hz_display = f"{actual_hz:.1f}" if actual_hz is not None else str(command_hz or "?")
        state_text = f"Running {direction} @ {hz_display} Hz"
    embed.add_field(name="State", value=state_text, inline=True)

    if status.get("motorCurrent") is not None:
        embed.add_field(name="Motor", value=f"{status['motorCurrent']:.2f} A", inline=True)

    if status.get("commandCount") is not None:
        embed.add_field(name="Commands", value=str(status["commandCount"]), inline=True)

    if not success and action != "status":
        msg = result.get("message") or result.get("detail") or "Command failed"
        embed.add_field(name="Error", value=str(msg)[:1024], inline=False)

    embed.add_field(
        name="Live View",
        value=f"[Open control page]({relay_url}/)",
        inline=False,
    )
    embed.set_footer(text="FactoryLM Conveyor Lab")
    return embed


def build_about_embed() -> discord.Embed:
    """Static FactoryLM info embed for the /about command."""
    embed = discord.Embed(
        title="FactoryLM",
        description=(
            "**Text your factory. AI tells you what's wrong.**\n\n"
            "FactoryLM connects industrial PLCs to natural language AI so "
            "technicians can diagnose faults by asking questions — via "
            "Telegram, Discord, or WhatsApp."
        ),
        color=discord.Color.blue(),
        url="https://github.com/Mikecranesync/factorylm",
    )
    embed.add_field(
        name="Architecture",
        value=(
            "```\n"
            "Phone/Discord -> Cloud Gateway -> Edge Node -> PLC\n"
            "                      |                        |\n"
            "                  AI Analysis <--- Tag Data ---+\n"
            "```"
        ),
        inline=False,
    )
    embed.add_field(
        name="Cosmos Cookoff",
        value=(
            "Using **NVIDIA Cosmos Reason 2** for video-based fault "
            "analysis on real factory floor footage. The model watches "
            "conveyor operations and identifies anomalies in real time."
        ),
        inline=False,
    )
    embed.add_field(
        name="Stack",
        value=(
            "- **Layer 0**: Deterministic code + knowledge base\n"
            "- **Layer 1**: Edge LLM on Raspberry Pi (0.5B)\n"
            "- **Layer 2**: Local GPU server (70B, air-gapped)\n"
            "- **Layer 3**: Cloud AI (Claude, Cosmos R2)"
        ),
        inline=False,
    )
    embed.add_field(
        name="Links",
        value=(
            "[GitHub](https://github.com/Mikecranesync/factorylm) | "
            "[Website](https://factorylm.com)"
        ),
        inline=False,
    )
    embed.set_footer(text="FactoryLM — Cosmos Cookoff 2026")
    return embed
