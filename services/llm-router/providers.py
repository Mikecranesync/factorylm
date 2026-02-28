"""UnifiedProvider — thin AsyncOpenAI wrapper per provider."""

from __future__ import annotations

import logging
from typing import Any

from openai import AsyncOpenAI

from config import ProviderConfig

logger = logging.getLogger("llm-router.providers")

# OpenRouter requires these headers for free-tier access
_OPENROUTER_HEADERS = {
    "HTTP-Referer": "https://factorylm.com",
    "X-Title": "FactoryLM",
}


class UnifiedProvider:
    """Single async OpenAI-compatible client for one provider."""

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        extra_headers = (
            _OPENROUTER_HEADERS if "openrouter" in config.name else None
        )
        self._client = AsyncOpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
            default_headers=extra_headers,
        )

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        """Call the provider and return raw OpenAI-shaped response dict."""
        resp = await self._client.chat.completions.create(
            model=model or self.config.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        choice = resp.choices[0]
        usage = resp.usage or type("U", (), {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})()
        return {
            "content": choice.message.content or "",
            "finish_reason": choice.finish_reason or "stop",
            "model": resp.model,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
        }
