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
    # --- primary providers (round-robin hits these first) ---
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
    "openrouter-hermes": ProviderConfig(
        name="openrouter-hermes",
        base_url="https://openrouter.ai/api/v1",
        model="nousresearch/hermes-3-llama-3.1-405b:free",
        api_key_env="OPENROUTER_API_KEY",
        daily_budget=200,
        budget_type="requests",
    ),
    "openrouter-qwen3": ProviderConfig(
        name="openrouter-qwen3",
        base_url="https://openrouter.ai/api/v1",
        model="qwen/qwen3-coder:free",
        api_key_env="OPENROUTER_API_KEY",
        daily_budget=200,
        budget_type="requests",
    ),
    "openrouter-llama70b": ProviderConfig(
        name="openrouter-llama70b",
        base_url="https://openrouter.ai/api/v1",
        model="meta-llama/llama-3.3-70b-instruct:free",
        api_key_env="OPENROUTER_API_KEY",
        daily_budget=200,
        budget_type="requests",
    ),
    # --- last-resort fallback ---
    "cerebras": ProviderConfig(
        name="cerebras",
        base_url="https://api.cerebras.ai/v1",
        model="gpt-oss-120b",
        api_key_env="CEREBRAS_API_KEY",
        daily_budget=1_000_000,
        budget_type="tokens",
    ),
}

# Reverse mapping: model name → provider name
MODEL_TO_PROVIDER: dict[str, str] = {
    cfg.model: name for name, cfg in PROVIDERS.items()
}

# Task-type → ordered list of preferred providers
TASK_TYPE_ROUTES: dict[str, list[str]] = {
    "fast": ["groq", "deepseek"],
    "reasoning": ["openrouter-hermes", "deepseek", "openrouter-qwen3"],
    "structured": ["groq", "deepseek"],
    "coding": ["deepseek", "groq"],
}
