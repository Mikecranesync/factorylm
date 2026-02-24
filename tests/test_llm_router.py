"""Tests for the LLM Router service — provider routing, circuit breaker, budget."""

import asyncio
import sys
import os
import unittest
from unittest.mock import AsyncMock, patch

# Add the service directory to the path so we can import directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "llm-router"))

from models import ChatMessage, ChatRequest, TaskType
from config import PROVIDERS, MODEL_TO_PROVIDER, TASK_TYPE_ROUTES
from router import (
    SmartRouter,
    ProviderBudget,
    ProviderHealth,
    CIRCUIT_BREAKER_THRESHOLD,
    CIRCUIT_BREAKER_COOLDOWN,
)


def _make_request(model="auto", task_type=None, prefer_provider=None):
    return ChatRequest(
        model=model,
        messages=[ChatMessage(role="user", content="hello")],
        task_type=task_type,
        prefer_provider=prefer_provider,
    )


def _mock_complete_result():
    return {
        "content": "Hello!",
        "finish_reason": "stop",
        "model": "test-model",
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }


class TestTaskTypeRouting(unittest.TestCase):
    """fast->cerebras/groq, reasoning->r1/deepseek/qwen3."""

    def test_fast_routes_to_cerebras_or_groq(self):
        req = _make_request(task_type=TaskType.fast)
        router = SmartRouter()
        candidates = router._resolve_candidates(req)
        self.assertEqual(candidates[:2], ["cerebras", "groq"])

    def test_reasoning_routes_to_r1_deepseek_qwen3(self):
        req = _make_request(task_type=TaskType.reasoning)
        router = SmartRouter()
        candidates = router._resolve_candidates(req)
        self.assertEqual(candidates[:3], ["openrouter-r1", "deepseek", "openrouter-qwen3"])

    def test_coding_routes_to_deepseek_cerebras(self):
        req = _make_request(task_type=TaskType.coding)
        router = SmartRouter()
        candidates = router._resolve_candidates(req)
        self.assertEqual(candidates[:2], ["deepseek", "cerebras"])

    def test_structured_routes_to_groq(self):
        req = _make_request(task_type=TaskType.structured)
        router = SmartRouter()
        candidates = router._resolve_candidates(req)
        self.assertEqual(candidates[0], "groq")


class TestRoundRobin(unittest.TestCase):
    """6 requests with model=auto use different providers."""

    def test_round_robin_cycles_providers(self):
        router = SmartRouter()
        seen = []
        for _ in range(6):
            req = _make_request(model="auto")
            candidates = router._resolve_candidates(req)
            seen.append(candidates[0])
        self.assertEqual(len(set(seen)), 6)


class TestCircuitBreaker(unittest.TestCase):
    """3 failures open circuit, provider skipped."""

    def test_circuit_opens_after_threshold(self):
        router = SmartRouter()
        provider = "cerebras"
        for _ in range(CIRCUIT_BREAKER_THRESHOLD):
            router._record_failure(provider)

        health = router._health[provider]
        self.assertGreater(health.circuit_open_until, 0)
        self.assertEqual(health.consecutive_failures, CIRCUIT_BREAKER_THRESHOLD)

    def test_success_resets_failures(self):
        router = SmartRouter()
        provider = "groq"
        router._record_failure(provider)
        router._record_failure(provider)
        router._record_success(provider)
        health = router._health[provider]
        self.assertEqual(health.consecutive_failures, 0)


class TestBudgetTracking(unittest.TestCase):
    """Exhausted budget excludes provider."""

    def test_budget_exhaustion(self):
        budget = ProviderBudget(daily_limit=100, budget_type="tokens")
        self.assertTrue(budget.is_within_budget())

        budget.record(100)
        self.assertFalse(budget.is_within_budget())
        self.assertEqual(budget.remaining(), 0)

    def test_budget_daily_reset(self):
        budget = ProviderBudget(daily_limit=100, budget_type="tokens")
        budget.record(100)
        self.assertFalse(budget.is_within_budget())

        # Simulate next day
        budget.reset_date = "2020-01-01"
        self.assertTrue(budget.is_within_budget())
        self.assertEqual(budget.remaining(), 100)

    def test_request_budget_type(self):
        budget = ProviderBudget(daily_limit=200, budget_type="requests")
        for _ in range(200):
            budget.record(1)
        self.assertFalse(budget.is_within_budget())


