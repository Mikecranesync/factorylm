"""
Unit Tests for Claude Client

Tests for factorylm.llm.claude_client module.
"""

import pytest
from unittest.mock import MagicMock, patch

from factorylm.llm.base import LLMResponse, LLMAuthenticationError


class TestClaudeClientInitialization:
    """Tests for ClaudeClient initialization."""

    def test_init_with_valid_key(self, mock_anthropic_client):
        """Test initialization with valid API key."""
        from factorylm.llm.claude_client import ClaudeClient

        client = ClaudeClient(api_key="valid-key")
        assert client.get_model_name() == "claude-sonnet-4-20250514"

    def test_init_with_custom_model(self, mock_anthropic_client):
        """Test initialization with custom model."""
        from factorylm.llm.claude_client import ClaudeClient

        client = ClaudeClient(api_key="key", model="claude-3-opus-20240229")
        assert client.get_model_name() == "claude-3-opus-20240229"

    def test_init_without_key_raises_error(self, mock_anthropic_client):
        """Test that missing API key raises error."""
        from factorylm.llm.claude_client import ClaudeClient

        with pytest.raises(LLMAuthenticationError):
            ClaudeClient(api_key="")


class TestClaudeClientChat:
    """Tests for ClaudeClient chat method."""

    def test_chat_returns_llm_response(self, mock_anthropic_client, sample_messages):
        """Test that chat returns proper LLMResponse."""
        from factorylm.llm.claude_client import ClaudeClient

        client = ClaudeClient(api_key="test-key")
        response = client.chat(sample_messages)

        assert isinstance(response, LLMResponse)
        assert response.text == "The system appears to be operating normally."

    def test_chat_with_system_message(self, mock_anthropic_client):
        """Test chat extracts system message correctly."""
        from factorylm.llm.claude_client import ClaudeClient

        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]

        client = ClaudeClient(api_key="test-key")
        response = client.chat(messages)

        assert isinstance(response, LLMResponse)


class TestClaudeClientAnalyzeMachineState:
    """Tests for ClaudeClient analyze_machine_state method."""

    def test_analyze_machine_state(
        self, mock_anthropic_client, sample_machine_state, sample_question
    ):
        """Test analyze_machine_state method."""
        from factorylm.llm.claude_client import ClaudeClient

        client = ClaudeClient(api_key="test-key")
        response = client.analyze_machine_state(sample_question, sample_machine_state)

        assert isinstance(response, LLMResponse)
        assert len(response.text) > 0


class TestClaudeClientCostEstimation:
    """Tests for ClaudeClient cost estimation."""

    def test_estimate_cost_sonnet(self, mock_anthropic_client):
        """Test cost estimation for Sonnet model."""
        from factorylm.llm.claude_client import ClaudeClient

        client = ClaudeClient(api_key="test-key")

        response = LLMResponse(
            text="Test",
            tokens_used=1000,
            model="claude-3-sonnet-20240229",
            input_tokens=600,
            output_tokens=400,
        )

        cost = client.estimate_cost(response)

        # Sonnet: $3.00 per 1M input, $15.00 per 1M output
        expected = (600 / 1_000_000 * 3.00) + (400 / 1_000_000 * 15.00)
        assert abs(cost - expected) < 0.000001

    def test_estimate_cost_haiku(self, mock_anthropic_client):
        """Test cost estimation for Haiku model."""
        from factorylm.llm.claude_client import ClaudeClient

        client = ClaudeClient(api_key="test-key", model="claude-3-haiku-20240307")

        response = LLMResponse(
            text="Test",
            tokens_used=1000,
            model="claude-3-haiku-20240307",
            input_tokens=600,
            output_tokens=400,
        )

        cost = client.estimate_cost(response)

        # Haiku: $0.25 per 1M input, $1.25 per 1M output
        expected = (600 / 1_000_000 * 0.25) + (400 / 1_000_000 * 1.25)
        assert abs(cost - expected) < 0.000001


class TestClaudeClientUtilities:
    """Tests for ClaudeClient utility methods."""

    def test_list_models(self, mock_anthropic_client):
        """Test list_models method."""
        from factorylm.llm.claude_client import ClaudeClient

        client = ClaudeClient(api_key="key")
        models = client.list_models()

        assert isinstance(models, list)
        assert "claude-sonnet-4-20250514" in models
        assert "claude-3-opus-20240229" in models

    def test_health_check_success(self, mock_anthropic_client):
        """Test health_check returns True on success."""
        from factorylm.llm.claude_client import ClaudeClient

        client = ClaudeClient(api_key="key")
        assert client.health_check() is True

    def test_health_check_failure(self):
        """Test health_check returns False on failure."""
        with patch("factorylm.llm.claude_client.Anthropic") as mock_anthropic:
            mock_instance = MagicMock()
            mock_instance.messages.create.side_effect = Exception("Failed")
            mock_anthropic.return_value = mock_instance

            from factorylm.llm.claude_client import ClaudeClient

            client = ClaudeClient(api_key="key")
            assert client.health_check() is False
