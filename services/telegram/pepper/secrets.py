"""
PEPPER Secrets Management

Doppler-first with local failover strategy:

Priority Order:
1. Doppler CLI injection (runtime)
2. Doppler Service Token (API fetch)
3. Local encrypted cache (~/.pepper/secrets.enc)
4. Environment variables (.env file)

Usage:
    from secrets import get_secret, SecretsManager

    # Simple access
    token = get_secret("PEPPER_PRIME_TOKEN")

    # With manager
    secrets = SecretsManager()
    await secrets.initialize()
    token = secrets.get("PEPPER_PRIME_TOKEN")
"""

import os
import json
import logging
import subprocess
import base64
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import hashlib

logger = logging.getLogger(__name__)


class SecretSource(Enum):
    """Where the secret was loaded from."""
    DOPPLER_CLI = "doppler_cli"
    DOPPLER_API = "doppler_api"
    LOCAL_CACHE = "local_cache"
    ENV_FILE = "env_file"
    ENVIRONMENT = "environment"
    NOT_FOUND = "not_found"


@dataclass
class SecretResult:
    """Result of secret lookup."""
    value: Optional[str]
    source: SecretSource
    cached: bool = False


# Required secrets for PEPPER
REQUIRED_SECRETS = [
    "PEPPER_PRIME_TOKEN",
    "GROQ_API_KEY",
]

OPTIONAL_SECRETS = [
    "FACTORYLM_BOT_TOKEN",
    "ANTHROPIC_API_KEY",
    "HONEYCOMB_API_KEY",
    "SENTRY_DSN",
]

# Doppler configuration
DOPPLER_PROJECT = "voltron"
DOPPLER_CONFIG = "dev"