class TestDirectModelRouting(unittest.TestCase):
    """Specific model name -> correct provider."""

    def test_groq_model_resolves(self):
        req = _make_request(model="llama-3.3-70b-versatile")
        router = SmartRouter()
        candidates = router._resolve_candidates(req)
        self.assertEqual(candidates, ["groq"])

    def test_deepseek_model_resolves(self):
        req = _make_request(model="deepseek-chat")
        router = SmartRouter()
        candidates = router._resolve_candidates(req)
        self.assertEqual(candidates, ["deepseek"])

    def test_openrouter_r1_model_resolves(self):
        req = _make_request(model="deepseek/deepseek-r1-0528:free")
        router = SmartRouter()
        candidates = router._resolve_candidates(req)
        self.assertEqual(candidates, ["openrouter-r1"])

    def test_provider_name_as_model(self):
        req = _make_request(model="cerebras")
        router = SmartRouter()
        candidates = router._resolve_candidates(req)
        self.assertEqual(candidates, ["cerebras"])


class TestOpenAICompatibleResponse(unittest.TestCase):
    """Response matches OpenAI chat completion schema."""

    def test_response_schema(self):
        async def _run():
            router = SmartRouter()
            # Mock all provider clients
            for client in router._clients.values():
                client.complete = AsyncMock(return_value=_mock_complete_result())
            # Set fake API keys so providers pass eligibility
            for name, cfg in router._configs.items():
                os.environ[cfg.api_key_env] = "test-key"

            try:
                # Re-create clients so they pick up the env keys
                from providers import UnifiedProvider
                for name, cfg in router._configs.items():
                    router._clients[name] = UnifiedProvider(cfg)
                    router._clients[name].complete = AsyncMock(return_value=_mock_complete_result())

                req = _make_request(model="cerebras")
                prov_name, resp = await router.route(req)

                self.assertEqual(resp.object, "chat.completion")
                self.assertTrue(resp.id.startswith("chatcmpl-"))
                self.assertEqual(len(resp.choices), 1)
                self.assertEqual(resp.choices[0].message.role, "assistant")
                self.assertEqual(resp.choices[0].message.content, "Hello!")
                self.assertEqual(resp.choices[0].finish_reason, "stop")
                self.assertEqual(resp.usage.total_tokens, 15)
                self.assertEqual(resp.x_provider, "cerebras")
            finally:
                # Clean up env vars
                for cfg in router._configs.values():
                    os.environ.pop(cfg.api_key_env, None)

        asyncio.run(_run())


class TestConfig(unittest.TestCase):
    """Provider configuration sanity checks."""

    def test_six_providers_configured(self):
        self.assertEqual(len(PROVIDERS), 6)

    def test_model_to_provider_mapping(self):
        self.assertEqual(MODEL_TO_PROVIDER["deepseek-chat"], "deepseek")
        self.assertEqual(MODEL_TO_PROVIDER["llama-3.3-70b-versatile"], "groq")
        self.assertEqual(MODEL_TO_PROVIDER["gpt-oss-120b"], "cerebras")

    def test_all_task_types_have_routes(self):
        for tt in TaskType:
            self.assertIn(tt.value, TASK_TYPE_ROUTES)

    def test_openrouter_providers_share_key(self):
        or_providers = [p for name, p in PROVIDERS.items() if "openrouter" in name]
        keys = {p.api_key_env for p in or_providers}
        self.assertEqual(keys, {"OPENROUTER_API_KEY"})


if __name__ == "__main__":
    unittest.main()
