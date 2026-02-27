"""Tests for config models and TOML loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from factorylm.config import ConfigError, get_bot_token, load_config
from factorylm.models import (
    AgentConfig,
    DiscordConfig,
    FactoryLMConfig,
    RelayConfig,
    TelegramConfig,
)

SAMPLE_TOML = """\
[discord]
guild_id = 123456789

[discord.agents.tony]
name = "Tony"
webhook_url = "https://discord.com/api/webhooks/111/abc"
channel_id = 100
machine = "Mac Mini"
role = "Boss agent"

[discord.agents.ultron]
name = "Ultron"
webhook_url = "https://discord.com/api/webhooks/222/def"
channel_id = 200
machine = "VPS"
role = "Cloud reasoning"

[telegram]
chat_id = 8445149012

[relay]
host = "127.0.0.1"
port = 8765
log_level = "DEBUG"
"""

MINIMAL_TOML = """\
[discord]
guild_id = 999
"""


class TestModels:
    def test_agent_config(self):
        agent = AgentConfig(
            name="Tony",
            webhook_url="https://example.com/hook",
            channel_id=100,
        )
        assert agent.name == "Tony"
        assert agent.machine == ""

    def test_discord_config_defaults(self):
        dc = DiscordConfig(guild_id=123)
        assert dc.bot_token_env_var == "DISCORD_BOT_TOKEN"
        assert dc.agents == {}

    def test_relay_config_defaults(self):
        rc = RelayConfig()
        assert rc.host == "127.0.0.1"
        assert rc.port == 8765
        assert rc.log_level == "INFO"

    def test_telegram_config_defaults(self):
        tc = TelegramConfig()
        assert tc.token_env_var == "TELEGRAM_BOT_TOKEN"
        assert tc.chat_id == 0

    def test_full_config(self):
        config = FactoryLMConfig(
            discord=DiscordConfig(guild_id=123),
            telegram=TelegramConfig(chat_id=456),
            relay=RelayConfig(port=9999),
        )
        assert config.discord.guild_id == 123
        assert config.relay.port == 9999


class TestLoadConfig:
    def test_load_valid_config(self, tmp_path: Path):
        config_file = tmp_path / "config.toml"
        config_file.write_text(SAMPLE_TOML)

        config = load_config(config_file)
        assert config.discord.guild_id == 123456789
        assert "tony" in config.discord.agents
        assert config.discord.agents["tony"].name == "Tony"
        assert config.discord.agents["ultron"].channel_id == 200
        assert config.telegram.chat_id == 8445149012
        assert config.relay.log_level == "DEBUG"

    def test_load_minimal_config(self, tmp_path: Path):
        config_file = tmp_path / "config.toml"
        config_file.write_text(MINIMAL_TOML)

        config = load_config(config_file)
        assert config.discord.guild_id == 999
        assert config.relay.port == 8765  # default

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(ConfigError, match="not found"):
            load_config(tmp_path / "nonexistent.toml")

    def test_missing_required_field(self, tmp_path: Path):
        config_file = tmp_path / "config.toml"
        config_file.write_text("[telegram]\nchat_id = 123\n")

        with pytest.raises(ConfigError, match="discord"):
            load_config(config_file)

    def test_invalid_toml(self, tmp_path: Path):
        config_file = tmp_path / "config.toml"
        config_file.write_text("this is not valid [[ toml")

        with pytest.raises(ConfigError, match="parse"):
            load_config(config_file)

    def test_default_path(self):
        from factorylm.config import DEFAULT_CONFIG_PATH

        assert str(DEFAULT_CONFIG_PATH).endswith(".factorylm/config.toml")


class TestGetBotToken:
    def test_token_from_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-token-123")

        config_file = tmp_path / "config.toml"
        config_file.write_text(MINIMAL_TOML)
        config = load_config(config_file)

        token = get_bot_token(config)
        assert token == "test-token-123"

    def test_custom_env_var(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("MY_CUSTOM_TOKEN", "custom-token-456")

        config = FactoryLMConfig(
            discord=DiscordConfig(guild_id=1, bot_token_env_var="MY_CUSTOM_TOKEN"),
        )
        token = get_bot_token(config)
        assert token == "custom-token-456"

    def test_missing_token_raises(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)

        config = FactoryLMConfig(discord=DiscordConfig(guild_id=1))
        with pytest.raises(ConfigError, match="not set"):
            get_bot_token(config)

    def test_empty_token_raises(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "   ")

        config = FactoryLMConfig(discord=DiscordConfig(guild_id=1))
        with pytest.raises(ConfigError, match="not set"):
            get_bot_token(config)
