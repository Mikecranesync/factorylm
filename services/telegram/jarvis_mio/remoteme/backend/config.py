"""
RemoteMe Configuration
======================
Load settings from environment variables.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
ENV_FILE = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_FILE)


class Settings:
    """Application settings from environment"""
    
    # App
    APP_NAME: str = "RemoteMe"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./remoteme.db")
    
    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    MIKE_TELEGRAM_ID: str = os.getenv("MIKE_TELEGRAM_ID", "8445149012")
    
    # Anthropic (for command parsing)
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    
    # LangFuse (observability)
    LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    
    # Stripe (billing) - Phase 3
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    
    # Nodes (Tailscale IPs)
    NODES: dict = {
        "plc-laptop": {
            "ip": os.getenv("PLC_LAPTOP_IP", "100.72.2.99"),
            "port": int(os.getenv("PLC_LAPTOP_PORT", "8765")),
        },
        "travel-laptop": {
            "ip": os.getenv("TRAVEL_LAPTOP_IP", "100.83.251.23"),
            "port": int(os.getenv("TRAVEL_LAPTOP_PORT", "8765")),
        }
    }
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
    
    # Paths
    UPLOAD_DIR: Path = Path(os.getenv("UPLOAD_DIR", "/opt/remoteme/uploads"))
    RECORDINGS_DIR: Path = Path(os.getenv("RECORDINGS_DIR", "/opt/remoteme/recordings"))


settings = Settings()

# Ensure directories exist
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
