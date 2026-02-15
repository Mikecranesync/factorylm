"""
API Key Validator
==================

Validates API keys for external services.

Tests:
- Groq API key
- Anthropic (Claude) API key
- Telegram bot tokens
- Other service keys

Uses minimal test requests to avoid quota consumption.
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class KeyStatus:
    """API key validation status."""
    provider: str
    valid: bool
    error: Optional[str] = None
    tested_at: Optional[datetime] = None
    response_time_ms: Optional[float] = None

    @property
    def is_valid(self) -> bool:
        """Quick validation check."""
        return self.valid


class APIValidator:
    """
    API key validator.

    Tests API keys with minimal requests to validate they work.
    """

    def __init__(self, config: dict):
        """
        Initialize API validator.

        Args:
            config: Watchdog configuration from watchdog.yaml
        """
        self.config = config
        self.api_config = config.get("api_validation", {})
        self.providers = self.api_config.get("providers", [])
        self.timeout = 15  # Longer timeout for API calls

    async def validate_all(self) -> Dict[str, KeyStatus]:
        """
        Validate all configured API keys.

        Returns:
            Dictionary mapping provider name to KeyStatus
        """
        logger.info("Starting API key validation")
        results = {}

        # Validate all providers concurrently
        tasks = [
            self._validate_provider(provider)
            for provider in self.providers
        ]

        provider_results = await asyncio.gather(*tasks, return_exceptions=True)

        for provider, result in zip(self.providers, provider_results):
            provider_name = provider["name"]

            if isinstance(result, Exception):
                logger.error(f"API validation failed for {provider_name}: {result}")
                results[provider_name] = KeyStatus(
                    provider=provider_name,
                    valid=False,
                    error=str(result),
                    tested_at=datetime.now(),
                )
            else:
                results[provider_name] = result

        valid_count = sum(1 for status in results.values() if status.is_valid)
        logger.info(
            f"API validation complete: {valid_count}/{len(results)} keys valid"
        )

        return results

    async def _validate_provider(self, provider: dict) -> KeyStatus:
        """
        Validate a single API provider.

        Args:
            provider: Provider configuration

        Returns:
            KeyStatus for this provider
        """
        provider_name = provider["name"]
        env_var = provider["env_var"]
        test_endpoint = provider["test_endpoint"]

        # Get API key from environment
        api_key = os.getenv(env_var)

        if not api_key:
            logger.warning(f"API key not found in environment: {env_var}")
            return KeyStatus(
                provider=provider_name,
                valid=False,
                error=f"Environment variable {env_var} not set",
                tested_at=datetime.now(),
            )

        # Route to appropriate validation method
        if "groq" in provider_name.lower():
            return await self._validate_groq(provider_name, api_key)
        elif "anthropic" in provider_name.lower():
            return await self._validate_anthropic(provider_name, api_key)
        elif "telegram" in provider_name.lower():
            return await self._validate_telegram(provider_name, api_key)
        else:
            logger.warning(f"Unknown provider type: {provider_name}")
            return KeyStatus(
                provider=provider_name,
                valid=False,
                error="Unknown provider type",
                tested_at=datetime.now(),
            )

    async def _validate_groq(self, provider_name: str, api_key: str) -> KeyStatus:
        """
        Validate Groq API key.

        Args:
            provider_name: Provider identifier
            api_key: API key to test

        Returns:
            KeyStatus
        """
        start_time = datetime.now()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "llama-3.1-8b-instant",
                        "messages": [{"role": "user", "content": "test"}],
                        "max_tokens": 5,
                    },
                )

                response_time = (datetime.now() - start_time).total_seconds() * 1000

                if response.status_code == 200:
                    logger.debug(f"Groq API key valid: {provider_name}")
                    return KeyStatus(
                        provider=provider_name,
                        valid=True,
                        tested_at=datetime.now(),
                        response_time_ms=response_time,
                    )
                elif response.status_code == 401:
                    logger.error(f"Groq API key invalid: {provider_name}")
                    return KeyStatus(
                        provider=provider_name,
                        valid=False,
                        error="Invalid API key (401 Unauthorized)",
                        tested_at=datetime.now(),
                        response_time_ms=response_time,
                    )
                else:
                    logger.warning(
                        f"Groq API unexpected response: {response.status_code}"
                    )
                    return KeyStatus(
                        provider=provider_name,
                        valid=False,
                        error=f"HTTP {response.status_code}: {response.text[:100]}",
                        tested_at=datetime.now(),
                        response_time_ms=response_time,
                    )

        except httpx.TimeoutException:
            logger.error(f"Groq API timeout: {provider_name}")
            return KeyStatus(
                provider=provider_name,
                valid=False,
                error="Request timeout",
                tested_at=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Groq API validation error: {e}")
            return KeyStatus(
                provider=provider_name,
                valid=False,
                error=str(e),
                tested_at=datetime.now(),
            )

    async def _validate_anthropic(
        self, provider_name: str, api_key: str
    ) -> KeyStatus:
        """
        Validate Anthropic (Claude) API key.

        Args:
            provider_name: Provider identifier
            api_key: API key to test

        Returns:
            KeyStatus
        """
        start_time = datetime.now()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 5,
                        "messages": [{"role": "user", "content": "test"}],
                    },
                )

                response_time = (datetime.now() - start_time).total_seconds() * 1000

                if response.status_code == 200:
                    logger.debug(f"Anthropic API key valid: {provider_name}")
                    return KeyStatus(
                        provider=provider_name,
                        valid=True,
                        tested_at=datetime.now(),
                        response_time_ms=response_time,
                    )
                elif response.status_code == 401:
                    logger.error(f"Anthropic API key invalid: {provider_name}")
                    return KeyStatus(
                        provider=provider_name,
                        valid=False,
                        error="Invalid API key (401 Unauthorized)",
                        tested_at=datetime.now(),
                        response_time_ms=response_time,
                    )
                else:
                    logger.warning(
                        f"Anthropic API unexpected response: {response.status_code}"
                    )
                    return KeyStatus(
                        provider=provider_name,
                        valid=False,
                        error=f"HTTP {response.status_code}: {response.text[:100]}",
                        tested_at=datetime.now(),
                        response_time_ms=response_time,
                    )

        except httpx.TimeoutException:
            logger.error(f"Anthropic API timeout: {provider_name}")
            return KeyStatus(
                provider=provider_name,
                valid=False,
                error="Request timeout",
                tested_at=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Anthropic API validation error: {e}")
            return KeyStatus(
                provider=provider_name,
                valid=False,
                error=str(e),
                tested_at=datetime.now(),
            )

    async def _validate_telegram(
        self, provider_name: str, bot_token: str
    ) -> KeyStatus:
        """
        Validate Telegram bot token.

        Args:
            provider_name: Provider identifier
            bot_token: Bot token to test

        Returns:
            KeyStatus
        """
        start_time = datetime.now()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"https://api.telegram.org/bot{bot_token}/getMe"
                )

                response_time = (datetime.now() - start_time).total_seconds() * 1000

                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        bot_info = data.get("result", {})
                        logger.debug(
                            f"Telegram bot token valid: {provider_name} "
                            f"(@{bot_info.get('username', 'unknown')})"
                        )
                        return KeyStatus(
                            provider=provider_name,
                            valid=True,
                            tested_at=datetime.now(),
                            response_time_ms=response_time,
                        )
                    else:
                        logger.error(f"Telegram API error: {data.get('description')}")
                        return KeyStatus(
                            provider=provider_name,
                            valid=False,
                            error=data.get("description", "Unknown error"),
                            tested_at=datetime.now(),
                            response_time_ms=response_time,
                        )
                elif response.status_code == 401:
                    logger.error(f"Telegram bot token invalid: {provider_name}")
                    return KeyStatus(
                        provider=provider_name,
                        valid=False,
                        error="Invalid bot token (401 Unauthorized)",
                        tested_at=datetime.now(),
                        response_time_ms=response_time,
                    )
                else:
                    logger.warning(
                        f"Telegram API unexpected response: {response.status_code}"
                    )
                    return KeyStatus(
                        provider=provider_name,
                        valid=False,
                        error=f"HTTP {response.status_code}",
                        tested_at=datetime.now(),
                        response_time_ms=response_time,
                    )

        except httpx.TimeoutException:
            logger.error(f"Telegram API timeout: {provider_name}")
            return KeyStatus(
                provider=provider_name,
                valid=False,
                error="Request timeout",
                tested_at=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Telegram API validation error: {e}")
            return KeyStatus(
                provider=provider_name,
                valid=False,
                error=str(e),
                tested_at=datetime.now(),
            )
