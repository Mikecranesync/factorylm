"""
Claude (Anthropic) LLM Client Implementation

Provides integration with Anthropic's Claude API using their official SDK.
Claude excels at nuanced reasoning and following complex instructions.
"""

import json
from typing import Dict, List, Any, Iterator, Optional

from factorylm.llm.base import (
    BaseLLMClient,
    LLMResponse,
    LLMError,
    LLMConnectionError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMInvalidRequestError,
)

try:
    import anthropic
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    Anthropic = None


# Claude pricing per 1M tokens (as of 2024)
CLAUDE_PRICING = {
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "claude-3-sonnet-20240229": {"input": 3.00, "output": 15.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 1.00, "output": 5.00},
}

DEFAULT_MODEL = "claude-3-sonnet-20240229"


class ClaudeClient(BaseLLMClient):
    """
    Claude (Anthropic) LLM client implementation.

    Claude models excel at nuanced reasoning, following complex instructions,
    and providing detailed explanations.

    Example:
        >>> client = ClaudeClient(api_key="your-key")
        >>> response = client.analyze_machine_state(
        ...     "Why did the conveyor stop?",
        ...     {"conveyor_speed": 0, "jam_sensor": True, "motor_current": 0}
        ... )
    """

    def __init__(self, api_key: str, model: str = None):
        """
        Initialize Claude client.

        Args:
            api_key: Anthropic API key from https://console.anthropic.com/
            model: Model to use (default: claude-3-sonnet-20240229)

        Raises:
            ImportError: If anthropic package is not installed
            LLMAuthenticationError: If API key is invalid
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                "anthropic package not installed. Run: pip install anthropic"
            )

        if not api_key or not isinstance(api_key, str):
            raise LLMAuthenticationError(
                "Valid API key required", provider="claude"
            )

        self._api_key = api_key
        self._model = model or DEFAULT_MODEL
        self._client = Anthropic(api_key=api_key)

    def get_model_name(self) -> str:
        """Return the model name being used."""
        return self._model

    def analyze_machine_state(
        self, question: str, machine_state: Dict[str, Any]
    ) -> LLMResponse:
        """
        Analyze machine state and answer technician question.

        Args:
            question: Natural language question about the machine
            machine_state: Dictionary of sensor values

        Returns:
            LLMResponse with analysis
        """
        state_json = json.dumps(machine_state, indent=2)
        system_prompt = """You are an industrial machine diagnostics expert.
Analyze the provided machine state data and answer the technician's question.
Be concise, specific, and actionable. Focus on:
- Identifying any values outside normal ranges
- Potential causes of issues
- Recommended actions"""

        user_prompt = f"""Machine State Data:
```json
{state_json}
```

Technician Question: {question}"""

        messages = [
            {"role": "user", "content": user_prompt},
        ]

        return self.chat(messages, temperature=0.3, system=system_prompt)

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        system: str = None,
    ) -> LLMResponse:
        """
        Send a chat completion request to Claude.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens in response
            system: Optional system prompt

        Returns:
            LLMResponse with the model's response

        Raises:
            LLMError: On API errors
        """
        try:
            # Claude uses a different message format
            # Extract system message if present in messages
            system_content = system
            filtered_messages = []

            for msg in messages:
                if msg["role"] == "system":
                    system_content = msg["content"]
                else:
                    filtered_messages.append(msg)

            kwargs = {
                "model": self._model,
                "messages": filtered_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            if system_content:
                kwargs["system"] = system_content

            response = self._client.messages.create(**kwargs)

            # Extract text from content blocks
            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text

            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            return LLMResponse(
                text=text,
                tokens_used=input_tokens + output_tokens,
                model=response.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                finish_reason=response.stop_reason,
                raw_response=response,
            )

        except anthropic.AuthenticationError as e:
            raise LLMAuthenticationError(
                f"Claude authentication failed: {e}",
                provider="claude",
                original_error=e,
            )
        except anthropic.RateLimitError as e:
            raise LLMRateLimitError(
                f"Claude rate limit exceeded: {e}",
                provider="claude",
                original_error=e,
            )
        except anthropic.APIConnectionError as e:
            raise LLMConnectionError(
                f"Failed to connect to Claude: {e}",
                provider="claude",
                original_error=e,
            )
        except anthropic.APIError as e:
            raise LLMError(
                f"Claude API error: {e}",
                provider="claude",
                original_error=e,
            )
        except Exception as e:
            raise LLMError(
                f"Unexpected error: {e}",
                provider="claude",
                original_error=e,
            )

    def stream_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        system: str = None,
    ) -> Iterator[str]:
        """
        Stream a chat completion response from Claude.

        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            system: Optional system prompt

        Yields:
            Chunks of response text as they arrive
        """
        try:
            system_content = system
            filtered_messages = []

            for msg in messages:
                if msg["role"] == "system":
                    system_content = msg["content"]
                else:
                    filtered_messages.append(msg)

            kwargs = {
                "model": self._model,
                "messages": filtered_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            if system_content:
                kwargs["system"] = system_content

            with self._client.messages.stream(**kwargs) as stream:
                for text in stream.text_stream:
                    yield text

        except Exception as e:
            raise LLMError(
                f"Stream error: {e}",
                provider="claude",
                original_error=e,
            )

    def estimate_cost(self, response: LLMResponse) -> float:
        """
        Estimate cost of a Claude API call in USD.

        Args:
            response: LLMResponse to estimate cost for

        Returns:
            Estimated cost in USD
        """
        model = response.model or self._model

        # Get pricing (default to sonnet)
        pricing = CLAUDE_PRICING.get(
            model, CLAUDE_PRICING[DEFAULT_MODEL]
        )

        input_tokens = response.input_tokens or 0
        output_tokens = response.output_tokens or 0

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return round(input_cost + output_cost, 6)

    def list_models(self) -> List[str]:
        """
        List available Claude models.

        Returns:
            List of model names
        """
        return list(CLAUDE_PRICING.keys())

    def health_check(self) -> bool:
        """
        Check if Claude API is accessible.

        Returns:
            True if accessible, False otherwise
        """
        try:
            response = self._client.messages.create(
                model=self._model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
            )
            return True
        except Exception:
            return False
