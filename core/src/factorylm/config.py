"""
FactoryLM Configuration Management

Loads configuration from environment variables and .env files.
Provides centralized configuration for all FactoryLM components.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False


# Valid LLM providers
VALID_PROVIDERS = ["groq", "deepseek", "claude", "flm"]

# Default models per provider
DEFAULT_MODELS = {
    "groq": "mixtral-8x7b-32768",
    "deepseek": "deepseek-chat",
    "claude": "claude-3-sonnet-20240229",
    "flm": "flm-industrial-v1",
}


@dataclass
class FactoryLMConfig:
    """
    FactoryLM configuration container.

    Attributes:
        llm_provider: LLM provider to use (groq, deepseek, claude, flm)
        llm_api_key: API key for the LLM provider
        llm_model: Model name (provider-specific)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        debug: Enable debug mode
    """

    llm_provider: str = "groq"
    llm_api_key: str = ""
    llm_model: Optional[str] = None
    log_level: str = "INFO"
    debug: bool = False

    def __post_init__(self):
        """Validate configuration after initialization."""
        self.llm_provider = self.llm_provider.lower()
        if self.llm_provider not in VALID_PROVIDERS:
            raise ValueError(
                f"Invalid LLM provider: {self.llm_provider}. "
                f"Valid options: {', '.join(VALID_PROVIDERS)}"
            )

        # Set default model if not specified
        if not self.llm_model:
            self.llm_model = DEFAULT_MODELS.get(self.llm_provider)

    def get_model(self) -> str:
        """Get the configured model name."""
        return self.llm_model or DEFAULT_MODELS.get(self.llm_provider, "")

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary (excluding sensitive data)."""
        return {
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "log_level": self.log_level,
            "debug": self.debug,
            "api_key_set": bool(self.llm_api_key),
        }


def load_env_file(env_path: Optional[str] = None) -> bool:
    """
    Load environment variables from .env file.

    Args:
        env_path: Optional path to .env file. If not provided,
                  searches in current directory and parent directories.

    Returns:
        True if .env file was loaded, False otherwise
    """
    if not DOTENV_AVAILABLE:
        return False

    if env_path:
        path = Path(env_path)
        if path.exists():
            load_dotenv(path)
            return True
        return False

    # Search for .env file
    current = Path.cwd()
    for _ in range(5):  # Search up to 5 levels
        env_file = current / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            return True
        if current.parent == current:
            break
        current = current.parent

    return False


def get_config(env_path: Optional[str] = None) -> FactoryLMConfig:
    """
    Load and return FactoryLM configuration.

    Args:
        env_path: Optional path to .env file

    Returns:
        FactoryLMConfig instance with loaded values

    Example:
        >>> config = get_config()
        >>> print(config.llm_provider)
        'groq'
    """
    # Load .env file if available
    load_env_file(env_path)

    return FactoryLMConfig(
        llm_provider=os.getenv("LLM_PROVIDER", "groq"),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_model=os.getenv("LLM_MODEL") or None,
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        debug=os.getenv("DEBUG", "false").lower() == "true",
    )


def validate_config(config: FactoryLMConfig) -> Dict[str, Any]:
    """
    Validate configuration and return any issues.

    Args:
        config: Configuration to validate

    Returns:
        Dict with 'valid' boolean and 'errors' list
    """
    errors = []

    if config.llm_provider not in VALID_PROVIDERS:
        errors.append(f"Invalid provider: {config.llm_provider}")

    if not config.llm_api_key:
        errors.append("LLM_API_KEY is not set")

    if config.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        errors.append(f"Invalid log level: {config.log_level}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
    }


# Module-level configuration (loaded on import)
# These can be used for backward compatibility
_config = None


def _ensure_config():
    """Ensure configuration is loaded."""
    global _config
    if _config is None:
        _config = get_config()
    return _config


# Convenience accessors
@property
def LLM_PROVIDER() -> str:
    """Get configured LLM provider."""
    return _ensure_config().llm_provider


@property
def LLM_API_KEY() -> str:
    """Get configured LLM API key."""
    return _ensure_config().llm_api_key


@property
def LLM_MODEL() -> str:
    """Get configured LLM model."""
    return _ensure_config().get_model()


# Export commonly used values
def get_llm_provider() -> str:
    """Get the configured LLM provider."""
    return _ensure_config().llm_provider


def get_llm_api_key() -> str:
    """Get the configured LLM API key."""
    return _ensure_config().llm_api_key


def get_llm_model() -> str:
    """Get the configured LLM model."""
    return _ensure_config().get_model()


def get_log_level() -> str:
    """Get the configured log level."""
    return _ensure_config().log_level


def is_debug() -> bool:
    """Check if debug mode is enabled."""
    return _ensure_config().debug
