"""
Unit Tests for LLM Base Interface

Tests for factorylm.llm.base module (LLMResponse and BaseLLMClient).
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock

from factorylm.llm.base import (
    LLMResponse,
    BaseLLMClient,
    LLMError,
    LLMConnectionError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMInvalidRequestError,
)


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_basic_creation(self):
        """Test basic LLMResponse creation."""
        response = LLMResponse(
            text="Hello, world!",
            tokens_used=10,
            model="test-model",
        )
        assert response.text == "Hello, world!"
        assert response.tokens_used == 10
        assert response.model == "test-model"

    def test_optional_fields(self):
        """Test optional fields have correct defaults."""
        response = LLMResponse(
            text="Test",
            tokens_used=5,
            model="model",
        )
        assert response.input_tokens is None
        assert response.output_tokens is None
        assert response.finish_reason is None
        assert response.raw_response is None
        assert isinstance(response.created_at, datetime)

    def test_full_creation(self):
        """Test LLMResponse with all fields."""
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

        assert response.text == "Complete response"
        assert response.tokens_used == 150
        assert response.model == "gpt-4"
        assert response.input_tokens == 100
        assert response.output_tokens == 50
        assert response.finish_reason == "stop"
        assert response.created_at == now
        assert response.raw_response == raw

    def test_invalid_text_type(self):
        """Test that non-string text raises TypeError."""
        with pytest.raises(TypeError):
            LLMResponse(text=123, tokens_used=10, model="model")

    def test_invalid_tokens_used_type(self):
        """Test that invalid tokens_used raises ValueError."""
        with pytest.raises(ValueError):
            LLMResponse(text="test", tokens_used=-1, model="model")

    def test_invalid_model_empty(self):
        """Test that empty model raises ValueError."""
        with pytest.raises(ValueError):
            LLMResponse(text="test", tokens_used=10, model="")

    def test_to_dict(self):
        """Test to_dict method."""
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
        assert result["input_tokens"] == 30
        assert result["output_tokens"] == 20
        assert result["finish_reason"] == "stop"
        assert "created_at" in result
        # raw_response should not be in dict
        assert "raw_response" not in result


class TestLLMErrors:
    """Tests for LLM error classes."""

    def test_base_llm_error(self):
        """Test LLMError base class."""
        error = LLMError("Something went wrong", provider="groq")
        assert str(error) == "Something went wrong"
        assert error.provider == "groq"
        assert error.original_error is None

    def test_llm_error_with_original(self):
        """Test LLMError with original exception."""
        original = ValueError("Original error")
        error = LLMError("Wrapped error", provider="claude", original_error=original)
        assert error.original_error == original

    def test_connection_error(self):
        """Test LLMConnectionError."""
        error = LLMConnectionError("Connection failed", provider="deepseek")
        assert isinstance(error, LLMError)
        assert "Connection failed" in str(error)

    def test_authentication_error(self):
        """Test LLMAuthenticationError."""
        error = LLMAuthenticationError("Invalid API key", provider="groq")
        assert isinstance(error, LLMError)
        assert error.provider == "groq"

    def test_rate_limit_error(self):
        """Test LLMRateLimitError."""
        error = LLMRateLimitError("Rate limit exceeded", provider="claude")
        assert isinstance(error, LLMError)

    def test_invalid_request_error(self):
        """Test LLMInvalidRequestError."""
        error = LLMInvalidRequestError("Bad request", provider="groq")
        assert isinstance(error, LLMError)


class TestBaseLLMClientInterface:
    """Tests for BaseLLMClient abstract interface."""

    def test_cannot_instantiate_directly(self):
        """Test that BaseLLMClient cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseLLMClient(api_key="test", model="test")

    def test_concrete_implementation(self):
        """Test that a concrete implementation works."""

        class TestClient(BaseLLMClient):
            def __init__(self, api_key: str, model: str = None):
                self._api_key = api_key
                self._model = model or "test-model"

            def analyze_machine_state(self, question, machine_state):
                return LLMResponse(
                    text=f"Analysis for: {question}",
                    tokens_used=10,
                    model=self._model,
                )

            def get_model_name(self):
                return self._model

            def estimate_cost(self, response):
                return 0.001

        client = TestClient(api_key="test-key")
        assert client.get_model_name() == "test-model"

    def test_health_check_default(self):
        """Test default health_check implementation."""

        class TestClient(BaseLLMClient):
            def __init__(self, api_key: str, model: str = None):
                self._model = model or "test"

            def analyze_machine_state(self, question, machine_state):
                return LLMResponse(text="ok", tokens_used=1, model=self._model)

            def get_model_name(self):
                return self._model

            def estimate_cost(self, response):
                return 0.0

        client = TestClient(api_key="key")
        # Default health_check calls get_model_name
        assert client.health_check() is True

    def test_chat_not_implemented_by_default(self):
        """Test that chat raises NotImplementedError by default."""

        class MinimalClient(BaseLLMClient):
            def __init__(self, api_key: str, model: str = None):
                self._model = model

            def analyze_machine_state(self, question, machine_state):
                return LLMResponse(text="ok", tokens_used=1, model="test")

            def get_model_name(self):
                return "test"

            def estimate_cost(self, response):
                return 0.0

        client = MinimalClient(api_key="key")
        with pytest.raises(NotImplementedError):
            client.chat([{"role": "user", "content": "test"}])

    def test_stream_chat_not_implemented_by_default(self):
        """Test that stream_chat raises NotImplementedError by default."""

        class MinimalClient(BaseLLMClient):
            def __init__(self, api_key: str, model: str = None):
                self._model = model

            def analyze_machine_state(self, question, machine_state):
                return LLMResponse(text="ok", tokens_used=1, model="test")

            def get_model_name(self):
                return "test"

            def estimate_cost(self, response):
                return 0.0

        client = MinimalClient(api_key="key")
        with pytest.raises(NotImplementedError):
            list(client.stream_chat([{"role": "user", "content": "test"}]))

    def test_repr(self):
        """Test __repr__ method."""

        class TestClient(BaseLLMClient):
            def __init__(self, api_key: str, model: str = None):
                self._model = model or "my-model"

            def analyze_machine_state(self, question, machine_state):
                return LLMResponse(text="ok", tokens_used=1, model=self._model)

            def get_model_name(self):
                return self._model

            def estimate_cost(self, response):
                return 0.0

        client = TestClient(api_key="key")
        repr_str = repr(client)
        assert "TestClient" in repr_str
        assert "my-model" in repr_str
