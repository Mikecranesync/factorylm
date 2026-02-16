"""
LLM Client Factory Module

Provides factory function to create appropriate LLM client based on provider.
"""

from factorylm.llm.base import BaseLLMClient, LLMResponse
from factorylm.llm.groq_client import GroqClient
from factorylm.llm.deepseek_client import DeepSeekClient
from factorylm.llm.claude_client import ClaudeClient
from factorylm.llm.flm_client import FLMClient


def create_llm_client(provider: str, api_key: str, model: str = None) -> BaseLLMClient:
    """
    Factory function to create appropriate LLM client.

    Args:
        provider: LLM provider name ('groq', 'deepseek', 'claude', 'flm')
        api_key: API key for the provider
        model: Optional model name (defaults vary by provider)

    Returns:
        BaseLLMClient: Configured LLM client instance

    Raises:
        ValueError: If provider is unknown

    Example:
        >>> client = create_llm_client("groq", "your-api-key")
        >>> response = client.analyze_machine_state("What's wrong?", {"temp": 150})
    """
    providers = {
        "groq": GroqClient,
        "deepseek": DeepSeekClient,
        "claude": ClaudeClient,
        "flm": FLMClient,
    }

    provider_lower = provider.lower()
    if provider_lower not in providers:
        valid_providers = ", ".join(providers.keys())
        raise ValueError(
            f"Unknown provider: {provider}. Valid providers: {valid_providers}"
        )

    client_class = providers[provider_lower]
    return client_class(api_key=api_key, model=model)


__all__ = [
    "create_llm_client",
    "BaseLLMClient",
    "LLMResponse",
    "GroqClient",
    "DeepSeekClient",
    "ClaudeClient",
    "FLMClient",
]
