"""
Base LLM Interface

Defines the abstract interface that all LLM providers must implement.
This ensures consistent behavior across GROQ, DeepSeek, Claude, and future providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Iterator
from datetime import datetime


@dataclass
class LLMResponse:
    """
    Standardized response object from any LLM provider.

    Attributes:
        text: The generated text response
        tokens_used: Total tokens consumed (input + output)
        model: The model name that generated this response
        input_tokens: Number of input/prompt tokens (optional)
        output_tokens: Number of output/completion tokens (optional)
        finish_reason: Why the model stopped generating (optional)
        created_at: Timestamp of response creation
        raw_response: Original provider response for debugging (optional)
    """

    text: str
    tokens_used: int
    model: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    finish_reason: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    raw_response: Optional[Any] = None

    def __post_init__(self):
        """Validate response after initialization."""
        if not isinstance(self.text, str):
            raise TypeError("text must be a string")
        if not isinstance(self.tokens_used, int) or self.tokens_used < 0:
            raise ValueError("tokens_used must be a non-negative integer")
        if not isinstance(self.model, str) or not self.model:
            raise ValueError("model must be a non-empty string")

    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary for serialization."""
        return {
            "text": self.text,
            "tokens_used": self.tokens_used,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "finish_reason": self.finish_reason,
            "created_at": self.created_at.isoformat(),
        }


class LLMError(Exception):
    """Base exception for LLM-related errors."""

    def __init__(self, message: str, provider: str = None, original_error: Exception = None):
        self.message = message
        self.provider = provider
        self.original_error = original_error
        super().__init__(self.message)


class LLMConnectionError(LLMError):
    """Raised when connection to LLM provider fails."""
    pass


class LLMAuthenticationError(LLMError):
    """Raised when authentication with LLM provider fails."""
    pass


class LLMRateLimitError(LLMError):
    """Raised when rate limit is exceeded."""
    pass


class LLMInvalidRequestError(LLMError):
    """Raised when request to LLM is invalid."""
    pass


class BaseLLMClient(ABC):
    """
    Abstract base class for all LLM provider clients.

    All LLM clients (GROQ, DeepSeek, Claude, FLM) must inherit from this class
    and implement all abstract methods. This ensures a consistent interface
    for the factory function and downstream consumers.

    Example:
        >>> class MyLLMClient(BaseLLMClient):
        ...     def __init__(self, api_key: str, model: str = None):
        ...         self.api_key = api_key
        ...         self.model = model or "default-model"
        ...     # implement other abstract methods...
    """

    @abstractmethod
    def __init__(self, api_key: str, model: str = None):
        """
        Initialize the LLM client.

        Args:
            api_key: API key for authentication with the provider
            model: Optional model name (provider-specific default if not specified)
        """
        pass

    @abstractmethod
    def analyze_machine_state(
        self, question: str, machine_state: Dict[str, Any]
    ) -> LLMResponse:
        """
        Analyze PLC/machine state and answer technician question.

        This is the primary method for industrial applications. It takes
        machine sensor data and allows natural language queries about the state.

        Args:
            question: Natural language question from technician
                      (e.g., "Why is temperature rising?")
            machine_state: Dictionary containing current machine sensor values
                          (e.g., {"temperature": 150, "pressure": 45, "rpm": 1200})

        Returns:
            LLMResponse: Standardized response with analysis and answer

        Raises:
            LLMError: If the request fails

        Example:
            >>> response = client.analyze_machine_state(
            ...     "Is the motor running too hot?",
            ...     {"motor_temp": 185, "ambient_temp": 72, "load": 0.85}
            ... )
            >>> print(response.text)
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """
        Return the model name being used.

        Returns:
            str: Full model identifier (e.g., "mixtral-8x7b-32768")
        """
        pass

    @abstractmethod
    def estimate_cost(self, response: LLMResponse) -> float:
        """
        Estimate the cost of an API call in USD.

        Args:
            response: The LLMResponse to estimate cost for

        Returns:
            float: Estimated cost in USD (e.g., 0.0015)

        Note:
            Costs are estimates based on published pricing and may vary.
        """
        pass

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """
        Send a chat completion request.

        This is an optional method that provides direct chat access.
        Default implementation raises NotImplementedError.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens in response

        Returns:
            LLMResponse: The model's response
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement chat()"
        )

    def stream_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> Iterator[str]:
        """
        Stream a chat completion response.

        This is an optional method for streaming responses.
        Default implementation raises NotImplementedError.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens in response

        Yields:
            str: Chunks of the response text as they arrive
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement stream_chat()"
        )

    def health_check(self) -> bool:
        """
        Check if the LLM provider is accessible.

        Returns:
            bool: True if provider is accessible, False otherwise
        """
        try:
            # Simple test: try to get model name
            _ = self.get_model_name()
            return True
        except Exception:
            return False

    def __repr__(self) -> str:
        """Return string representation of the client."""
        return f"{self.__class__.__name__}(model={self.get_model_name()})"
