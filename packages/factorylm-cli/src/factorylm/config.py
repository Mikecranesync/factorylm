"""TOML config loader for FactoryLM CLI.

Reads from ~/.factorylm/config.toml with env-var overrides.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

CONFIG_DIR = Path.home() / ".factorylm"
CONFIG_FILE = CONFIG_DIR / "config.toml"


@dataclass
class PLCConfig:
    type: str = "modbus"
    host: str = "192.168.1.100"
    port: int = 502
    unit_id: int = 1
    poll_interval: float = 2.0
    # S7-specific
    rack: int = 0
    slot: int = 1
    # EtherNet/IP tag list
    tags: list[str] = field(default_factory=lambda: [
        "Motor_Speed", "Motor_Temp", "Vibration", "Current", "Run_Status",
    ])


@dataclass
class DBConfig:
    path: str = str(CONFIG_DIR / "tags.db")


@dataclass
class APIConfig:
    host: str = "0.0.0.0"
    port: int = 8001


@dataclass
class DiscordConfig:
    token: str = ""
    bot_name: str = "FactoryLM"
    mention_only: bool = True


@dataclass
class MonitorConfig:
    enabled: bool = True
    poll_interval: float = 5.0


@dataclass
class CosmosConfig:
    api_key: str = ""
    model: str = "nvidia/cosmos-reason2-8b"


@dataclass
class FactoryLMConfig:
    plc: PLCConfig = field(default_factory=PLCConfig)
    db: DBConfig = field(default_factory=DBConfig)
    api: APIConfig = field(default_factory=APIConfig)
    discord: DiscordConfig = field(default_factory=DiscordConfig)
    monitor: MonitorConfig = field(default_factory=MonitorConfig)
    cosmos: CosmosConfig = field(default_factory=CosmosConfig)


def _apply_env_overrides(cfg: FactoryLMConfig) -> None:
    """Override config values from environment variables."""
    if v := os.getenv("FACTORYLM_PLC_HOST"):
        cfg.plc.host = v
    if v := os.getenv("FACTORYLM_PLC_PORT"):
        cfg.plc.port = int(v)
    if v := os.getenv("FACTORYLM_PLC_TYPE"):
        cfg.plc.type = v
    if v := os.getenv("DISCORD_BOT_TOKEN"):
        cfg.discord.token = v
    if v := os.getenv("NVIDIA_COSMOS_API_KEY"):
        cfg.cosmos.api_key = v


def load_config(path: Path | None = None) -> FactoryLMConfig:
    """Load config from TOML file, then apply env-var overrides."""
    cfg = FactoryLMConfig()
    config_path = path or CONFIG_FILE

    if config_path.exists():
        with open(config_path, "rb") as f:
            raw = tomllib.load(f)

        if "plc" in raw:
            for k, v in raw["plc"].items():
                if hasattr(cfg.plc, k):
                    setattr(cfg.plc, k, v)
        if "db" in raw:
            for k, v in raw["db"].items():
                if hasattr(cfg.db, k):
                    setattr(cfg.db, k, v)
        if "api" in raw:
            for k, v in raw["api"].items():
                if hasattr(cfg.api, k):
                    setattr(cfg.api, k, v)
        if "discord" in raw:
            for k, v in raw["discord"].items():
                if hasattr(cfg.discord, k):
                    setattr(cfg.discord, k, v)
        if "monitor" in raw:
            for k, v in raw["monitor"].items():
                if hasattr(cfg.monitor, k):
                    setattr(cfg.monitor, k, v)
        if "cosmos" in raw:
            for k, v in raw["cosmos"].items():
                if hasattr(cfg.cosmos, k):
                    setattr(cfg.cosmos, k, v)

    _apply_env_overrides(cfg)
    return cfg


DEFAULT_CONFIG_TOML = """\
[plc]
type = "modbus"           # modbus | enip | s7
host = "192.168.1.100"
port = 502
unit_id = 1
poll_interval = 2.0       # seconds

[db]
path = "~/.factorylm/tags.db"

[api]
host = "0.0.0.0"
port = 8001

[discord]
token = ""                # or use DISCORD_BOT_TOKEN env var
bot_name = "FactoryLM"
mention_only = true

[monitor]
enabled = true
poll_interval = 5.0

[cosmos]
api_key = ""              # or use NVIDIA_COSMOS_API_KEY env var
model = "nvidia/cosmos-reason2-8b"
"""


def write_default_config(path: Path | None = None) -> Path:
    """Write the default config.toml and return its path."""
    config_path = path or CONFIG_FILE
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(DEFAULT_CONFIG_TOML)
    return config_path
