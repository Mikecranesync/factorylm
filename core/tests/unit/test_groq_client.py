"""
Unit Tests for GROQ Client

Tests for factorylm.llm.groq_client module.
"""

import pytest
from unittest.mock import MagicMock, patch

from factorylm.llm.base import LLMResponse, LLMAuthenticationError, LLMRateLimitError


class TestGroqClientInitialization:
    """Tests for GroqClient initialization."""

    def test_init_with_valid_key(self, mock_groq_client):
        """Test initialization with valid API key."""
        from factorylm.llm.groq_client import GroqClient

        client = GroqClient(api_key="valid-key")
        assert client.get_model_name() == "llama-3.3-70b-versatile"

    def test_init_with_custom_model(self, mock_groq_client):
        """Test initialization with custom model."""
        from factorylm.llm.groq_client import GroqClient

        client = GroqClient(api_key="key", model="llama3-70b-8192")
        assert client.get_model_name() == "llama3-70b-8192"

    def test_init_without_key_raises_error(self, mock_groq_client):
        """Test that missing API key raises error."""
        from factorylm.llm.groq_client import GroqClient

        with pytest.raises(LLMAuthenticationError):
            GroqClient(api_key="")

    def test_init_with_none_key_raises_error(self, mock_groq_client):
        """Test that None API key raises error."""
        from factorylm.llm.groq_client import GroqClient

        with pytest.raises(LLMAuthenticationError):
            GroqClient(api_key=None)


class TestGroqClientChat:
    """Tests for GroqClient chat method."""

    def test_chat_returns_llm_response(self, mock_groq_client, sample_messages):
        """Test that chat returns proper LLMResponse."""
        from factorylm.llm.groq_client import GroqClient

        client = GroqClient(api_key="test-key")
        response = client.chat(sample_messages)

        assert isinstance(response, LLMResponse)
        assert response.text == "The motor temperature is within normal range."
        assert response.tokens_used == 150
        assert response.model == "mixtral-8x7b-32768"

    def test_chat_with_custom_parameters(self, mock_groq_client, sample_messages):
        """Test chat with custom temperature and max_tokens."""
        from factorylm.llm.groq_client import GroqClient

        client = GroqClient(api_key="test-key")
        response = client.chat(
            sample_messages,
            temperature=0.5,
            max_tokens=500,
        )

        assert isinstance(response, LLMResponse)

    def test_chat_includes_token_breakdown(self, mock_groq_client, sample_messages):
        """Test that response includes input/output token breakdown."""
        from factorylm.llm.groq_client import GroqClient

        client = GroqClient(api_key="test-key")
        response = client.chat(sample_messages)

        assert response.input_tokens == 100
        assert response.output_tokens == 50
        assert response.tokens_used == 150


class TestGroqClientAnalyzeMachineState:
    """Tests for GroqClient analyze_machine_state method."""

    def test_analyze_machine_state(
        self, mock_groq_client, sample_machine_state, sample_question
    ):
        """Test analyze_machine_state method."""
        from factorylm.llm.groq_client import GroqClient

        client = GroqClient(api_key="test-key")
        response = client.analyze_machine_state(sample_question, sample_machine_state)

        assert isinstance(response, LLMResponse)
        assert len(response.text) > 0

    def test_analyze_machine_state_with_issues(
        self, mock_groq_client, sample_machine_state_with_issues
    ):
        """Test analyze_machine_state with problematic state."""
        from factorylm.llm.groq_client import GroqClient

        client = GroqClient(api_key="test-key")
        response = client.analyze_machine_state(
            "What's wrong with the machine?",
            sample_machine_state_with_issues,
        )

        assert isinstance(response, LLMResponse)


