"""
PEPPER Layer 3: Cloud AI (Claude)

Claude fallback for complex queries when local LLM fails.
Used sparingly - prefer Layer 2 for cost efficiency.
"""

import logging
from typing import Optional, Any
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class CloudResult:
    """Result from cloud AI generation."""
    response: str
    confidence: float
    model: str
    tokens_used: int
    stop_reason: str


# Claude model configuration
CLAUDE_MODELS = [
    "claude-sonnet-4-20250514",      # Primary: balanced
    "claude-3-haiku-20240307",       # Fallback: faster/cheaper
]

# System prompt for factory assistant
DEFAULT_SYSTEM_PROMPT = """You are Pepper, an AI assistant for factory technicians at FactoryLM.

Your role:
- Help diagnose equipment issues quickly and accurately
- Explain maintenance procedures step by step
- Answer questions about PLC systems, conveyors, sensors
- Provide actionable recommendations

Communication style:
- Be concise and direct
- Use technical language appropriate for technicians
- Include specific steps when relevant
- Acknowledge uncertainty when appropriate

You have access to real-time equipment data when context is provided.
Focus on practical, immediate solutions that can be implemented on the factory floor."""


class CloudAI:
    """
    Claude-based cloud AI for complex queries.

    Features:
    - Fallback for Layer 2 failures
    - Complex reasoning capabilities
    - Multi-step diagnosis support
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Anthropic client.

        Args:
            api_key: Anthropic API key (or from ANTHROPIC_API_KEY env)
        """
        self.api_key = api_key
        self._client = None
        self.current_model = CLAUDE_MODELS[0]
        self._available = False

        if api_key:
            self._init_client()

    def _init_client(self):
        """Initialize the Anthropic client."""
        try:
            import anthropic
            self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
            self._available = True
            logger.info("Anthropic client initialized")
        except ImportError:
            logger.error("anthropic package not installed")
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic client: {e}")

    def is_available(self) -> bool:
        """Check if Claude is available."""
        return self._available and self._client is not None

    async def generate(
        self,
        query: str,
        context: Optional[dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7
    ) -> Optional[CloudResult]:
        """
        Generate a response using Claude.

        Args:
            query: User query
            context: Optional context dict
            system_prompt: Optional system prompt override
            model: Optional model override
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            CloudResult or None on failure
        """
        if not self.is_available():
            logger.warning("Claude not available")
            return None

        # Build system prompt with context
        system = system_prompt or DEFAULT_SYSTEM_PROMPT
        if context:
            context_str = self._format_context(context)
            system = f"{system}\n\nCurrent context:\n{context_str}"

        # Try models in order
        models_to_try = [model] if model else CLAUDE_MODELS

        for try_model in models_to_try:
            try:
                result = await self._call_claude(
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
                logger.warning(f"Claude model {try_model} failed: {e}")
                continue

        return None

    async def _call_claude(
        self,
        query: str,
        system: str,
        model: str,
        max_tokens: int,
        temperature: float
    ) -> Optional[CloudResult]:
        """Make the actual Claude API call."""
        try:
            response = await self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[
                    {"role": "user", "content": query}
                ],
                temperature=temperature
            )

            # Extract text from response
            text_content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text_content += block.text

            return CloudResult(
                response=text_content,
                confidence=0.9,  # Higher confidence for Claude
                model=model,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                stop_reason=response.stop_reason or "unknown"
            )

        except Exception as e:
            logger.error(f"Claude API call failed: {e}")
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
            response = await self._client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}]
            )
            return True
        except Exception as e:
            logger.error(f"Claude API key validation failed: {e}")
            return False

    async def diagnose_with_reasoning(
        self,
        symptoms: list[str],
        equipment_data: dict[str, Any],
        history: Optional[list[dict]] = None
    ) -> CloudResult:
        """
        Complex fault diagnosis with step-by-step reasoning.

        This is where Claude shines - complex multi-factor analysis.

        Args:
            symptoms: List of observed symptoms
            equipment_data: Current equipment readings
            history: Optional fault history

        Returns:
            CloudResult with diagnosis
        """
        query = f"""Analyze this equipment fault:

Symptoms:
{chr(10).join(f'- {s}' for s in symptoms)}

Current Readings:
{self._format_context(equipment_data)}

{f"Recent History:{chr(10)}{chr(10).join(str(h) for h in history)}" if history else ""}

Provide:
1. Most likely root cause
2. Supporting evidence from the data
3. Recommended immediate actions
4. Preventive measures for future"""

        return await self.generate(
            query=query,
            system_prompt="""You are an expert industrial equipment diagnostician.
Analyze the symptoms and data to identify the root cause.
Be specific and actionable in your recommendations.
Consider both immediate fixes and long-term prevention."""
        )
