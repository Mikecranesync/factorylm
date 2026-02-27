"""Pydantic v2 configuration models for FactoryLM Discord Layer."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """Configuration for a single agent's Discord presence."""

    name: str
    webhook_url: str
    channel_id: int
    machine: str = ""
    role: str = ""


class DiscordConfig(BaseModel):
    """Discord server configuration."""

    guild_id: int
    bot_token_env_var: str = "DISCORD_BOT_TOKEN"
    agents: dict[str, AgentConfig] = Field(default_factory=dict)


class TelegramConfig(BaseModel):
    """Telegram bridge configuration."""

    token_env_var: str = "TELEGRAM_BOT_TOKEN"
    chat_id: int = 0


class RelayConfig(BaseModel):
    """Relay daemon configuration."""

    host: str = "127.0.0.1"
    port: int = 8765
    log_level: str = "INFO"


class FactoryLMConfig(BaseModel):
    """Top-level configuration combining all sections."""

    discord: DiscordConfig
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    relay: RelayConfig = Field(default_factory=RelayConfig)
