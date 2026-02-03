"""
Unit Tests for DeepSeek Client

Tests for factorylm.llm.deepseek_client module.
"""

import pytest
from unittest.mock import MagicMock, patch

from factorylm.llm.base import LLMResponse, LLMAuthenticationError


class TestDeepSeekClientInitialization:
    """Tests for DeepSeekClient initialization."""

    def test_init_with_valid_key(self, mock_openai_client):
        """Test initialization with valid API key."""
        from factorylm.llm.deepseek_client import DeepSeekClient

        client = DeepSeekClient(api_key="valid-key")
        assert client.get_model_name() == "deepseek-chat"

    def test_init_with_custom_model(self, mock_openai_client):
        """Test initialization with custom model."""
        from factorylm.llm.deepseek_client import DeepSeekClient

        client = DeepSeekClient(api_key="key", model="deepseek-coder")
        assert client.get_model_name() == "deepseek-coder"

    def test_init_without_key_raises_error(self, mock_openai_client):
        """Test that missing API key raises error."""
        from factorylm.llm.deepseek_client import DeepSeekClient

        with pytest.raises(LLMAuthenticationError):
            DeepSeekClient(api_key="")


class TestDeepSeekClientChat:
    """Tests for DeepSeekClient chat method."""

    def test_chat_returns_llm_response(self, mock_openai_client, sample_messages):
        """Test that chat returns proper LLMResponse."""
        from factorylm.llm.deepseek_client import DeepSeekClient

        client = DeepSeekClient(api_key="test-key")
        response = client.chat(sample_messages)

        assert isinstance(response, LLMResponse)
        assert response.text == "Analysis complete. No issues detected."
        assert response.tokens_used == 120


class TestDeepSeekClientAnalyzeMachineState:
    """Tests for DeepSeekClient analyze_machine_state method."""

    def test_analyze_machine_state(
        self, mock_openai_client, sample_machine_state, sample_question
    ):
        """Test analyze_machine_state method."""
        from factorylm.llm.deepseek_client import DeepSeekClient

        client = DeepSeekClient(api_key="test-key")
        response = client.analyze_machine_state(sample_question, sample_machine_state)

        assert isinstance(response, LLMResponse)
        assert len(response.text) > 0


class TestDeepSeekClientCostEstimation:
    """Tests for DeepSeekClient cost estimation."""

    def test_estimate_cost(self, mock_openai_client):
        """Test cost estimation."""
        from factorylm.llm.deepseek_client import DeepSeekClient

        client = DeepSeekClient(api_key="test-key")

        response = LLMResponse(
            text="Test",
            tokens_used=1000,
            model="deepseek-chat",
            input_tokens=600,
            output_tokens=400,
        )

        cost = client.estimate_cost(response)

        # DeepSeek: $0.14 per 1M input, $0.28 per 1M output
        expected = (600 / 1_000_000 * 0.14) + (400 / 1_000_000 * 0.28)
        assert abs(cost - expected) < 0.000001


class TestDeepSeekClientUtilities:
    """Tests for DeepSeekClient utility methods."""

    def test_list_models(self, mock_openai_client):
        """Test list_models method."""
        from factorylm.llm.deepseek_client import DeepSeekClient

        client = DeepSeekClient(api_key="key")
        models = client.list_models()

        assert isinstance(models, list)
        assert "deepseek-chat" in models

    def test_health_check_success(self, mock_openai_client):
        """Test health_check returns True on success."""
        from factorylm.llm.deepseek_client import DeepSeekClient

        client = DeepSeekClient(api_key="key")
        assert client.health_check() is True

    def test_health_check_failure(self):
        """Test health_check returns False on failure."""
        with patch("factorylm.llm.deepseek_client.OpenAI") as mock_openai:
            mock_instance = MagicMock()
            mock_instance.chat.completions.create.side_effect = Exception("Failed")
            mock_openai.return_value = mock_instance

            from factorylm.llm.deepseek_client import DeepSeekClient

            client = DeepSeekClient(api_key="key")
            assert client.health_check() is False
