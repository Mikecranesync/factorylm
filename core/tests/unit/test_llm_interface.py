"""
Unit Tests for LLM Base Interface

Tests for factorylm.llm.base module (LLMResponse and exception classes).
"""

import pytest
from datetime import datetime

from factorylm.llm.base import (
    LLMResponse,
    LLMError,
    LLMConnectionError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMInvalidRequestError,
)


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_basic_creation(self):
        response = LLMResponse(text="Hello, world!", tokens_used=10, model="test-model")
        assert response.text == "Hello, world!"
        assert response.tokens_used == 10
        assert response.model == "test-model"

    def test_optional_fields(self):
        response = LLMResponse(text="Test", tokens_used=5, model="model")
        assert response.input_tokens is None
        assert response.output_tokens is None
        assert response.finish_reason is None
        assert response.raw_response is None
        assert isinstance(response.created_at, datetime)

    def test_full_creation(self):
        now = datetime.now()
        raw = {"id": "123", "object": "chat.completion"}
        response = LLMResponse(
            text="Complete response",
            tokens_used=150,
            model="gpt-4",
            input_tokens=100,
            output_tokens=50,
            finish_reason="stop",
            created_at=now,
            raw_response=raw,
        )
        assert response.tokens_used == 150
        assert response.input_tokens == 100
        assert response.output_tokens == 50
        assert response.finish_reason == "stop"
        assert response.created_at == now
        assert response.raw_response == raw

    def test_invalid_text_type(self):
        with pytest.raises(TypeError):
            LLMResponse(text=123, tokens_used=10, model="model")

    def test_invalid_tokens_used_type(self):
        with pytest.raises(ValueError):
            LLMResponse(text="test", tokens_used=-1, model="model")

    def test_invalid_model_empty(self):
        with pytest.raises(ValueError):
            LLMResponse(text="test", tokens_used=10, model="")

    def test_to_dict(self):
        response = LLMResponse(
            text="Test response",
            tokens_used=50,
            model="test-model",
            input_tokens=30,
            output_tokens=20,
            finish_reason="stop",
        )
        result = response.to_dict()
        assert result["text"] == "Test response"
        assert result["tokens_used"] == 50
        assert result["model"] == "test-model"
        assert "created_at" in result
        assert "raw_response" not in result


class TestLLMErrors:
    """Tests for LLM error classes."""

    def test_base_llm_error(self):
        error = LLMError("Something went wrong", provider="groq")
        assert str(error) == "Something went wrong"
        assert error.provider == "groq"
        assert error.original_error is None

    def test_llm_error_with_original(self):
        original = ValueError("Original error")
        error = LLMError("Wrapped error", provider="claude", original_error=original)
        assert error.original_error == original

    def test_connection_error(self):
        error = LLMConnectionError("Connection failed", provider="deepseek")
        assert isinstance(error, LLMError)

    def test_authentication_error(self):
        error = LLMAuthenticationError("Invalid API key", provider="groq")
        assert isinstance(error, LLMError)

    def test_rate_limit_error(self):
        error = LLMRateLimitError("Rate limit exceeded", provider="claude")
        assert isinstance(error, LLMError)

    def test_invalid_request_error(self):
        error = LLMInvalidRequestError("Bad request", provider="groq")
        assert isinstance(error, LLMError)
