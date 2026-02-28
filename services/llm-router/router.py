"""SmartRouter — budget + circuit breaker + task-type routing + round-robin."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date

from config import MODEL_TO_PROVIDER, PROVIDERS, TASK_TYPE_ROUTES, ProviderConfig
from models import ChatRequest, ChatResponse, ChatChoice, ChatMessage, ChatUsage
from providers import UnifiedProvider

logger = logging.getLogger("llm-router.router")

# ---------------------------------------------------------------------------
# Inlined from openclaw/llm/budget.py — provider budget tracking
# ---------------------------------------------------------------------------

@dataclass
class ProviderBudget:
    daily_limit: int
    used: int = 0
    budget_type: str = "tokens"  # "tokens" or "requests"
    reset_date: str = field(default_factory=lambda: str(date.today()))

    def record(self, amount: int = 1) -> None:
        self._maybe_reset()
        self.used += amount

    def is_within_budget(self) -> bool:
        self._maybe_reset()
        return self.used < self.daily_limit

    def remaining(self) -> int:
        self._maybe_reset()
        return max(0, self.daily_limit - self.used)

    def _maybe_reset(self) -> None:
        today = str(date.today())
        if self.reset_date != today:
            self.used = 0
            self.reset_date = today


# ---------------------------------------------------------------------------
# Inlined from output/vps-patches/router.py — circuit breaker
# ---------------------------------------------------------------------------

CIRCUIT_BREAKER_THRESHOLD = 3   # failures before opening circuit
CIRCUIT_BREAKER_COOLDOWN = 300  # seconds before retrying


@dataclass
class ProviderHealth:
    consecutive_failures: int = 0
    last_failure: float = 0.0
    circuit_open_until: float = 0.0


# ---------------------------------------------------------------------------
# SmartRouter
# ---------------------------------------------------------------------------

class SmartRouter:
    def __init__(self, providers: dict[str, ProviderConfig] | None = None) -> None:
        self._configs = providers or PROVIDERS
        self._clients: dict[str, UnifiedProvider] = {
            name: UnifiedProvider(cfg) for name, cfg in self._configs.items()
        }
        self._budgets: dict[str, ProviderBudget] = {
            name: ProviderBudget(
                daily_limit=cfg.daily_budget,
                budget_type=cfg.budget_type,
            )
            for name, cfg in self._configs.items()
        }
        self._health: dict[str, ProviderHealth] = {}
        self._rr_index = 0  # round-robin counter

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    async def route(self, request: ChatRequest) -> tuple[str, ChatResponse]:
        """Pick a provider and execute the request. Returns (provider_name, response)."""
        candidates = self._resolve_candidates(request)
        eligible = self._filter_eligible(candidates)

        if not eligible:
            raise RuntimeError(
                f"All providers exhausted (tried: {candidates}). "
                "Check budgets and circuit breakers."
            )

        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        last_err: Exception | None = None

        for provider_name in eligible:
            client = self._clients[provider_name]
            try:
                raw = await client.complete(
                    messages=messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                )
                # Record budget usage
                budget = self._budgets[provider_name]
                amount = raw["total_tokens"] if budget.budget_type == "tokens" else 1
                budget.record(amount)

                self._record_success(provider_name)

                return provider_name, ChatResponse(
                    model=raw["model"],
                    choices=[ChatChoice(message=ChatMessage(
                        role="assistant",
                        content=raw["content"],
                    ), finish_reason=raw["finish_reason"])],
                    usage=ChatUsage(
                        prompt_tokens=raw["prompt_tokens"],
                        completion_tokens=raw["completion_tokens"],
                        total_tokens=raw["total_tokens"],
                    ),
                    x_provider=provider_name,
                )

            except Exception as exc:
                logger.warning("Provider %s failed: %s", provider_name, exc)
                self._record_failure(provider_name)
                last_err = exc
                continue

        raise RuntimeError(
            f"All eligible providers failed (tried: {eligible}). Last error: {last_err}"
        )

    def get_provider_status(self) -> list[dict]:
        """Return status of all providers for /health."""
        now = time.monotonic()
        statuses = []
        for name, cfg in self._configs.items():
            budget = self._budgets[name]
            health = self._health.get(name, ProviderHealth())
            circuit_open = now < health.circuit_open_until
            statuses.append({
                "name": name,
                "model": cfg.model,
                "budget_type": budget.budget_type,
                "budget_used": budget.used,
                "budget_limit": budget.daily_limit,
                "budget_remaining": budget.remaining(),
                "circuit_open": circuit_open,
                "consecutive_failures": health.consecutive_failures,
                "has_api_key": bool(cfg.api_key),
            })
        return statuses

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def _resolve_candidates(self, request: ChatRequest) -> list[str]:
        """Determine candidate providers in priority order."""
        model = request.model

        # 1. Direct model name → specific provider
        if model in MODEL_TO_PROVIDER:
            return [MODEL_TO_PROVIDER[model]]

        # 2. Provider name used as model (e.g. model="cerebras")
        if model in self._configs:
            return [model]

        # 3. prefer_provider → try that first, then others
        if request.prefer_provider and request.prefer_provider in self._configs:
            others = [n for n in self._configs if n != request.prefer_provider]
            return [request.prefer_provider] + others

        # 4. task_type routing
        if request.task_type:
            primaries = TASK_TYPE_ROUTES.get(request.task_type.value, [])
            others = [n for n in self._configs if n not in primaries]
            return primaries + others

        # 5. Round-robin across all providers
        names = list(self._configs.keys())
        idx = self._rr_index % len(names)
        self._rr_index += 1
        return names[idx:] + names[:idx]

    def _filter_eligible(self, candidates: list[str]) -> list[str]:
        """Remove over-budget and circuit-open providers."""
        now = time.monotonic()
        eligible = []
        for name in candidates:
            if not self._budgets[name].is_within_budget():
                logger.info("Provider %s over budget, skipping", name)
                continue
            health = self._health.get(name)
            if health and now < health.circuit_open_until:
                logger.info("Circuit open for %s, skipping", name)
                continue
            if not self._configs[name].api_key:
                logger.info("Provider %s has no API key, skipping", name)
                continue
            eligible.append(name)
        return eligible

    # ------------------------------------------------------------------
    # Circuit breaker
    # ------------------------------------------------------------------

    def _record_success(self, provider_name: str) -> None:
        health = self._health.get(provider_name)
        if health:
            health.consecutive_failures = 0

    def _record_failure(self, provider_name: str) -> None:
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
                "Circuit breaker OPEN for %s after %d failures (cooldown %ds)",
                provider_name,
                health.consecutive_failures,
                CIRCUIT_BREAKER_COOLDOWN,
            )
