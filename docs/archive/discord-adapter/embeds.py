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


def build_ops_hub_summary(
    nodes: dict[str, dict],
    tags: dict | None,
    conveyor: dict | None,
    incident_count: int,
    detail_channel_id: int | None = None,
) -> discord.Embed:
    """Build a compact Ops Hub summary embed — one-glance status.

    detail_channel_id: if set, adds a pointer to the full report channel.
    """
    # --- Overall status ---
    plc_offline = tags is None
    any_node_down = any(not n["up"] for n in nodes.values()) if nodes else True
    fault = bool(tags and tags.get("fault"))
    e_stop = bool(tags and tags.get("e_stop"))

    if fault or e_stop or incident_count >= 3:
        color = discord.Color.red()
        status_icon = "\U0001f534"
        status_text = "ALERT"
    elif any_node_down or plc_offline:
        color = discord.Color.yellow()
        status_icon = "\U0001f7e1"
        status_text = "DEGRADED"
    else:
        color = discord.Color.green()
        status_icon = "\U0001f7e2"
        status_text = "ALL CLEAR"

    embed = discord.Embed(
        title=f"{status_icon} Daily Health \u2014 {status_text}",
        color=color,
        timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
    )

    # --- Nodes summary ---
    up_count = sum(1 for n in nodes.values() if n["up"]) if nodes else 0
    total = len(nodes) if nodes else 0
    nodes_str = f"\U0001f7e2 {up_count}/{total}" if up_count == total else f"\U0001f7e1 {up_count}/{total}"

    # --- PLC summary ---
    if tags is not None:
        motor_state = "ON" if tags.get("motor_running", False) else "OFF"
        plc_str = f"\U0001f7e2 Motor: {motor_state}"
        if fault:
            plc_str = "\U0001f534 FAULT"
        elif e_stop:
            plc_str = "\U0001f6d1 E-STOP"
    else:
        plc_str = "\U0001f534 Offline"

    embed.add_field(name="Nodes", value=nodes_str, inline=True)
    embed.add_field(name="PLC", value=plc_str, inline=True)

    # --- Conveyor summary ---
    if conveyor is not None:
        run_state = conveyor.get("runState", "unknown").upper()
        conv_str = f"{run_state}"
    elif tags is not None:
        conv_state = "RUNNING" if tags.get("conveyor_running", False) else "STOPPED"
        conv_str = conv_state
    else:
        conv_str = "Unknown"
    embed.add_field(name="Conveyor", value=conv_str, inline=True)

    # --- Incidents ---
    embed.add_field(name="Incidents", value=str(incident_count), inline=True)

    # --- Pointer to detail channel ---
    if detail_channel_id:
        embed.add_field(
            name="Details",
            value=f"Full report in <#{detail_channel_id}>",
            inline=False,
        )

    embed.set_footer(text="FactoryLM Ops Hub | Daily Summary")
    return embed


