"""
LLM Response and Exception Types

Kept for backward compatibility. All LLM calls now route through LiteLLM Proxy
via client.py — the abstract BaseLLMClient is no longer needed.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any
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



# BaseLLMClient removed — all LLM calls now go through LiteLLM Proxy (client.py)
