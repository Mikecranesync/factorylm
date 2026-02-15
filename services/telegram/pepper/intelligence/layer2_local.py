"""
PEPPER Layer 2: Local LLM (Groq)

Fast local inference using Groq's ultra-fast LLM API.
Primary LLM layer for most queries.
"""

import logging
from typing import Optional, Any
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class LLMResult:
    """Result from LLM generation."""
    response: str
    confidence: float
    model: str
    tokens_used: int
    finish_reason: str


# Model configuration with fallbacks
GROQ_MODELS = [
    "llama-3.3-70b-versatile",      # Primary: best quality
    "llama-3.1-8b-instant",          # Fallback: faster
    "deepseek-r1-distill-llama-70b", # Fallback: reasoning
]

# System prompt for factory assistant
DEFAULT_SYSTEM_PROMPT = """You are Pepper, an AI assistant for factory technicians.

Your role:
- Help diagnose equipment issues
- Explain maintenance procedures
- Answer questions about PLC and Factory I/O systems
- Be concise and practical

Guidelines:
- Use clear, technical language
- Reference specific equipment when possible
- Suggest next steps when appropriate
- Admit when you need more information

Current context will be provided if available."""


class LocalLLM:
    """
    Groq-based local LLM for fast inference.

    Features:
    - Multiple model fallbacks
    - Automatic retry on failure
    - Context injection
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Groq client.

        Args:
            api_key: Groq API key (or from GROQ_API_KEY env)
        """
        self.api_key = api_key
        self._client = None
        self.current_model = GROQ_MODELS[0]
        self._available = False

        if api_key:
            self._init_client()

    def _init_client(self):
        """Initialize the Groq client."""
        try:
            from groq import AsyncGroq
            self._client = AsyncGroq(api_key=self.api_key)
            self._available = True
            logger.info("Groq client initialized")
        except ImportError:
            logger.error("groq package not installed")
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {e}")

    def is_available(self) -> bool:
        """Check if Groq is available."""
        return self._available and self._client is not None

    async def generate(
        self,
        query: str,
        context: Optional[dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7
    ) -> Optional[LLMResult]:
        """
        Generate a response using Groq.

        Args:
            query: User query
            context: Optional context dict
            system_prompt: Optional system prompt override
            model: Optional model override
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            LLMResult or None on failure
        """
        if not self.is_available():
            logger.warning("Groq not available")
            return None

        # Build system prompt with context
        system = system_prompt or DEFAULT_SYSTEM_PROMPT
        if context:
            context_str = self._format_context(context)
            system = f"{system}\n\nCurrent context:\n{context_str}"

        # Try models in order
        models_to_try = [model] if model else GROQ_MODELS

        for try_model in models_to_try:
            try:
                result = await self._call_groq(
                    query=query,
                    system=system,
                    model=try_model,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                if result:
                    self.current_model = try_model
                    return result

            except Exception as e:
                logger.warning(f"Groq model {try_model} failed: {e}")
                continue

        return None

    async def _call_groq(
        self,
        query: str,
        system: str,
        model: str,
        max_tokens: int,
        temperature: float
    ) -> Optional[LLMResult]:
        """Make the actual Groq API call."""
        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": query}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )

            choice = response.choices[0]

            return LLMResult(
                response=choice.message.content,
                confidence=0.85,  # Base confidence for LLM responses
                model=model,
                tokens_used=response.usage.total_tokens if response.usage else 0,
                finish_reason=choice.finish_reason
            )

        except Exception as e:
            logger.error(f"Groq API call failed: {e}")
            raise

    def _format_context(self, context: dict[str, Any]) -> str:
        """Format context dict as readable string."""
        lines = []

        for key, value in context.items():
            if isinstance(value, dict):
                lines.append(f"{key}:")
                for k, v in value.items():
                    lines.append(f"  {k}: {v}")
            elif isinstance(value, list):
                lines.append(f"{key}: {', '.join(str(v) for v in value)}")
            else:
                lines.append(f"{key}: {value}")

        return "\n".join(lines)

    async def validate_api_key(self) -> bool:
        """Validate the API key with a simple request."""
        if not self.is_available():
            return False

        try:
            # Make a minimal request to validate
            response = await self._client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1
            )
            return True
        except Exception as e:
            logger.error(f"Groq API key validation failed: {e}")
            return False
