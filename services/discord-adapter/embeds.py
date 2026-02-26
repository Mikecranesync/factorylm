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


def build_insight_embed(insight: CosmosInsight, data_source: str = "") -> discord.Embed:
    """Format a CosmosInsight as a color-coded Discord embed.

    data_source: "live", "synthetic", or "" (no badge).
    """
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


def build_tags_embed(tags: dict | None, matrix_url: str) -> discord.Embed:
    """Format live PLC tag snapshot as a Discord embed.

    tags: single tag snapshot dict from Matrix API, or None if unreachable.
    matrix_url: base URL shown in footer for context.
    """
    if tags is None:
        embed = discord.Embed(
            title="PLC Tags — Offline",
            description="Cannot reach Matrix API.",
            color=discord.Color.dark_grey(),
            timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
        )
        embed.set_footer(text=f"Source: {matrix_url}")
        return embed

    # Determine color based on fault / e-stop state
    e_stop = tags.get("e_stop", False)
    fault = tags.get("fault", False)
    error_code = tags.get("error_code", 0)

    if e_stop:
        color = discord.Color.dark_red()
    elif fault or error_code not in (0, None):
        color = discord.Color.red()
    else:
        color = discord.Color.green()

    embed = discord.Embed(
        title="PLC Tags — Live",
        color=color,
        timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
    )

    # Motor field
    motor_state = "RUNNING" if tags.get("motor_running", False) else "STOPPED"
    motor_speed = tags.get("motor_speed", "-")
    motor_current = tags.get("motor_current", "-")
    motor_val = f"**{motor_state}**\nSpeed: {motor_speed}%\nCurrent: {motor_current} A"
    embed.add_field(name="Motor", value=motor_val, inline=True)

    # Conveyor field
    conv_state = "RUNNING" if tags.get("conveyor_running", False) else "STOPPED"
    conv_speed = tags.get("conveyor_speed", "-")
    conv_val = f"**{conv_state}**\nSpeed: {conv_speed}%"
    embed.add_field(name="Conveyor", value=conv_val, inline=True)

    # Environment field
    temp = tags.get("temperature", "-")
    pressure = tags.get("pressure", "-")
    env_val = f"Temp: {temp} \u00b0C\nPressure: {pressure} PSI"
    embed.add_field(name="Environment", value=env_val, inline=True)

    # Sensors field
    s1 = "PART" if tags.get("sensor_1", False) else "Clear"
    s2 = "PART" if tags.get("sensor_2", False) else "Clear"
    sensor_val = f"Sensor 1: **{s1}**\nSensor 2: **{s2}**"
    embed.add_field(name="Sensors", value=sensor_val, inline=True)

    # Safety field
    fault_str = "\U0001f534 FAULT" if fault else "\U0001f7e2 OK"
    estop_str = "\U0001f6d1 E-STOP" if e_stop else "\U0001f7e2 Clear"
    safety_val = f"Fault: {fault_str}\nE-Stop: {estop_str}"
    if error_code and error_code != 0:
        error_msg = tags.get("error_message", "")
        safety_val += f"\nError: `{error_code}`"
        if error_msg:
            safety_val += f" — {error_msg}"
    embed.add_field(name="Safety", value=safety_val, inline=True)

    # Footer with snapshot ID, node, and stale detection
    snapshot_id = tags.get("id", tags.get("snapshot_id", "?"))
    node_id = tags.get("node_id", "unknown")
    footer_text = f"Snapshot #{snapshot_id} | Node: {node_id}"

    ts_raw = tags.get("timestamp")
    if ts_raw:
        try:
            if isinstance(ts_raw, str):
                # Handle ISO format with or without Z suffix
                ts_raw = ts_raw.replace("Z", "+00:00")
                snap_time = datetime.datetime.fromisoformat(ts_raw)
            else:
                snap_time = datetime.datetime.fromtimestamp(ts_raw, tz=datetime.timezone.utc)
            if snap_time.tzinfo is None:
                snap_time = snap_time.replace(tzinfo=datetime.timezone.utc)
            age = (datetime.datetime.now(tz=datetime.timezone.utc) - snap_time).total_seconds()
            if age > 30:
                footer_text += f" | \u26a0\ufe0f STALE ({int(age)}s old)"
        except (ValueError, TypeError, OSError):
            pass

    embed.set_footer(text=footer_text)
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
