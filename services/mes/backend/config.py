"""MES service configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FACTORYLM_",
        env_file=".env",
        extra="ignore",
    )

    api_title: str = "FactoryLM MES API"
    api_version: str = "0.1.0"
    api_prefix: str = "/api"

    # PostgreSQL connection string
    # Format: postgresql://user:password@host:port/dbname
    database_url: str = "postgresql://mes:meslocal@localhost:5434/mes_core"

    # PLC defaults (overridden per-line from DB)
    plc_poll_interval_sec: int = 5
    plc_use_mock: bool = False


settings = Settings()
