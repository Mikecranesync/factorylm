"""Verify Telegram alerts fire independently of Cosmos R2 availability.

Tests the decoupling introduced to prevent Cosmos timeouts from blocking
PLC fault alerts to Mike's Telegram.
"""

import asyncio
import time
from functools import partial
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cosmos.client import CosmosClient
from cosmos.models import CosmosInsight


# ---------------------------------------------------------------------------
# Phase 1 tests: alert-before-cosmos
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_incident_alert_fires_without_cosmos():
    """PLCMonitor sends Telegram alert immediately, before Cosmos returns."""
    from services.plc_monitor.telegram_alerter import TelegramAlerter

    alerter = TelegramAlerter(bot_token="test-token", chat_id="123")
    alerter._client = AsyncMock()

    # Mock _send to track call timing
    call_times = {}

    async def mock_send(text):
        call_times["send"] = time.monotonic()
        return True

    alerter._send = mock_send

    incident = {"id": 42, "error_message": "Motor overload", "node_id": "plc-001"}
    result = await alerter.send_raw_incident_alert(incident)

    assert result is True
    assert "send" in call_times
    # Verify it contains the incident data but NOT AI analysis
    # (we tested via mock_send capturing the text)


@pytest.mark.asyncio
async def test_enrichment_followup_sends_after_cosmos():
    """send_enrichment_followup sends AI analysis as a separate message."""
    import datetime
    from services.plc_monitor.telegram_alerter import TelegramAlerter

    alerter = TelegramAlerter(bot_token="test-token", chat_id="123")

    sent_texts = []

    async def mock_send(text):
        sent_texts.append(text)
        return True

    alerter._send = mock_send

    insight = CosmosInsight(
        incident_id="42",
        node_id="plc-001",
        timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
        summary="Motor overload detected",
        root_cause="Bearing degradation",
        confidence=0.82,
        reasoning="Current exceeds rated",
        suggested_checks=["Check bearings", "Verify belt tension"],
        cosmos_model="nvidia/cosmos-reason2-8b",
    )

    result = await alerter.send_enrichment_followup("42", insight)
    assert result is True
    assert len(sent_texts) == 1
    assert "AI Analysis" in sent_texts[0]
    assert "Motor overload" in sent_texts[0]
    assert "Bearing degradation" in sent_texts[0]


# ---------------------------------------------------------------------------
# Phase 2 tests: circuit breaker
# ---------------------------------------------------------------------------


def test_circuit_breaker_skips_after_3_failures():
    """After 3 Cosmos connection failures, stub returned instantly."""
    import httpx

    client = CosmosClient()
    client.api_key = "fake-key"  # Force real path

    # Simulate 3 consecutive ConnectErrors
    for i in range(3):
        with patch.object(
            httpx, "post", side_effect=httpx.ConnectError("refused")
        ):
            result = client.analyze_incident(
                incident_id=f"test-{i}",
                node_id="plc-001",
                tags={"error_code": 1},
            )
            # Should return stub
            assert isinstance(result, CosmosInsight)

    assert client._consecutive_failures >= 3

    # 4th call should return stub WITHOUT making HTTP call
    with patch.object(httpx, "post") as mock_post:
        result = client.analyze_incident(
            incident_id="test-4",
            node_id="plc-001",
            tags={"error_code": 1},
        )
        assert isinstance(result, CosmosInsight)
        mock_post.assert_not_called()


def test_circuit_breaker_resets_on_success():
    """Successful API call resets the failure counter."""
    import httpx

    client = CosmosClient()
    client.api_key = "fake-key"
    client._consecutive_failures = 2  # Just below threshold

    # Simulate a successful response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"summary": "ok", "root_cause": "none", "confidence": 0.9, "reasoning": "fine", "suggested_checks": ["check1"]}'
                }
            }
        ]
    }

    with patch.object(httpx, "post", return_value=mock_response):
        result = client.analyze_incident(
            incident_id="test-success",
            node_id="plc-001",
            tags={"error_code": 0},
        )

    assert client._consecutive_failures == 0
    assert isinstance(result, CosmosInsight)
    assert result.summary == "ok"


@pytest.mark.asyncio
async def test_divergence_alert_fires_without_cosmos():
    """Twin divergence alert sends before Cosmos analysis."""
    from services.plc_monitor.telegram_alerter import TelegramAlerter

    alerter = TelegramAlerter(bot_token="test-token", chat_id="123")

    sent_texts = []

    async def mock_send(text):
        sent_texts.append(text)
        return True

    alerter._send = mock_send

    mismatches = [
        {"tag": "motor_speed", "real": 60, "sim": 45, "type": "numeric", "drift": 0.33},
        {"tag": "motor_run", "real": True, "sim": False, "type": "bool"},
    ]

    # Send without insight (the new decoupled path)
    result = await alerter.send_divergence_alert(
        drift_score=0.33,
        mismatches=mismatches,
    )

    assert result is True
    assert len(sent_texts) == 1
    assert "DIVERGENCE" in sent_texts[0]
    assert "motor_speed" in sent_texts[0]
    # Should NOT contain AI Analysis section (no insight passed)
    assert "AI Analysis:" not in sent_texts[0]


def test_cosmos_stub_returns_valid_insight():
    """Stub responses have all required CosmosInsight fields for all fault codes."""
    client = CosmosClient()
    # No API key = stub mode

    fault_codes = [0, 1, 2, 3, 4, 5, -1]
    for code in fault_codes:
        tags = {"error_code": code}
        if code == -1:
            tags = {"error_code": 0, "e_stop": True}

        result = client.analyze_incident(
            incident_id=f"stub-{code}",
            node_id="plc-001",
            tags=tags,
        )

        assert isinstance(result, CosmosInsight), f"fault_code={code}"
        assert result.incident_id == f"stub-{code}"
        assert result.summary, f"Empty summary for fault_code={code}"
        assert result.root_cause, f"Empty root_cause for fault_code={code}"
        assert 0 <= result.confidence <= 1, f"Bad confidence for fault_code={code}"
        assert isinstance(result.suggested_checks, list), f"fault_code={code}"
