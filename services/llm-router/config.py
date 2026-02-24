"""Provider configuration — loaded from Doppler env vars at startup."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    model: str
    api_key_env: str
    daily_budget: int
    budget_type: str  # "tokens" or "requests"

    @property
    def api_key(self) -> str:
        return os.environ.get(self.api_key_env, "")


PROVIDERS: dict[str, ProviderConfig] = {
    "cerebras": ProviderConfig(
        name="cerebras",
        base_url="https://api.cerebras.ai/v1",
        model="gpt-oss-120b",
        api_key_env="CEREBRAS_API_KEY",
        daily_budget=1_000_000,
        budget_type="tokens",
    ),
    "groq": ProviderConfig(
        name="groq",
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        daily_budget=14_400,
        budget_type="requests",
    ),
    "deepseek": ProviderConfig(
        name="deepseek",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        api_key_env="DEEPSEEK_API_KEY",
        daily_budget=400_000,
        budget_type="tokens",
    ),
    "openrouter-r1": ProviderConfig(
        name="openrouter-r1",
        base_url="https://openrouter.ai/api/v1",
        model="deepseek/deepseek-r1-0528:free",
        api_key_env="OPENROUTER_API_KEY",
        daily_budget=200,
        budget_type="requests",
    ),
    "openrouter-qwen3": ProviderConfig(
        name="openrouter-qwen3",
        base_url="https://openrouter.ai/api/v1",
        model="qwen/qwen3-235b-a22b:free",
        api_key_env="OPENROUTER_API_KEY",
        daily_budget=200,
        budget_type="requests",
    ),
    "openrouter-maverick": ProviderConfig(
        name="openrouter-maverick",
        base_url="https://openrouter.ai/api/v1",
        model="meta-llama/llama-4-maverick:free",
        api_key_env="OPENROUTER_API_KEY",
        daily_budget=200,
        budget_type="requests",
    ),
}

# Reverse mapping: model name → provider name
MODEL_TO_PROVIDER: dict[str, str] = {
    cfg.model: name for name, cfg in PROVIDERS.items()
}

# Task-type → ordered list of preferred providers
TASK_TYPE_ROUTES: dict[str, list[str]] = {
    "fast": ["cerebras", "groq"],
    "reasoning": ["openrouter-r1", "deepseek", "openrouter-qwen3"],
    "structured": ["groq"],
    "coding": ["deepseek", "cerebras"],
}
