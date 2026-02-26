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

from factorylm.models import FactoryLMConfig

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
