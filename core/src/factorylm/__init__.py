"""
FactoryLM Core - LLM Abstraction Layer for Industrial Applications

This package provides a unified interface for interacting with multiple LLM providers
(GROQ, DeepSeek, Claude, and future FactoryLM proprietary models).

Usage:
    from factorylm import create_llm_client
    from factorylm.config import LLM_PROVIDER, LLM_API_KEY, LLM_MODEL

    llm = create_llm_client(LLM_PROVIDER, LLM_API_KEY, LLM_MODEL)
    response = llm.analyze_machine_state(question, machine_state)
"""

__version__ = "0.1.0"
__author__ = "FactoryLM Team"

from factorylm.llm import create_llm_client
from factorylm.llm.base import BaseLLMClient, LLMResponse

__all__ = ["create_llm_client", "BaseLLMClient", "LLMResponse", "__version__"]