def build_health_report_embed(
    nodes: dict[str, dict],
    tags: dict | None,
    conveyor: dict | None,
    incident_count: int,
    footer_extra: str | None = None,
) -> discord.Embed:
    """Build the combined daily health report embed.

    nodes: {name: {"url": str, "up": bool, "latency_ms": int | None, "error": str | None}}
    tags: latest PLC tag snapshot or None if offline.
    conveyor: VFD relay status dict or None if offline.
    incident_count: number of open incidents from Matrix API.
    """
    # --- Determine overall color ---
    plc_offline = tags is None
    any_node_down = any(not n["up"] for n in nodes.values()) if nodes else True
    fault = bool(tags and tags.get("fault"))
    e_stop = bool(tags and tags.get("e_stop"))

    if fault or e_stop or incident_count >= 3:
        color = discord.Color.red()
    elif any_node_down or plc_offline:
        color = discord.Color.yellow()
    else:
        color = discord.Color.green()

    embed = discord.Embed(
        title="Daily Health Report",
        color=color,
        timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
    )

    # --- Network Nodes ---
    node_lines = []
    for name, info in nodes.items():
        if info["up"]:
            latency = f" ({info['latency_ms']}ms)" if info.get("latency_ms") is not None else ""
            node_lines.append(f"\U0001f7e2 **{name}**{latency}")
        else:
            reason = f" — {info['error']}" if info.get("error") else ""
            node_lines.append(f"\U0001f534 **{name}**{reason}")
    up_count = sum(1 for n in nodes.values() if n["up"])
    node_lines.append(f"_{up_count}/{len(nodes)} online_")
    embed.add_field(name="Network Nodes", value="\n".join(node_lines), inline=False)

    if tags is not None:
        # --- Motor ---
        motor_state = "RUNNING" if tags.get("motor_running", False) else "STOPPED"
        motor_speed = tags.get("motor_speed", "-")
        motor_current = tags.get("motor_current", "-")
        embed.add_field(
            name="Motor",
            value=f"**{motor_state}**\nSpeed: {motor_speed}%\nCurrent: {motor_current} A",
            inline=True,
        )

        # --- Conveyor (PLC) ---
        conv_state = "RUNNING" if tags.get("conveyor_running", False) else "STOPPED"
        conv_speed = tags.get("conveyor_speed", "-")
        embed.add_field(
            name="Conveyor (PLC)",
            value=f"**{conv_state}**\nSpeed: {conv_speed}%",
            inline=True,
        )
    else:
        embed.add_field(name="PLC", value="\U0001f534 Offline — cannot reach Matrix API", inline=False)

    # --- Conveyor (VFD Relay) ---
    if conveyor is not None:
        run_state = conveyor.get("runState", "unknown").capitalize()
        actual_hz = conveyor.get("actualHz")
        motor_a = conveyor.get("motorCurrent")
        relay_val = f"**{run_state}**"
        if actual_hz is not None:
            relay_val += f"\n{actual_hz:.1f} Hz"
        if motor_a is not None:
            relay_val += f"\n{motor_a:.2f} A"
        embed.add_field(name="Conveyor (VFD)", value=relay_val, inline=True)
    else:
        embed.add_field(name="Conveyor (VFD)", value="\U0001f534 Relay offline", inline=True)

    if tags is not None:
        # --- Environment ---
        temp = tags.get("temperature", "-")
        pressure = tags.get("pressure", "-")
        embed.add_field(
            name="Environment",
            value=f"Temp: {temp} \u00b0C\nPressure: {pressure} PSI",
            inline=True,
        )

        # --- Sensors ---
        s1 = "PART" if tags.get("sensor_1", False) else "Clear"
        s2 = "PART" if tags.get("sensor_2", False) else "Clear"
        embed.add_field(
            name="Sensors",
            value=f"Sensor 1: **{s1}**\nSensor 2: **{s2}**",
            inline=True,
        )

        # --- Safety ---
        fault_str = "\U0001f534 FAULT" if tags.get("fault") else "\U0001f7e2 OK"
        estop_str = "\U0001f6d1 E-STOP" if tags.get("e_stop") else "\U0001f7e2 Clear"
        error_code = tags.get("error_code", 0)
        safety_val = f"Fault: {fault_str}\nE-Stop: {estop_str}"
        if error_code and error_code != 0:
            error_msg = tags.get("error_message", "")
            safety_val += f"\nError: `{error_code}`"
            if error_msg:
                safety_val += f" — {error_msg}"
        embed.add_field(name="Safety", value=safety_val, inline=True)

    # --- Open Incidents ---
    if incident_count > 0:
        embed.add_field(
            name="Open Incidents",
            value=f"\u26a0\ufe0f **{incident_count}** open",
            inline=True,
        )

    footer_text = "FactoryLM Daily Health Report"
    if footer_extra:
        footer_text += f" | {footer_extra}"
    embed.set_footer(text=footer_text)
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
