"""
PEPPER Intelligence Package
FactoryLM Dual-Mode Telegram Bot

4-Layer intelligence routing:
- Layer 0: Deterministic code + Knowledge Base
- Layer 1: Edge LLM (future)
- Layer 2: Local LLM (Groq)
- Layer 3: Cloud AI (Claude fallback)

Usage:
    from pepper.intelligence import IntelligenceRouter, get_router, Layer

    # Get router singleton
    router = get_router(
        groq_api_key="...",
        claude_api_key="..."
    )

    # Route a query
    result = await router.route(
        query="Why did the conveyor stop?",
        context={"equipment": "conveyor_01"}
    )

    print(f"Layer {result.layer}: {result.response}")
"""

from .router import (
    IntelligenceRouter,
    RouteResult,
    Layer,
    get_router,
)
from .layer0_kb import KnowledgeBase, KBResult
from .layer2_local import LocalLLM, LLMResult
from .layer3_cloud import CloudAI, CloudResult


__all__ = [
    # Router
    "IntelligenceRouter",
    "RouteResult",
    "Layer",
    "get_router",
    # Layer 0
    "KnowledgeBase",
    "KBResult",
    # Layer 2
    "LocalLLM",
    "LLMResult",
    # Layer 3
    "CloudAI",
    "CloudResult",
]


__version__ = "1.0.0"
