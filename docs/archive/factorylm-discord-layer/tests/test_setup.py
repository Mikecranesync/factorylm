"""Tests for Discord setup wizard and config writer."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from factorylm.config import load_config
from factorylm.setup.config_writer import write_config
from factorylm.setup.discord_setup import CATEGORIES, DiscordSetup, SetupResult, _webhook_url


class TestWebhookUrl:
    def test_builds_url(self):
        data = {"id": "111", "token": "abc123"}
        assert _webhook_url(data) == "https://discord.com/api/webhooks/111/abc123"


class TestDiscordSetup:
    @pytest.fixture
    def setup(self):
        return DiscordSetup(bot_token="fake-token", guild_id=999)

    @pytest.mark.asyncio
    async def test_create_categories_skips_existing(self, setup):
        existing = [{"name": "FACTORY FLOOR", "id": 100, "type": 4}]

        with patch.object(setup, "_api_post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"id": 200, "name": "AGENTS"}
            cats = await setup.create_categories(existing)

        assert cats["FACTORY FLOOR"] == 100  # existing, not recreated
        assert cats["AGENTS"] == 200  # created
        mock_post.assert_called_once()  # only called for AGENTS

    @pytest.mark.asyncio
    async def test_create_categories_creates_all(self, setup):
        call_count = 0

        async def mock_post(path, json):
            nonlocal call_count
            call_count += 1
            return {"id": call_count * 100, "name": json["name"]}

        with patch.object(setup, "_api_post", side_effect=mock_post):
            cats = await setup.create_categories([])

        assert len(cats) == 2
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_create_channels_skips_existing(self, setup):
        categories = {"FACTORY FLOOR": 100, "AGENTS": 200}
        existing = [{"name": "plc-live", "id": 10, "type": 0}]

        created_ids = iter(range(20, 100))

        async def mock_post(path, json):
            cid = next(created_ids)
            return {"id": cid, "name": json["name"]}

        with patch.object(setup, "_api_post", side_effect=mock_post):
            channels = await setup.create_channels(categories, existing)

        assert channels["plc-live"] == 10  # existing
        assert "alerts" in channels
        assert "tony" in channels
        total_expected = sum(len(v) for v in CATEGORIES.values())
        assert len(channels) == total_expected

    @pytest.mark.asyncio
    async def test_create_webhooks_skips_existing(self, setup):
        channels = {"tony": 10, "ultron": 20}

        async def mock_get_webhooks(channel_id):
            if channel_id == 10:
                return [{"name": "FactoryLM", "id": "w1", "token": "t1"}]
            return []

        async def mock_post(path, json):
            return {"id": "w2", "token": "t2"}

        with (
            patch.object(setup, "_get_existing_webhooks", side_effect=mock_get_webhooks),
            patch.object(setup, "_api_post", side_effect=mock_post) as mock_post_call,
        ):
            webhooks = await setup.create_webhooks(channels)

        assert webhooks["tony"] == "https://discord.com/api/webhooks/w1/t1"
        assert webhooks["ultron"] == "https://discord.com/api/webhooks/w2/t2"
        mock_post_call.assert_called_once()  # only for ultron

    @pytest.mark.asyncio
    async def test_run_setup_orchestrates(self, setup):
        with (
            patch.object(
                setup, "_get_existing_channels", new_callable=AsyncMock, return_value=[]
            ),
            patch.object(
                setup,
                "create_categories",
                new_callable=AsyncMock,
                return_value={"FACTORY FLOOR": 1, "AGENTS": 2},
            ),
            patch.object(
                setup,
                "create_channels",
                new_callable=AsyncMock,
                return_value={"tony": 10, "alerts": 20},
            ),
            patch.object(
                setup,
                "create_webhooks",
                new_callable=AsyncMock,
                return_value={"tony": "https://example.com/hook"},
            ),
        ):
            result = await setup.run_setup()

        assert result.guild_id == 999
        assert result.categories == {"FACTORY FLOOR": 1, "AGENTS": 2}
        assert result.channels == {"tony": 10, "alerts": 20}


class TestConfigWriter:
    def test_write_config(self, tmp_path: Path):
        result = SetupResult(
            guild_id=123456,
            categories={"FACTORY FLOOR": 1, "AGENTS": 2},
            channels={"tony": 10, "ultron": 20, "plc-live": 30, "alerts": 40},
            webhooks={
                "tony": "https://discord.com/api/webhooks/1/a",
                "ultron": "https://discord.com/api/webhooks/2/b",
            },
        )

        output = tmp_path / "config.toml"
        path = write_config(result, output)

        assert path == output
        assert path.exists()

        content = path.read_text()
        assert "guild_id = 123456" in content
        assert "tony" in content
        assert "ultron" in content
        # plc-live is not an agent channel — should NOT appear as agent config
        assert "[discord.agents.plc-live]" not in content

    def test_written_config_is_loadable(self, tmp_path: Path):
        result = SetupResult(
            guild_id=999,
            channels={"tony": 10, "ultron": 20},
            webhooks={
                "tony": "https://discord.com/api/webhooks/1/a",
                "ultron": "https://discord.com/api/webhooks/2/b",
            },
        )

        output = tmp_path / "config.toml"
        write_config(result, output)

        config = load_config(output)
        assert config.discord.guild_id == 999
        assert "tony" in config.discord.agents
        assert config.relay.port == 8765

    def test_never_writes_bot_token(self, tmp_path: Path):
        result = SetupResult(guild_id=1)
        output = tmp_path / "config.toml"
        write_config(result, output)

        content = output.read_text()
        # Should reference the env var name, not a token value
        assert "bot_token_env_var" in content
        # No actual token value
        assert "xMT" not in content  # Discord tokens start with this
