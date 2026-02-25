"""Rich Discord embed builders for FactoryLM bot."""

from __future__ import annotations

import datetime
from typing import Any

import discord

from factorylm.cosmos.models import CosmosInsight


def _confidence_color(confidence: float) -> discord.Color:
    if confidence > 0.8:
        return discord.Color.green()
    if confidence > 0.6:
        return discord.Color.yellow()
    return discord.Color.red()


def _confidence_bar(confidence: float) -> str:
    filled = round(confidence * 10)
    return f"[{'=' * filled}{'-' * (10 - filled)}] {confidence:.0%}"


def build_insight_embed(insight: CosmosInsight, data_source: str = "") -> discord.Embed:
    embed = discord.Embed(
        title=f"Diagnosis: {insight.summary[:80]}",
        color=_confidence_color(insight.confidence),
        timestamp=insight.timestamp,
    )
    embed.add_field(name="Root Cause", value=insight.root_cause[:1024], inline=False)
    embed.add_field(name="Confidence", value=_confidence_bar(insight.confidence), inline=True)
    embed.add_field(name="Model", value=f"`{insight.cosmos_model}`", inline=True)

    if data_source == "live":
        embed.add_field(name="Data Source", value="\U0001f7e2 Live PLC data", inline=True)
    elif data_source == "synthetic":
        embed.add_field(name="Data Source", value="\U0001f7e1 Synthetic data", inline=True)

    if insight.reasoning:
        embed.add_field(name="Reasoning", value=insight.reasoning[:1024], inline=False)
    if insight.suggested_checks:
        checks = "\n".join(f"- {c}" for c in insight.suggested_checks[:10])
        embed.add_field(name="Suggested Checks", value=checks[:1024], inline=False)

    embed.set_footer(text=f"Incident {insight.incident_id} | Node {insight.node_id}")
    return embed


def build_status_embed(nodes: dict[str, dict]) -> discord.Embed:
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


def build_tags_embed(tags: dict | None) -> discord.Embed:
    if tags is None:
        return discord.Embed(
            title="PLC Tags — Offline",
            description="No tag data available.",
            color=discord.Color.dark_grey(),
            timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
        )

    fault = tags.get("fault_alarm", False)
    e_stop = tags.get("e_stop", False)
    if e_stop:
        color = discord.Color.dark_red()
    elif fault:
        color = discord.Color.red()
    else:
        color = discord.Color.green()

    embed = discord.Embed(
        title="PLC Tags — Live",
        color=color,
        timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
    )

    # Add tag fields dynamically
    skip = {"id", "timestamp", "node_id"}
    for key, val in tags.items():
        if key in skip:
            continue
        embed.add_field(name=key, value=f"`{val}`", inline=True)

    embed.set_footer(text=f"Node: {tags.get('node_id', 'local')}")
    return embed


def build_live_embed(
    tags: dict | None,
    *,
    stale: bool = False,
    node_id: str = "local",
) -> discord.Embed:
    """Build the live-updating dashboard embed for a dedicated channel.

    Args:
        tags: Latest tag dict from TagStore, or None if offline.
        stale: True if the data is older than the staleness threshold.
        node_id: Node identifier shown in the footer.
    """
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    if tags is None:
        return discord.Embed(
            title="FactoryLM Live — Offline",
            description="No tag data available.",
            color=discord.Color.dark_grey(),
            timestamp=now,
        ).set_footer(text=f"Node: {node_id}")

    # Determine embed color based on safety state
    fault = tags.get("fault_alarm", False)
    e_stop = tags.get("e_stop", False)
    if e_stop:
        color = discord.Color.dark_red()
    elif fault:
        color = discord.Color.red()
    elif stale:
        color = discord.Color.light_grey()
    else:
        color = discord.Color.green()

    title = "FactoryLM Live"
    if stale:
        title += " — STALE"

    embed = discord.Embed(title=title, color=color, timestamp=now)

    # Motor section
    motor_running = tags.get("Run_Status") or tags.get("motor_running", False)
    motor_speed = tags.get("Motor_Speed", tags.get("motor_speed", "—"))
    motor_current = tags.get("Current", tags.get("motor_current", "—"))
    motor_status = "RUNNING" if motor_running else "STOPPED"
    embed.add_field(
        name="Motor",
        value=f"**{motor_status}** | Speed: `{motor_speed}%` | Current: `{motor_current} A`",
        inline=False,
    )

    # Conveyor section
    conveyor_running = tags.get("conveyor_running", tags.get("Conveyor_Run", None))
    conveyor_speed = tags.get("conveyor_speed", tags.get("Conveyor_Speed", None))
    if conveyor_running is not None or conveyor_speed is not None:
        conv_status = "RUNNING" if conveyor_running else "STOPPED"
        conv_spd = conveyor_speed if conveyor_speed is not None else "—"
        embed.add_field(
            name="Conveyor",
            value=f"**{conv_status}** | Speed: `{conv_spd}%`",
            inline=False,
        )

    # Environment section
    temp = tags.get("Motor_Temp", tags.get("temperature", None))
    pressure = tags.get("pressure", tags.get("Pressure", None))
    vibration = tags.get("Vibration", tags.get("vibration", None))
    env_parts = []
    if temp is not None:
        env_parts.append(f"Temp: `{temp}`")
    if pressure is not None:
        env_parts.append(f"Pressure: `{pressure}`")
    if vibration is not None:
        env_parts.append(f"Vibration: `{vibration}`")
    if env_parts:
        embed.add_field(name="Environment", value=" | ".join(env_parts), inline=False)

    # Safety section
    error_code = tags.get("error_code", 0)
    safety_parts = []
    if fault:
        safety_parts.append("**FAULT ACTIVE**")
    if e_stop:
        safety_parts.append("**E-STOP ACTIVE**")
    if error_code:
        safety_parts.append(f"Error code: `{error_code}`")
    if safety_parts:
        embed.add_field(name="Safety", value=" | ".join(safety_parts), inline=False)
    else:
        embed.add_field(name="Safety", value="OK", inline=False)

    # Stale warning
    if stale:
        embed.add_field(
            name="Warning",
            value="Tag data is stale — PLC may be offline",
            inline=False,
        )

    embed.set_footer(text=f"Last updated: {now.strftime('%H:%M:%S')} UTC | Node: {node_id}")
    return embed


def build_about_embed() -> discord.Embed:
    embed = discord.Embed(
        title="FactoryLM",
        description=(
            "**Text your factory. AI tells you what's wrong.**\n\n"
            "FactoryLM connects industrial PLCs to natural language AI so "
            "technicians can diagnose faults by asking questions."
        ),
        color=discord.Color.blue(),
        url="https://github.com/Mikecranesync/factorylm",
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
    embed.set_footer(text="FactoryLM — pip install factorylm")
    return embed
