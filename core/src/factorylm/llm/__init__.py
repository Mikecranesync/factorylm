"""
LLM Client Module — all calls route through LiteLLM Proxy.

Usage:
    from factorylm.llm.client import llm_client, diagnose_fault, async_diagnose
"""

from factorylm.llm.base import LLMResponse
from factorylm.llm.client import (
    llm_client,
    llm_async_client,
    diagnose_fault,
    async_diagnose,
    classify_intent,
)

__all__ = [
    "llm_client",
    "llm_async_client",
    "diagnose_fault",
    "async_diagnose",
    "classify_intent",
    "LLMResponse",
]