class SecretsManager:
    """
    Manages secrets with Doppler-first, failover strategy.

    Failover chain:
    1. Check if Doppler CLI injected (env vars from `doppler run`)
    2. Try Doppler API with service token
    3. Load from encrypted local cache
    4. Fall back to .env file
    """

    def __init__(
        self,
        project: str = DOPPLER_PROJECT,
        config: str = DOPPLER_CONFIG,
        cache_dir: Optional[Path] = None
    ):
        self.project = project
        self.config = config
        self.cache_dir = cache_dir or Path.home() / ".pepper"
        self.cache_file = self.cache_dir / "secrets.enc"
        self._secrets: Dict[str, SecretResult] = {}
        self._initialized = False
        self._source_used: Optional[SecretSource] = None

    async def initialize(self) -> bool:
        """
        Initialize secrets from best available source.

        Returns:
            True if required secrets are available
        """
        # Try sources in priority order
        if self._try_doppler_cli():
            self._source_used = SecretSource.DOPPLER_CLI
            logger.info("Secrets loaded from Doppler CLI injection")
        elif self._try_doppler_api():
            self._source_used = SecretSource.DOPPLER_API
            logger.info("Secrets loaded from Doppler API")
        elif self._try_local_cache():
            self._source_used = SecretSource.LOCAL_CACHE
            logger.warning("Secrets loaded from local cache (Doppler unavailable)")
        elif self._try_env_file():
            self._source_used = SecretSource.ENV_FILE
            logger.warning("Secrets loaded from .env file (Doppler unavailable)")
        else:
            logger.error("No secrets source available!")
            return False

        self._initialized = True

        # Validate required secrets
        missing = self._check_required()
        if missing:
            logger.error(f"Missing required secrets: {missing}")
            return False

        # Update cache if we got fresh secrets
        if self._source_used in (SecretSource.DOPPLER_CLI, SecretSource.DOPPLER_API):
            self._update_cache()

        return True

    def _try_doppler_cli(self) -> bool:
        """Check if Doppler CLI injected secrets (via `doppler run`)."""
        # Doppler sets these when running via CLI
        if os.getenv("DOPPLER_PROJECT") == self.project:
            logger.debug("Detected Doppler CLI injection")
            for key in REQUIRED_SECRETS + OPTIONAL_SECRETS:
                value = os.getenv(key)
                if value:
                    self._secrets[key] = SecretResult(
                        value=value,
                        source=SecretSource.DOPPLER_CLI
                    )
            return bool(self._secrets)
        return False

    def _try_doppler_api(self) -> bool:
        """Fetch secrets via Doppler CLI command."""
        try:
            result = subprocess.run(
                [
                    "doppler", "secrets", "download",
                    "--project", self.project,
                    "--config", self.config,
                    "--format", "json",
                    "--no-file"
                ],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                secrets = json.loads(result.stdout)
                for key in REQUIRED_SECRETS + OPTIONAL_SECRETS:
                    if key in secrets and secrets[key]:
                        self._secrets[key] = SecretResult(
                            value=secrets[key],
                            source=SecretSource.DOPPLER_API
                        )
                return bool(self._secrets)

        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
            logger.debug(f"Doppler API fetch failed: {e}")

        return False

    def _try_local_cache(self) -> bool:
        """Load secrets from encrypted local cache."""
        if not self.cache_file.exists():
            return False

        try:
            # Simple obfuscation (not true encryption - use for failover only)
            with open(self.cache_file, "rb") as f:
                data = base64.b64decode(f.read())
                secrets = json.loads(data.decode())

            for key, value in secrets.items():
                if key in REQUIRED_SECRETS + OPTIONAL_SECRETS:
                    self._secrets[key] = SecretResult(
                        value=value,
                        source=SecretSource.LOCAL_CACHE,
                        cached=True
                    )
            return bool(self._secrets)

        except Exception as e:
            logger.debug(f"Cache load failed: {e}")
            return False

    def _try_env_file(self) -> bool:
        """Load secrets from .env file."""
        env_paths = [
            Path.cwd() / ".env",
            Path(__file__).parent / ".env",
            Path.home() / ".pepper" / ".env",
        ]

        for env_path in env_paths:
            if env_path.exists():
                try:
                    with open(env_path) as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                key, value = line.split("=", 1)
                                key = key.strip()
                                value = value.strip().strip('"').strip("'")
                                if key in REQUIRED_SECRETS + OPTIONAL_SECRETS:
                                    self._secrets[key] = SecretResult(
                                        value=value,
                                        source=SecretSource.ENV_FILE
                                    )
                    if self._secrets:
                        return True
                except Exception as e:
                    logger.debug(f"Env file load failed: {e}")

        return False

    def _check_required(self) -> list[str]:
        """Check for missing required secrets."""
        missing = []
        for key in REQUIRED_SECRETS:
            result = self._secrets.get(key)
            if not result or not result.value:
                missing.append(key)
        return missing

    def _update_cache(self):
        """Update local cache with fresh secrets."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

            # Only cache non-empty values
            cache_data = {
                k: v.value for k, v in self._secrets.items()
                if v.value
            }

            # Simple obfuscation
            encoded = base64.b64encode(
                json.dumps(cache_data).encode()
            )

            with open(self.cache_file, "wb") as f:
                f.write(encoded)

            # Restrict permissions
            self.cache_file.chmod(0o600)

            logger.debug(f"Updated secrets cache: {self.cache_file}")

        except Exception as e:
            logger.warning(f"Failed to update cache: {e}")

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a secret value."""
        result = self._secrets.get(key)
        if result and result.value:
            return result.value
        return default

    def get_source(self, key: str) -> SecretSource:
        """Get the source of a secret."""
        result = self._secrets.get(key)
        return result.source if result else SecretSource.NOT_FOUND

    def is_cached(self, key: str) -> bool:
        """Check if secret was loaded from cache."""
        result = self._secrets.get(key)
        return result.cached if result else False

    def get_status(self) -> Dict[str, Any]:
        """Get secrets status summary."""
        return {
            "initialized": self._initialized,
            "source": self._source_used.value if self._source_used else None,
            "secrets_loaded": len(self._secrets),
            "required_present": len([
                k for k in REQUIRED_SECRETS
                if self._secrets.get(k) and self._secrets[k].value
            ]),
            "required_total": len(REQUIRED_SECRETS),
            "cache_exists": self.cache_file.exists(),
        }


# Singleton instance
_manager: Optional[SecretsManager] = None


def get_secrets_manager() -> SecretsManager:
    """Get or create the secrets manager singleton."""
    global _manager
    if _manager is None:
        _manager = SecretsManager()
    return _manager


def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Quick access to a secret value.

    Falls back through: Doppler CLI → Doppler API → Cache → .env → Environment
    """
    # First check if already in environment (Doppler CLI or direct)
    value = os.getenv(key)
    if value:
        return value

    # Try the manager
    manager = get_secrets_manager()
    if manager._initialized:
        return manager.get(key, default)

    # Last resort - return default
    return default


async def initialize_secrets() -> bool:
    """Initialize the secrets manager."""
    manager = get_secrets_manager()
    return await manager.initialize()
