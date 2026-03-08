"""
FactoryLM Core - LLM Abstraction Layer for Industrial Applications

All LLM calls route through LiteLLM Proxy (localhost:4000).
Model routing, fallbacks, retries handled by the proxy config.

Usage:
    from factorylm.llm.client import diagnose_fault, async_diagnose
"""

__version__ = "0.1.0"
__author__ = "FactoryLM Team"

from factorylm.llm import llm_client, async_diagnose, diagnose_fault
from factorylm.llm.base import LLMResponse

__all__ = ["llm_client", "async_diagnose", "diagnose_fault", "LLMResponse", "__version__"]
