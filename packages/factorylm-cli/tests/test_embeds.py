"""Tests for Discord embed builders — live dashboard, alerts, dispatch."""

import discord

from factorylm.discord.embeds import (
    build_alert_embed,
    build_dispatch_embed,
    build_live_embed,
)


def test_live_embed_normal():
    """Normal running state: green, motor section present, safety OK."""
    tags = {
        "Motor_Speed": 75,
        "Current": 4.2,
        "Run_Status": True,
        "Motor_Temp": 42,
        "Vibration": 0.3,
        "fault_alarm": False,
        "e_stop": False,
        "error_code": 0,
    }
    embed = build_live_embed(tags)
    assert embed.color == discord.Color.green()
    assert embed.title == "FactoryLM Live"
    # Motor field present with RUNNING
    motor_field = next(f for f in embed.fields if f.name == "Motor")
    assert "RUNNING" in motor_field.value
    assert "75%" in motor_field.value
    # Safety OK
    safety_field = next(f for f in embed.fields if f.name == "Safety")
    assert safety_field.value == "OK"


def test_live_embed_fault():
    """Fault active: red embed, safety section shows fault."""
    tags = {
        "Motor_Speed": 0,
        "Current": 0,
        "Run_Status": False,
        "fault_alarm": True,
        "e_stop": False,
        "error_code": 3,
    }
    embed = build_live_embed(tags)
    assert embed.color == discord.Color.red()
    safety_field = next(f for f in embed.fields if f.name == "Safety")
    assert "FAULT ACTIVE" in safety_field.value
    assert "3" in safety_field.value


def test_live_embed_estop():
    """E-stop: dark red embed."""
    tags = {
        "Motor_Speed": 0,
        "Current": 0,
        "Run_Status": False,
        "fault_alarm": False,
        "e_stop": True,
        "error_code": -1,
    }
    embed = build_live_embed(tags)
    assert embed.color == discord.Color.dark_red()
    safety_field = next(f for f in embed.fields if f.name == "Safety")
    assert "E-STOP ACTIVE" in safety_field.value


def test_live_embed_stale():
    """Stale data: grey embed with STALE in title and warning field."""
    tags = {"Motor_Speed": 50, "Run_Status": True, "fault_alarm": False, "e_stop": False}
    embed = build_live_embed(tags, stale=True)
    assert embed.color == discord.Color.light_grey()
    assert "STALE" in embed.title
    warning_field = next(f for f in embed.fields if f.name == "Warning")
    assert "stale" in warning_field.value.lower()


def test_live_embed_offline():
    """No tags: dark grey, offline title."""
    embed = build_live_embed(None)
    assert embed.color == discord.Color.dark_grey()
    assert "Offline" in embed.title
    assert embed.description == "No tag data available."


def test_live_embed_conveyor():
    """Conveyor section appears when conveyor tags exist."""
    tags = {
        "Motor_Speed": 60,
        "Run_Status": True,
        "conveyor_running": True,
        "conveyor_speed": 80,
        "fault_alarm": False,
        "e_stop": False,
    }
    embed = build_live_embed(tags)
    conveyor_field = next(f for f in embed.fields if f.name == "Conveyor")
    assert "RUNNING" in conveyor_field.value
    assert "80%" in conveyor_field.value


def test_live_embed_node_id_in_footer():
    """Footer shows the node ID."""
    embed = build_live_embed(None, node_id="plc-laptop")
    assert "plc-laptop" in embed.footer.text


# ── Alert embeds ─────────────────────────────────────────────────────


def test_alert_embed_fault():
    """Fault incident: red embed with error code and message."""
    incident = {"id": 42, "error_code": 3, "error_message": "Conveyor jam", "node_id": "plc-laptop"}
    embed = build_alert_embed(incident)
    assert embed.color == discord.Color.red()
    assert "Error Code 3" in embed.title
    msg_field = next(f for f in embed.fields if f.name == "Message")
    assert msg_field.value == "Conveyor jam"
    node_field = next(f for f in embed.fields if f.name == "Node")
    assert "plc-laptop" in node_field.value


def test_alert_embed_estop():
    """E-stop incident: dark red embed."""
    incident = {"id": 99, "error_code": -1, "node_id": "local"}
    embed = build_alert_embed(incident)
    assert embed.color == discord.Color.dark_red()
    assert "E-STOP" in embed.title


def test_alert_embed_with_insight():
    """Alert with AI diagnosis shows summary and confidence."""
    incident = {"id": 10, "error_code": 1, "node_id": "local"}
    insight = {"summary": "Motor bearing failure", "root_cause": "Worn bearings", "confidence": 0.85}
    embed = build_alert_embed(incident, insight=insight)
    diag_field = next(f for f in embed.fields if f.name == "AI Diagnosis")
    assert "Motor bearing failure" in diag_field.value
    cause_field = next(f for f in embed.fields if f.name == "Root Cause")
    assert "Worn bearings" in cause_field.value


# ── Dispatch embeds ──────────────────────────────────────────────────


def test_dispatch_embed_delegated():
    """Delegated task: blue embed with from/to/status fields."""
    embed = build_dispatch_embed(
        action="web-search",
        summary="Research Micro820 fault codes",
        from_agent="tony",
        to_agent="ultron",
        status="delegated",
    )
    assert embed.color == discord.Color.blue()
    assert embed.title == "web-search"
    from_field = next(f for f in embed.fields if f.name == "From")
    assert "tony" in from_field.value
    to_field = next(f for f in embed.fields if f.name == "To")
    assert "ultron" in to_field.value
    status_field = next(f for f in embed.fields if f.name == "Status")
    assert "DELEGATED" in status_field.value


def test_dispatch_embed_completed():
    """Completed task: green embed."""
    embed = build_dispatch_embed(
        action="plc-read",
        summary="Read motor registers",
        from_agent="tony",
        to_agent="jarvis",
        status="completed",
    )
    assert embed.color == discord.Color.green()
    status_field = next(f for f in embed.fields if f.name == "Status")
    assert "COMPLETED" in status_field.value


def test_dispatch_embed_failed():
    """Failed task: red embed."""
    embed = build_dispatch_embed(
        action="batch-job",
        summary="Train model",
        from_agent="tony",
        to_agent="hetzner",
        status="failed",
    )
    assert embed.color == discord.Color.red()
    status_field = next(f for f in embed.fields if f.name == "Status")
    assert "FAILED" in status_field.value
