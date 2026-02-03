"""Backend configuration settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_prefix="FACTORYLM_",
        env_file=".env",
        extra="ignore",
    )

    # API settings
    api_title: str = "FactoryLM PLC API"
    api_version: str = "0.1.0"
    api_prefix: str = "/api"

    # CORS settings
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # Network scanner defaults
    scanner_default_timeout: float = 0.3
    scanner_default_port: int = 502
    scanner_max_workers: int = 50
    scanner_default_subnet: str = "192.168.1"
    scanner_default_start: int = 1
    scanner_default_end: int = 254


settings = Settings()
