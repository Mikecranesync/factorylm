"""
DeepSeek LLM Client Implementation

Provides integration with DeepSeek's API using their OpenAI-compatible interface.
DeepSeek offers competitive pricing with strong coding and reasoning capabilities.
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
    from openai import OpenAI
    from openai import APIError, AuthenticationError, RateLimitError, APIConnectionError
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None


# DeepSeek pricing per 1M tokens (as of 2024)
DEEPSEEK_PRICING = {
    "deepseek-chat": {"input": 0.14, "output": 0.28},
    "deepseek-coder": {"input": 0.14, "output": 0.28},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
}

DEFAULT_MODEL = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"


class DeepSeekClient(BaseLLMClient):
    """
    DeepSeek LLM client implementation.

    DeepSeek provides an OpenAI-compatible API with competitive pricing
    and strong performance on coding and reasoning tasks.

    Example:
        >>> client = DeepSeekClient(api_key="your-key")
        >>> response = client.analyze_machine_state(
        ...     "What's causing the vibration?",
        ...     {"vibration_hz": 120, "normal_hz": 60}
        ... )
    """

    def __init__(self, api_key: str, model: str = None):
        """
        Initialize DeepSeek client.

        Args:
            api_key: DeepSeek API key from https://platform.deepseek.com/
            model: Model to use (default: deepseek-chat)

        Raises:
            ImportError: If openai package is not installed
            LLMAuthenticationError: If API key is invalid
        """
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "openai package not installed. Run: pip install openai"
            )

        if not api_key or not isinstance(api_key, str):
            raise LLMAuthenticationError(
                "Valid API key required", provider="deepseek"
            )

        self._api_key = api_key
        self._model = model or DEFAULT_MODEL
        self._client = OpenAI(
            api_key=api_key,
            base_url=DEEPSEEK_BASE_URL,
        )

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
        Send a chat completion request to DeepSeek.

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
                f"DeepSeek authentication failed: {e}",
                provider="deepseek",
                original_error=e,
            )
        except RateLimitError as e:
            raise LLMRateLimitError(
                f"DeepSeek rate limit exceeded: {e}",
                provider="deepseek",
                original_error=e,
            )
        except APIConnectionError as e:
            raise LLMConnectionError(
                f"Failed to connect to DeepSeek: {e}",
                provider="deepseek",
                original_error=e,
            )
        except APIError as e:
            raise LLMError(
                f"DeepSeek API error: {e}",
                provider="deepseek",
                original_error=e,
            )
        except Exception as e:
            raise LLMError(
                f"Unexpected error: {e}",
                provider="deepseek",
                original_error=e,
            )

    def stream_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> Iterator[str]:
        """
        Stream a chat completion response from DeepSeek.

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
                provider="deepseek",
                original_error=e,
            )

    def estimate_cost(self, response: LLMResponse) -> float:
        """
        Estimate cost of a DeepSeek API call in USD.

        Args:
            response: LLMResponse to estimate cost for

        Returns:
            Estimated cost in USD
        """
        model = response.model or self._model

        # Get pricing (default to deepseek-chat)
        pricing = DEEPSEEK_PRICING.get(
            model, DEEPSEEK_PRICING[DEFAULT_MODEL]
        )

        input_tokens = response.input_tokens or 0
        output_tokens = response.output_tokens or 0

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return round(input_cost + output_cost, 6)

    def list_models(self) -> List[str]:
        """
        List available DeepSeek models.

        Returns:
            List of model names
        """
        return list(DEEPSEEK_PRICING.keys())

    def health_check(self) -> bool:
        """
        Check if DeepSeek API is accessible.

        Returns:
            True if accessible, False otherwise
        """
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
            )
            return True
        except Exception:
            return False
