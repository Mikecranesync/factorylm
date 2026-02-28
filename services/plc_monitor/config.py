"""PLC Monitor service configuration — loads from environment variables."""

import dataclasses
import os


@dataclasses.dataclass
class MonitorConfig:
    """All settings for the PLC Monitor service, loaded from env vars."""

    # Matrix API (real PLC data source)
    matrix_url: str = ""
    # Factory I/O (digital twin Modbus)
    factoryio_host: str = ""
    factoryio_port: int = 502
    # NVIDIA Cosmos
    nvidia_cosmos_api_key: str = ""
    # Telegram alerts
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    # Polling
    poll_interval: float = 5.0
    twin_compare_interval: float = 10.0
    twin_divergence_threshold: float = 0.15
    # Health server
    health_port: int = 7200

    @classmethod
    def from_env(cls) -> "MonitorConfig":
        return cls(
            matrix_url=os.getenv("MATRIX_URL", "http://100.72.2.99:8001"),
            factoryio_host=os.getenv("FACTORYIO_HOST", "127.0.0.1"),
            factoryio_port=int(os.getenv("FACTORYIO_PORT", "502")),
            nvidia_cosmos_api_key=os.getenv("NVIDIA_COSMOS_API_KEY", ""),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "8445149012"),
            poll_interval=float(os.getenv("PLC_MONITOR_POLL_INTERVAL", "5.0")),
            twin_compare_interval=float(os.getenv("TWIN_COMPARE_INTERVAL", "10.0")),
            twin_divergence_threshold=float(os.getenv("TWIN_DIVERGENCE_THRESHOLD", "0.15")),
            health_port=int(os.getenv("PLC_MONITOR_HEALTH_PORT", "7200")),
        )
