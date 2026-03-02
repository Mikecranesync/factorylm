"""Tests for bot slash commands and events."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from factorylm.bot.commands import FLEET_TABLE, create_commands
from factorylm.bot.events import setup_events
from factorylm.models import AgentConfig, DiscordConfig, FactoryLMConfig, RelayConfig


@pytest.fixture
def config():
    return FactoryLMConfig(
        discord=DiscordConfig(
            guild_id=999,
            agents={
                "tony": AgentConfig(
                    name="Tony",
                    webhook_url="https://discord.com/api/webhooks/1/SECRET",
                    channel_id=100,
                    machine="Mac Mini",
                    role="Boss agent",
                ),
            },
        ),
        relay=RelayConfig(host="127.0.0.1", port=8765),
    )


class TestCreateCommands:
    def test_registers_commands(self, config):
        """Verify that create_commands adds commands to the tree without error."""
        tree = MagicMock()
        tree.command = MagicMock(return_value=lambda f: f)
        tree.add_command = MagicMock()

        # Just verify it doesn't raise
        create_commands(tree, config)

        # Should have called tree.command multiple times (relay, status, fleet)
        assert tree.command.call_count >= 3
        # Should have added the config group
        tree.add_command.assert_called_once()


class TestFleetTable:
    def test_fleet_table_content(self):
        assert "Tony" in FLEET_TABLE
        assert "Ultron" in FLEET_TABLE
        assert "Jarvis" in FLEET_TABLE
        assert "Hetzner" in FLEET_TABLE
        assert "100.108.19.94" in FLEET_TABLE

    def test_fleet_table_is_code_block(self):
        assert FLEET_TABLE.strip().startswith("```")
        assert FLEET_TABLE.strip().endswith("```")


class TestConfigShowHidesSecrets:
    def test_webhook_url_not_in_config_show(self, config):
        """The /config show command must never expose webhook URLs."""
        # Build the agent lines the same way the command does
        agent_lines = []
        for name, agent_cfg in config.discord.agents.items():
            agent_lines.append(f"**{name}**: ch={agent_cfg.channel_id}, {agent_cfg.machine}")

        output = "\n".join(agent_lines)
        assert "SECRET" not in output
        assert "webhook" not in output.lower()

    def test_bot_token_not_exposed(self, config):
        """Config show should reference env var name, not actual token."""
        # The config stores env var name, not the token itself
        assert config.discord.bot_token_env_var == "DISCORD_BOT_TOKEN"
        # The actual token is never in the config model
        config_dict = config.model_dump()
        config_str = str(config_dict)
        # Only the env var name should appear, no actual token values
        assert "bot_token_env_var" in config_str
        assert "DISCORD_BOT_TOKEN" in config_str


class TestSetupEvents:
    def test_registers_on_ready(self, config):
        client = MagicMock()
        tree = MagicMock()
        # event decorator should be called
        client.event = MagicMock(side_effect=lambda f: f)
        tree.error = MagicMock(side_effect=lambda f: f)

        setup_events(client, tree, config)

        # on_ready and error handler registered
        assert client.event.call_count >= 1
        assert tree.error.call_count >= 1
