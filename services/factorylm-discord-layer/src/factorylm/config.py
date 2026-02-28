"""TOML configuration loader for FactoryLM Discord Layer."""

from __future__ import annotations

import os
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from pydantic import ValidationError

from factorylm.models import FactoryLMConfig, InstanceConfig

DEFAULT_CONFIG_PATH = Path("~/.factorylm/config.toml").expanduser()


class ConfigError(Exception):
    """Raised when configuration is invalid or missing."""

    def __init__(self, message: str, field: str = "") -> None:
        self.field = field
        super().__init__(message)


def load_config(path: str | Path | None = None) -> FactoryLMConfig:
    """Load and validate configuration from a TOML file.

    Args:
        path: Path to config file. Defaults to ~/.factorylm/config.toml.

    Returns:
        Validated FactoryLMConfig instance.

    Raises:
        ConfigError: If the file is missing, unparseable, or fails validation.
    """
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH

    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}", field="path")

    try:
        with open(config_path, "rb") as f:
            raw = tomllib.load(f)
    except Exception as exc:
        raise ConfigError(f"Failed to parse TOML: {exc}", field="path") from exc

    try:
        config = FactoryLMConfig.model_validate(raw)
    except ValidationError as exc:
        first_error = exc.errors()[0]
        field_path = ".".join(str(loc) for loc in first_error["loc"])
        raise ConfigError(
            f"Validation error at '{field_path}': {first_error['msg']}",
            field=field_path,
        ) from exc

    return config


def get_all_instances(config: FactoryLMConfig) -> dict[str, InstanceConfig]:
    """Return instances dict, falling back to legacy single-guild config.

    If config has instances defined, returns those directly.
    Otherwise, synthesizes a single instance from the legacy guild_id + agents.
    """
    if config.discord.instances:
        return config.discord.instances

    # Fallback: wrap legacy single-guild config as a "default" instance
    if config.discord.guild_id:
        return {
            "default": InstanceConfig(
                name="default",
                guild_id=config.discord.guild_id,
                bot_token_env_var=config.discord.bot_token_env_var,
                agents=config.discord.agents,
            )
        }

    return {}


def get_all_guild_ids(config: FactoryLMConfig) -> list[int]:
    """Return all guild IDs from instances (or legacy single guild)."""
    instances = get_all_instances(config)
    return [inst.guild_id for inst in instances.values() if inst.guild_id]


def get_bot_token(config: FactoryLMConfig) -> str:
    """Read the bot token from the environment variable named in config.

    Raises:
        ConfigError: If the env var is not set or empty.
    """
    env_var = config.discord.bot_token_env_var
    token = os.environ.get(env_var, "").strip()
    if not token:
        raise ConfigError(
            f"Bot token env var '{env_var}' is not set or empty",
            field="discord.bot_token_env_var",
        )
    return token
