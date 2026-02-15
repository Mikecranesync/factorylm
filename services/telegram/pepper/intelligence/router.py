"""
PEPPER Intelligence Router

4-Layer routing system:
- Layer 0: Deterministic code + Knowledge Base
- Layer 1: Edge LLM (future)
- Layer 2: Local LLM (Groq)
- Layer 3: Cloud AI (Claude fallback)

Intelligence flows DOWNWARD - Convert Layer 3 answers into Layer 0 code over time.
"""

import logging
from typing import Optional, Any
from dataclasses import dataclass
from enum import IntEnum, auto

from .layer0_kb import KnowledgeBase
from .layer2_local import LocalLLM
from .layer3_cloud import CloudAI


logger = logging.getLogger(__name__)


class Layer(IntEnum):
    """Intelligence layer levels."""
    KB = 0          # Knowledge Base (fastest, cheapest)
    EDGE = 1        # Edge LLM (future Pi deployment)
    LOCAL = 2       # Local LLM (Groq)
    CLOUD = 3       # Cloud AI (Claude)


@dataclass
class RouteResult:
    """Result of intelligence routing."""
    layer: Layer
    response: str
    confidence: float
    model: Optional[str] = None
    cached: bool = False
    latency_ms: int = 0
    tokens_used: int = 0


class IntelligenceRouter:
    """
    Routes queries through the 4-layer intelligence stack.

    Routing strategy:
    1. Try Layer 0 (KB) first for known patterns
    2. Fall through to Layer 2 (Groq) for most queries
    3. Use Layer 3 (Claude) as fallback when Groq fails
    """

    def __init__(
        self,
        groq_api_key: Optional[str] = None,
        claude_api_key: Optional[str] = None,
        kb_path: Optional[str] = None
    ):
        """
        Initialize the intelligence router.

        Args:
            groq_api_key: API key for Groq (Layer 2)
            claude_api_key: API key for Anthropic (Layer 3)
            kb_path: Path to knowledge base directory
        """
        self.kb = KnowledgeBase(kb_path)
        self.local_llm = LocalLLM(groq_api_key) if groq_api_key else None
        self.cloud_ai = CloudAI(claude_api_key) if claude_api_key else None

        logger.info(
            f"IntelligenceRouter initialized: "
            f"KB={self.kb is not None}, "
            f"Local={self.local_llm is not None}, "
            f"Cloud={self.cloud_ai is not None}"
        )

    async def route(
        self,
        query: str,
        context: Optional[dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        force_layer: Optional[Layer] = None,
        max_layer: Layer = Layer.CLOUD
    ) -> RouteResult:
        """
        Route a query through the intelligence stack.

        Args:
            query: The user's query
            context: Optional context (equipment, session, etc.)
            system_prompt: Optional system prompt override
            force_layer: Force specific layer (skip lower layers)
            max_layer: Maximum layer to try (for cost control)

        Returns:
            RouteResult with response and metadata
        """
        import time
        start_time = time.time()

        # Try Layer 0: Knowledge Base
        if force_layer is None or force_layer == Layer.KB:
            kb_result = await self._try_layer0(query, context)
            if kb_result:
                kb_result.latency_ms = int((time.time() - start_time) * 1000)
                return kb_result

        # Skip Layer 1 (Edge) - not implemented yet

        # Try Layer 2: Local LLM (Groq)
        if max_layer >= Layer.LOCAL and self.local_llm:
            if force_layer is None or force_layer == Layer.LOCAL:
                try:
                    local_result = await self._try_layer2(
                        query, context, system_prompt
                    )
                    if local_result:
                        local_result.latency_ms = int((time.time() - start_time) * 1000)
                        return local_result
                except Exception as e:
                    logger.warning(f"Layer 2 (Groq) failed: {e}")

        # Try Layer 3: Cloud AI (Claude)
        if max_layer >= Layer.CLOUD and self.cloud_ai:
            if force_layer is None or force_layer == Layer.CLOUD:
                try:
                    cloud_result = await self._try_layer3(
                        query, context, system_prompt
                    )
                    if cloud_result:
                        cloud_result.latency_ms = int((time.time() - start_time) * 1000)
                        return cloud_result
                except Exception as e:
                    logger.error(f"Layer 3 (Claude) failed: {e}")

        # All layers failed
        return RouteResult(
            layer=Layer.KB,
            response="I'm unable to process your request right now. Please try again later.",
            confidence=0.0,
            latency_ms=int((time.time() - start_time) * 1000)
        )

    async def _try_layer0(
        self,
        query: str,
        context: Optional[dict[str, Any]]
    ) -> Optional[RouteResult]:
        """Try to answer from knowledge base."""
        result = await self.kb.lookup(query, context)

        if result and result.confidence >= 0.8:
            logger.debug(f"Layer 0 hit: {result.pattern}")
            return RouteResult(
                layer=Layer.KB,
                response=result.response,
                confidence=result.confidence,
                cached=True
            )

        return None

    async def _try_layer2(
        self,
        query: str,
        context: Optional[dict[str, Any]],
        system_prompt: Optional[str]
    ) -> Optional[RouteResult]:
        """Try to answer with local LLM (Groq)."""
        if not self.local_llm:
            return None

        result = await self.local_llm.generate(
            query=query,
            context=context,
            system_prompt=system_prompt
        )

        if result:
            logger.debug(f"Layer 2 response: model={result.model}")
            return RouteResult(
                layer=Layer.LOCAL,
                response=result.response,
                confidence=result.confidence,
                model=result.model,
                tokens_used=result.tokens_used
            )

        return None

    async def _try_layer3(
        self,
        query: str,
        context: Optional[dict[str, Any]],
        system_prompt: Optional[str]
    ) -> Optional[RouteResult]:
        """Try to answer with cloud AI (Claude)."""
        if not self.cloud_ai:
            return None

        result = await self.cloud_ai.generate(
            query=query,
            context=context,
            system_prompt=system_prompt
        )

        if result:
            logger.debug(f"Layer 3 response: model={result.model}")
            return RouteResult(
                layer=Layer.CLOUD,
                response=result.response,
                confidence=result.confidence,
                model=result.model,
                tokens_used=result.tokens_used
            )

        return None

    def get_layer_status(self) -> dict[str, bool]:
        """Get availability status of each layer."""
        return {
            "layer0_kb": self.kb is not None,
            "layer1_edge": False,  # Not implemented
            "layer2_local": self.local_llm is not None and self.local_llm.is_available(),
            "layer3_cloud": self.cloud_ai is not None and self.cloud_ai.is_available()
        }


# Singleton instance
_router: Optional[IntelligenceRouter] = None


def get_router(
    groq_api_key: Optional[str] = None,
    claude_api_key: Optional[str] = None
) -> IntelligenceRouter:
    """Get or create the intelligence router singleton."""
    global _router

    if _router is None:
        _router = IntelligenceRouter(
            groq_api_key=groq_api_key,
            claude_api_key=claude_api_key
        )

    return _router
