"""Unit tests for cosmos.agent — Cosmos Reason 2 connector."""

import asyncio
import datetime
from unittest.mock import patch

import pytest

from cosmos.agent import CosmosAgent
from cosmos.models import CosmosInsight


class TestCosmosAgentDisabled:
    """Agent should report disabled when no API key is set."""

    def test_cosmos_agent_disabled_by_default(self):
        with patch.dict("os.environ", {}, clear=True):
            agent = CosmosAgent(config_path="nonexistent.yaml")
            assert agent.is_enabled() is False


class TestCosmosInsightDefaults:
    """CosmosInsight fields have sensible defaults."""

    def test_cosmos_insight_defaults(self):
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        insight = CosmosInsight(
            incident_id="INC-001",
            node_id="node-a",
            timestamp=now,
        )
        assert insight.summary == ""
        assert insight.root_cause == ""
        assert insight.confidence == 0.0
        assert insight.reasoning == ""
        assert insight.suggested_checks == []
        assert insight.video_url == ""
        assert insight.tag_window_seconds == 60
        assert insight.cosmos_model == "nvidia/cosmos-reason2"


class TestOnIncident:
    """on_incident should return a CosmosInsight stub."""

    @pytest.mark.asyncio
    async def test_on_incident_returns_insight(self):
        agent = CosmosAgent(config_path="nonexistent.yaml")
        insight = await agent.on_incident(
            incident_id="INC-042",
            node_id="plc-7",
            tags={"temp": 72.5},
        )
        assert isinstance(insight, CosmosInsight)
        assert insight.incident_id == "INC-042"
        assert insight.node_id == "plc-7"
        assert len(insight.summary) > 0


class TestFetchTagHistory:
    """fetch_tag_history stub should return an empty dict."""

    @pytest.mark.asyncio
    async def test_fetch_tag_history_returns_empty(self):
        agent = CosmosAgent(config_path="nonexistent.yaml")
        result = await agent.fetch_tag_history("node-a", seconds=120)
        assert result == {}


class TestCosmosAgentEnabled:
    """Agent should report enabled when config + API key are both set."""

    def test_cosmos_agent_enabled_with_key(self, tmp_path):
        cfg = tmp_path / "cosmos.yaml"
        cfg.write_text(
            "cosmos:\n  enabled: true\n  model: nvidia/cosmos-reason2\n",
            encoding="utf-8",
        )
        with patch.dict("os.environ", {"NVIDIA_COSMOS_API_KEY": "nvapi-test-key"}):
            agent = CosmosAgent(config_path=str(cfg))
            assert agent.is_enabled() is True
