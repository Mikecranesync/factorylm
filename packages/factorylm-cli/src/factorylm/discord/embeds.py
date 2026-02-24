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
