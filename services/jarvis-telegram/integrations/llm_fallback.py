"""
LLM Fallback Chain — tries multiple free inference providers in order.

Uses the OpenAI SDK with different base_url values for each provider.
All providers support OpenAI-compatible chat completions.

Provider order (by speed + free limits):
1. Groq       — ~1K req/day, 30 RPM
2. Cerebras   — 1M tokens/day, 30 RPM
3. OpenRouter  — 200-1K req/day, 20 RPM
"""

import asyncio
import logging
from dataclasses import dataclass

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


@dataclass
class Provider:
    name: str
    base_url: str
    api_key: str
    model: str


class LLMFallbackChain:
    """Try multiple free LLM providers in order."""

    def __init__(self, providers: list[dict]):
        self.providers = [Provider(**p) for p in providers]
        self.clients = {
            p.name: AsyncOpenAI(base_url=p.base_url, api_key=p.api_key)
            for p in self.providers
        }
        names = [p.name for p in self.providers]
        logger.info(f"LLM fallback chain initialized: {' → '.join(names)}")

    async def _try_provider(self, provider: Provider, messages: list[dict],
                            max_tokens: int, retries: int = 2) -> str:
        """Try a single provider with retries."""
        client = self.clients[provider.name]
        for attempt in range(retries + 1):
            try:
                response = await client.chat.completions.create(
                    model=provider.model,
                    messages=messages,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content
            except Exception as e:
                if attempt == retries:
                    raise
                logger.warning(f"{provider.name} attempt {attempt + 1}/{retries} failed: {e}")
                await asyncio.sleep(1.0 * (attempt + 1))

    async def chat(self, messages: list[dict], max_tokens: int = 512) -> tuple[str, str]:
        """Try each provider in order. Returns (response_text, provider_name)."""
        errors = []
        for provider in self.providers:
            try:
                text = await self._try_provider(provider, messages, max_tokens)
                return text, provider.name
            except Exception as e:
                logger.warning(f"{provider.name} failed: {e}")
                errors.append(f"{provider.name}: {e}")

        error_summary = "; ".join(errors)
        logger.error(f"All LLM providers failed: {error_summary}")
        return f"All AI providers failed. Errors: {error_summary}", "none"

    @property
    def provider_names(self) -> list[str]:
        return [p.name for p in self.providers]
