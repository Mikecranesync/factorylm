"""
Configuration Management for PEPPER Bot

Loads configuration from YAML files with environment variable interpolation.
Supports multiple bot instances (prime, demo) and node routing.
"""

import os
import yaml
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from pathlib import Path
import re

logger = logging.getLogger(__name__)


@dataclass
class BotConfig:
    """Configuration for a single bot instance"""

    token: str
    name: str
    username: Optional[str] = None


@dataclass
class NodeConfig:
    """Configuration for a remote node"""

    url: str
    matrix_api: Optional[str] = None
    enabled: bool = True
    timeout: int = 30


@dataclass
class PepperConfig:
    """Main PEPPER bot configuration"""

    version: str
    bots: Dict[str, BotConfig]
    god_users: List[int]
    nodes: Dict[str, NodeConfig]
    log_level: str = "INFO"
    rate_limit_window: int = 3600  # 1 hour in seconds

    @property
    def prime_bot(self) -> Optional[BotConfig]:
        """Get the prime bot configuration"""
        return self.bots.get("prime")

    @property
    def demo_bot(self) -> Optional[BotConfig]:
        """Get the demo bot configuration"""
        return self.bots.get("demo")


def _interpolate_env_vars(value: Any) -> Any:
    """
    Recursively interpolate environment variables in configuration values.

    Supports ${VAR_NAME} and ${VAR_NAME:-default} syntax.

    Args:
        value: Configuration value (can be str, dict, list, etc.)

    Returns:
        Value with environment variables interpolated
    """
    if isinstance(value, str):
        # Pattern: ${VAR_NAME} or ${VAR_NAME:-default_value}
        pattern = r'\$\{([^}:]+)(?::?-([^}]*))?\}'

        def replace_var(match):
            var_name = match.group(1)
            default_value = match.group(2) if match.group(2) is not None else ""
            return os.environ.get(var_name, default_value)

        return re.sub(pattern, replace_var, value)

    elif isinstance(value, dict):
        return {k: _interpolate_env_vars(v) for k, v in value.items()}

    elif isinstance(value, list):
        return [_interpolate_env_vars(item) for item in value]

    return value


def load_config(config_path: Optional[str] = None) -> PepperConfig:
    """
    Load PEPPER bot configuration from YAML file.

    Args:
        config_path: Path to config.yaml (defaults to ./config.yaml)

    Returns:
        PepperConfig instance

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
    """
    if config_path is None:
        # Default to config.yaml in same directory as this file
        config_path = Path(__file__).parent / "config.yaml"

    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    logger.info(f"Loading configuration from {config_path}")

    # Load YAML
    with open(config_path, 'r', encoding='utf-8') as f:
        raw_config = yaml.safe_load(f)

    # Interpolate environment variables
    config_data = _interpolate_env_vars(raw_config)

    # Parse bots
    bots = {}
    for bot_name, bot_data in config_data.get("bots", {}).items():
        token = bot_data.get("token")
        if not token:
            logger.warning(f"Bot '{bot_name}' has no token, skipping")
            continue

        bots[bot_name] = BotConfig(
            token=token,
            name=bot_data.get("name", bot_name),
            username=bot_data.get("username"),
        )

    if not bots:
        raise ValueError("No valid bot configurations found")

    # Parse nodes
    nodes = {}
    for node_name, node_data in config_data.get("nodes", {}).items():
        nodes[node_name] = NodeConfig(
            url=node_data.get("url"),
            matrix_api=node_data.get("matrix_api"),
            enabled=node_data.get("enabled", True),
            timeout=node_data.get("timeout", 30),
        )

    # Parse god users
    god_users = config_data.get("god_users", [])
    if not isinstance(god_users, list):
        god_users = [god_users]

    # Create config object
    config = PepperConfig(
        version=config_data.get("version", "1.0.0"),
        bots=bots,
        god_users=god_users,
        nodes=nodes,
        log_level=config_data.get("log_level", "INFO"),
        rate_limit_window=config_data.get("rate_limit_window", 3600),
    )

    logger.info(f"Configuration loaded successfully: {len(bots)} bot(s), {len(nodes)} node(s)")
    logger.info(f"God users: {config.god_users}")

    return config


def validate_config(config: PepperConfig) -> None:
    """
    Validate configuration and log warnings.

    Args:
        config: PepperConfig to validate

    Raises:
        ValueError: If configuration is invalid
    """
    # Validate bot tokens
    for bot_name, bot in config.bots.items():
        if not bot.token or bot.token.startswith("${"):
            raise ValueError(
                f"Bot '{bot_name}' has invalid token. "
                "Make sure environment variable is set."
            )

    # Validate nodes
    for node_name, node in config.nodes.items():
        if not node.url:
            logger.warning(f"Node '{node_name}' has no URL configured")
        elif node.url.startswith("${"):
            raise ValueError(
                f"Node '{node_name}' has unresolved environment variable in URL"
            )

    # Validate god users
    if not config.god_users:
        logger.warning("No god users configured - all users will be in demo mode")

    logger.info("Configuration validation passed")


def get_active_bot(config: PepperConfig, prefer_prime: bool = True) -> BotConfig:
    """
    Get the active bot configuration.

    Args:
        config: PepperConfig instance
        prefer_prime: If True, prefer prime bot over demo bot

    Returns:
        BotConfig for the active bot

    Raises:
        ValueError: If no valid bot configuration found
    """
    if prefer_prime and config.prime_bot:
        logger.info(f"Using prime bot: {config.prime_bot.name}")
        return config.prime_bot

    if config.demo_bot:
        logger.info(f"Using demo bot: {config.demo_bot.name}")
        return config.demo_bot

    if config.prime_bot:
        logger.info(f"Falling back to prime bot: {config.prime_bot.name}")
        return config.prime_bot

    # Return first available bot
    if config.bots:
        bot = next(iter(config.bots.values()))
        logger.info(f"Using first available bot: {bot.name}")
        return bot

    raise ValueError("No valid bot configuration found")


def create_default_config(output_path: Optional[str] = None) -> None:
    """
    Create a default config.yaml file.

    Args:
        output_path: Where to write the config file (defaults to ./config.yaml)
    """
    if output_path is None:
        output_path = Path(__file__).parent / "config.yaml"

    default_config = """version: "1.0.0"

# Bot Configurations
bots:
  prime:
    token: ${PEPPER_PRIME_TOKEN}
    name: "Pepper Prime"
    username: "pepper_prime_bot"

  demo:
    token: ${FACTORYLM_BOT_TOKEN}
    name: "Pepper"
    username: "factorylm_bot"

# God Mode Users (Telegram user IDs)
god_users:
  - 8445149012  # Mike Crane

# Remote Nodes
nodes:
  plc:
    url: http://100.72.2.99:8765
    matrix_api: http://100.72.2.99:8000
    enabled: true
    timeout: 30

  travel:
    url: http://100.83.251.23:8765
    enabled: true
    timeout: 30

  vps:
    url: http://localhost:18789
    enabled: true
    timeout: 30

# Logging
log_level: INFO

# Rate Limiting
rate_limit_window: 3600  # 1 hour in seconds
"""

    output_path = Path(output_path)

    if output_path.exists():
        logger.warning(f"Config file already exists: {output_path}")
        backup_path = output_path.with_suffix(".yaml.backup")
        logger.info(f"Creating backup at {backup_path}")
        output_path.rename(backup_path)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(default_config)

    logger.info(f"Default configuration created at {output_path}")
    logger.info("Remember to set environment variables:")
    logger.info("  - PEPPER_PRIME_TOKEN")
    logger.info("  - FACTORYLM_BOT_TOKEN")
