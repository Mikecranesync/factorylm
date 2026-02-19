"""LLM Router — selects provider by intent with fallback chain."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from openclaw.llm.base import LLMProvider, LLMResponse
from openclaw.llm.budget import BudgetTracker
from openclaw.types import Intent

logger = logging.getLogger(__name__)


@dataclass
class Route:
    primary: str
    fallbacks: list[str] = field(default_factory=list)


@dataclass
class ProviderHealth:
    """Track consecutive failures for circuit breaker logic."""

    consecutive_failures: int = 0
    last_failure: float = 0.0
    circuit_open_until: float = 0.0


# Circuit breaker settings
CIRCUIT_BREAKER_THRESHOLD = 3  # failures before opening circuit
CIRCUIT_BREAKER_COOLDOWN = 300  # 5 minutes before retrying


# Default routing table
DEFAULT_ROUTES: dict[Intent, Route] = {
    Intent.DIAGNOSE: Route("openrouter", ["groq", "deepseek", "nvidia", "openai"]),
    Intent.STATUS: Route("groq", ["openai"]),
    Intent.PHOTO: Route("openrouter", ["gemini", "openai"]),
    Intent.WORK_ORDER: Route("openrouter", ["groq", "deepseek", "anthropic", "openai"]),
    Intent.CHAT: Route("groq", ["deepseek", "openrouter", "openai"]),
    Intent.SEARCH: Route("groq", []),
    Intent.ADMIN: Route("groq", []),
    Intent.HELP: Route("groq", []),
    Intent.DIAGRAM: Route("openrouter", ["groq", "deepseek", "anthropic"]),
    Intent.GIST: Route("openrouter", ["groq", "deepseek", "anthropic"]),
    Intent.PROJECT: Route("openrouter", ["groq", "deepseek", "anthropic"]),
    Intent.TROUBLESHOOT: Route("groq", ["deepseek", "openrouter"]),
    Intent.UNKNOWN: Route("groq", ["deepseek", "openrouter", "openai"]),
}


class LLMRouter:
    """Selects the right LLM provider based on intent, budget, and availability."""

    def __init__(
        self,
        providers: dict[str, LLMProvider],
        budget: BudgetTracker | None = None,
        routes: dict[Intent, Route] | None = None,
    ) -> None:
        self.providers = providers
        self.budget = budget or BudgetTracker()
        self.routes = routes or DEFAULT_ROUTES
        self._health: dict[str, ProviderHealth] = {}

    async def route(
        self,
        intent: Intent,
        messages: list[dict],
        system_prompt: str = "",
        images: list[bytes] | None = None,
        prefer: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.3,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Select provider and execute request with automatic fallback."""
        now = time.monotonic()

        # If explicit provider requested
        if prefer and prefer in self.providers:
            provider = self.providers[prefer]
            if provider.is_available() and self.budget.is_within_budget(prefer):
                health = self._health.get(prefer)
                if not health or now >= health.circuit_open_until:
                    try:
                        response = await self._call(provider, messages, system_prompt, images, max_tokens, temperature, json_mode)
                        self._record_success(prefer)
                        return response
                    except Exception:
                        self._record_failure(prefer)
                        logger.exception("Preferred provider %s failed", prefer)

        # Get route for this intent
        route = self.routes.get(intent, Route("groq", ["openai"]))
        candidates = [route.primary] + route.fallbacks

        attempted = []
        for provider_name in candidates:
            provider = self.providers.get(provider_name)
            if not provider or not provider.is_available():
                continue
            if not self.budget.is_within_budget(provider_name):
                logger.warning("Provider %s over budget, skipping", provider_name)
                continue
            if images and not provider.supports_vision():
                continue

            # Circuit breaker check
            health = self._health.get(provider_name)
            if health and now < health.circuit_open_until:
                logger.info(
                    "Circuit open for %s (skip for %.0fs more), trying next",
                    provider_name,
                    health.circuit_open_until - now,
                )
                continue

            attempted.append(provider_name)
            try:
                response = await self._call(provider, messages, system_prompt, images, max_tokens, temperature, json_mode)
                self.budget.record(provider_name, response.tokens_used)
                self._record_success(provider_name)
                return response
            except Exception:
                logger.exception("Provider %s failed, trying fallback", provider_name)
                self._record_failure(provider_name)
                continue

        raise RuntimeError(
            f"All LLM providers exhausted for intent={intent.value}, "
            f"tried: {attempted or candidates}"
        )

    def _record_success(self, provider_name: str) -> None:
        """Reset failure counter on success."""
        health = self._health.get(provider_name)
        if health:
            health.consecutive_failures = 0

    def _record_failure(self, provider_name: str) -> None:
        """Increment failure counter; open circuit if threshold reached."""
        now = time.monotonic()
        health = self._health.get(provider_name)
        if not health:
            health = ProviderHealth()
            self._health[provider_name] = health

        health.consecutive_failures += 1
        health.last_failure = now

        if health.consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD:
            health.circuit_open_until = now + CIRCUIT_BREAKER_COOLDOWN
            logger.warning(
                "Circuit breaker OPEN for %s after %d consecutive failures (cooldown %ds)",
                provider_name,
                health.consecutive_failures,
                CIRCUIT_BREAKER_COOLDOWN,
            )

    async def _call(
        self,
        provider: LLMProvider,
        messages: list[dict],
        system_prompt: str,
        images: list[bytes] | None,
        max_tokens: int,
        temperature: float,
        json_mode: bool = False,
    ) -> LLMResponse:
        start = time.monotonic()
        if images:
            response = await provider.complete_with_vision(
                messages, images, system_prompt=system_prompt, max_tokens=max_tokens
            )
        else:
            response = await provider.complete(
                messages, system_prompt=system_prompt, max_tokens=max_tokens, temperature=temperature,
                json_mode=json_mode,
            )
        response.latency_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "LLM response: provider=%s model=%s tokens=%d latency=%dms",
            response.provider, response.model, response.tokens_used, response.latency_ms,
        )
        return response
