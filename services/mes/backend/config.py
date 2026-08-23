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

    # plc-modbus service URL — MES calls this over HTTP (never raw Modbus TCP)
    plc_modbus_url: str = "http://plc-modbus:8001"

    # Polling interval in seconds (default 5, set lower in tests)
    plc_poll_interval_sec: int = 5

    # OEE calculator tick interval in seconds (default 60)
    oee_tick_sec: int = 60

    # Set True to skip background task startup (useful in unit tests)
    plc_use_mock: bool = False

    # CMMS sync via GitHub Gist — disabled by default (set token to enable)
    cmms_enabled: bool = False
    cmms_github_token: str = ""   # GitHub PAT with gist scope (via Doppler)


settings = Settings()
