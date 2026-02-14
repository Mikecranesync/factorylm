"""
GROQ LLM Client Implementation

Provides integration with GROQ's fast inference API using their official SDK.
GROQ offers extremely fast inference with models like LLaMA.
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
    from groq import Groq
    from groq import APIError, AuthenticationError, RateLimitError, APIConnectionError
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    Groq = None


# GROQ pricing per 1M tokens (as of 2025)
GROQ_PRICING = {
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    "llama-3.1-70b-versatile": {"input": 0.59, "output": 0.79},
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    "llama3-70b-8192": {"input": 0.59, "output": 0.79},
    "llama3-8b-8192": {"input": 0.05, "output": 0.08},
    "gemma2-9b-it": {"input": 0.20, "output": 0.20},
}

DEFAULT_MODEL = "llama-3.3-70b-versatile"


class GroqClient(BaseLLMClient):
    """
    GROQ LLM client implementation.

    GROQ provides extremely fast inference (100+ tokens/second) with
    open-source models like LLaMA.

    Example:
        >>> client = GroqClient(api_key="your-key")
        >>> response = client.analyze_machine_state(
        ...     "Is pressure too high?",
        ...     {"pressure_psi": 150, "max_psi": 100}
        ... )
    """

    def __init__(self, api_key: str, model: str = None):
        """
        Initialize GROQ client.

        Args:
            api_key: GROQ API key from https://console.groq.com/keys
            model: Model to use (default: llama-3.3-70b-versatile)

        Raises:
            ImportError: If groq package is not installed
            LLMAuthenticationError: If API key is invalid
        """
        if not GROQ_AVAILABLE:
            raise ImportError(
                "groq package not installed. Run: pip install groq"
            )

        if not api_key or not isinstance(api_key, str):
            raise LLMAuthenticationError(
                "Valid API key required", provider="groq"
            )

        self._api_key = api_key
        self._model = model or DEFAULT_MODEL
        self._client = Groq(api_key=api_key)

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
        # Build the analysis prompt
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
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        return self.chat(messages, temperature=0.3)

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """
        Send a chat completion request to GROQ.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens in response

        Returns:
            LLMResponse with the model's response

        Raises:
            LLMError: On API errors
        """
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # Extract response data
            choice = response.choices[0]
            usage = response.usage

            return LLMResponse(
                text=choice.message.content,
                tokens_used=usage.total_tokens,
                model=response.model,
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
                finish_reason=choice.finish_reason,
                raw_response=response,
            )

        except AuthenticationError as e:
            raise LLMAuthenticationError(
                f"GROQ authentication failed: {e}",
                provider="groq",
                original_error=e,
            )
        except RateLimitError as e:
            raise LLMRateLimitError(
                f"GROQ rate limit exceeded: {e}",
                provider="groq",
                original_error=e,
            )
        except APIConnectionError as e:
            raise LLMConnectionError(
                f"Failed to connect to GROQ: {e}",
                provider="groq",
                original_error=e,
            )
        except APIError as e:
            raise LLMError(
                f"GROQ API error: {e}",
                provider="groq",
                original_error=e,
            )
        except Exception as e:
            raise LLMError(
                f"Unexpected error: {e}",
                provider="groq",
                original_error=e,
            )

    def stream_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> Iterator[str]:
        """
        Stream a chat completion response from GROQ.

        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response

        Yields:
            Chunks of response text as they arrive
        """
        try:
            stream = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            raise LLMError(
                f"Stream error: {e}",
                provider="groq",
                original_error=e,
            )

    def estimate_cost(self, response: LLMResponse) -> float:
        """
        Estimate cost of a GROQ API call in USD.

        Args:
            response: LLMResponse to estimate cost for

        Returns:
            Estimated cost in USD
        """
        model = response.model or self._model

        # Get pricing for model (default to llama-3.3 pricing)
        pricing = GROQ_PRICING.get(
            model, GROQ_PRICING[DEFAULT_MODEL]
        )

        input_tokens = response.input_tokens or 0
        output_tokens = response.output_tokens or 0

        # Calculate cost (pricing is per 1M tokens)
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return round(input_cost + output_cost, 6)

    def list_models(self) -> List[str]:
        """
        List available GROQ models.

        Returns:
            List of model names
        """
        return list(GROQ_PRICING.keys())

    def health_check(self) -> bool:
        """
        Check if GROQ API is accessible.

        Returns:
            True if accessible, False otherwise
        """
        try:
            # Simple test request
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
            )
            return True
        except Exception:
            return False