class TestGroqClientCostEstimation:
    """Tests for GroqClient cost estimation."""

    def test_estimate_cost_default(self, mock_groq_client):
        """Test cost estimation for default model (llama-3.3-70b)."""
        from factorylm.llm.groq_client import GroqClient

        client = GroqClient(api_key="test-key")

        response = LLMResponse(
            text="Test",
            tokens_used=1000,
            model="llama-3.3-70b-versatile",
            input_tokens=600,
            output_tokens=400,
        )

        cost = client.estimate_cost(response)

        # llama-3.3-70b: $0.59 per 1M input, $0.79 per 1M output
        expected = (600 / 1_000_000 * 0.59) + (400 / 1_000_000 * 0.79)
        assert abs(cost - expected) < 0.000001

    def test_estimate_cost_llama(self, mock_groq_client):
        """Test cost estimation for LLaMA model."""
        from factorylm.llm.groq_client import GroqClient

        client = GroqClient(api_key="test-key", model="llama3-70b-8192")

        response = LLMResponse(
            text="Test",
            tokens_used=1000,
            model="llama3-70b-8192",
            input_tokens=600,
            output_tokens=400,
        )

        cost = client.estimate_cost(response)

        # LLaMA 70B: $0.59 per 1M input, $0.79 per 1M output
        expected = (600 / 1_000_000 * 0.59) + (400 / 1_000_000 * 0.79)
        assert abs(cost - expected) < 0.000001


class TestGroqClientErrorHandling:
    """Tests for GroqClient error handling."""

    def test_authentication_error(self):
        """Test handling of authentication errors."""
        from factorylm.llm.groq_client import GroqClient, GROQ_AVAILABLE

        if not GROQ_AVAILABLE:
            pytest.skip("GROQ SDK not installed")

        with patch("factorylm.llm.groq_client.Groq") as mock_groq:
            from groq import AuthenticationError

            mock_instance = MagicMock()
            mock_instance.chat.completions.create.side_effect = AuthenticationError(
                "Invalid API key",
                response=MagicMock(status_code=401),
                body={"error": {"message": "Invalid API key"}},
            )
            mock_groq.return_value = mock_instance

            client = GroqClient(api_key="invalid-key")

            with pytest.raises(LLMAuthenticationError):
                client.chat([{"role": "user", "content": "test"}])

    def test_rate_limit_error(self):
        """Test handling of rate limit errors."""
        from factorylm.llm.groq_client import GroqClient, GROQ_AVAILABLE

        if not GROQ_AVAILABLE:
            pytest.skip("GROQ SDK not installed")

        with patch("factorylm.llm.groq_client.Groq") as mock_groq:
            from groq import RateLimitError

            mock_instance = MagicMock()
            mock_instance.chat.completions.create.side_effect = RateLimitError(
                "Rate limit exceeded",
                response=MagicMock(status_code=429),
                body={"error": {"message": "Rate limit exceeded"}},
            )
            mock_groq.return_value = mock_instance

            client = GroqClient(api_key="key")

            with pytest.raises(LLMRateLimitError):
                client.chat([{"role": "user", "content": "test"}])


class TestGroqClientUtilities:
    """Tests for GroqClient utility methods."""

    def test_list_models(self, mock_groq_client):
        """Test list_models method."""
        from factorylm.llm.groq_client import GroqClient

        client = GroqClient(api_key="key")
        models = client.list_models()

        assert isinstance(models, list)
        assert len(models) > 0
        assert "llama-3.3-70b-versatile" in models

    def test_health_check_success(self, mock_groq_client):
        """Test health_check returns True on success."""
        from factorylm.llm.groq_client import GroqClient

        client = GroqClient(api_key="key")
        assert client.health_check() is True

    def test_health_check_failure(self):
        """Test health_check returns False on failure."""
        with patch("factorylm.llm.groq_client.Groq") as mock_groq:
            mock_instance = MagicMock()
            mock_instance.chat.completions.create.side_effect = Exception("Failed")
            mock_groq.return_value = mock_instance

            from factorylm.llm.groq_client import GroqClient

            client = GroqClient(api_key="key")
            assert client.health_check() is False
