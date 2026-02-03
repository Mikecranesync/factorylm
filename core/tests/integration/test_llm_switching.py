"""
Integration Tests for LLM Provider Switching

Tests that verify the factory function and provider switching work correctly.
"""

import pytest
from unittest.mock import patch, MagicMock

from factorylm.llm import create_llm_client
from factorylm.llm.base import BaseLLMClient, LLMResponse


class TestCreateLLMClient:
    """Tests for create_llm_client factory function."""

    def test_create_groq_client(self, mock_groq_client):
        """Test creating GROQ client via factory."""
        from factorylm.llm.groq_client import GroqClient

        client = create_llm_client("groq", "test-api-key")
        assert isinstance(client, GroqClient)
        assert isinstance(client, BaseLLMClient)
        assert client.get_model_name() == "mixtral-8x7b-32768"

    def test_create_deepseek_client(self, mock_openai_client):
        """Test creating DeepSeek client via factory."""
        from factorylm.llm.deepseek_client import DeepSeekClient

        client = create_llm_client("deepseek", "test-api-key")
        assert isinstance(client, DeepSeekClient)
        assert isinstance(client, BaseLLMClient)
        assert client.get_model_name() == "deepseek-chat"

    def test_create_claude_client(self, mock_anthropic_client):
        """Test creating Claude client via factory."""
        from factorylm.llm.claude_client import ClaudeClient

        client = create_llm_client("claude", "test-api-key")
        assert isinstance(client, ClaudeClient)
        assert isinstance(client, BaseLLMClient)
        assert client.get_model_name() == "claude-3-sonnet-20240229"

    def test_create_flm_client(self):
        """Test creating FLM client via factory."""
        from factorylm.llm.flm_client import FLMClient

        client = create_llm_client("flm", "test-api-key")
        assert isinstance(client, FLMClient)
        assert isinstance(client, BaseLLMClient)
        assert client.get_model_name() == "flm-industrial-v1"

    def test_create_with_custom_model(self, mock_groq_client):
        """Test creating client with custom model."""
        client = create_llm_client("groq", "test-key", model="llama3-70b-8192")
        assert client.get_model_name() == "llama3-70b-8192"

    def test_case_insensitive_provider(self, mock_groq_client):
        """Test that provider name is case-insensitive."""
        client1 = create_llm_client("GROQ", "key")
        client2 = create_llm_client("Groq", "key")
        client3 = create_llm_client("groq", "key")

        assert type(client1).__name__ == "GroqClient"
        assert type(client2).__name__ == "GroqClient"
        assert type(client3).__name__ == "GroqClient"

    def test_invalid_provider_raises_error(self):
        """Test that invalid provider raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            create_llm_client("invalid_provider", "key")
        assert "Unknown provider" in str(exc_info.value)
        assert "groq" in str(exc_info.value).lower()


class TestProviderInterfaceCompliance:
    """Tests that all providers implement the interface correctly."""

    @pytest.fixture(params=["groq", "deepseek", "claude"])
    def provider_client(self, request, mock_groq_client, mock_openai_client, mock_anthropic_client):
        """Parametrized fixture for all providers."""
        return create_llm_client(request.param, "test-key")

    def test_all_providers_inherit_base_client(self, provider_client):
        """Test all providers inherit from BaseLLMClient."""
        assert isinstance(provider_client, BaseLLMClient)

    def test_all_providers_have_get_model_name(self, provider_client):
        """Test all providers implement get_model_name."""
        model = provider_client.get_model_name()
        assert isinstance(model, str)
        assert len(model) > 0

    def test_all_providers_have_estimate_cost(self, provider_client):
        """Test all providers implement estimate_cost."""
        response = LLMResponse(
            text="test",
            tokens_used=100,
            model=provider_client.get_model_name(),
            input_tokens=60,
            output_tokens=40,
        )
        cost = provider_client.estimate_cost(response)
        assert isinstance(cost, float)
        assert cost >= 0


class TestProviderSwitching:
    """Tests for switching between providers at runtime."""

    def test_switch_between_providers(
        self, mock_groq_client, mock_openai_client, mock_anthropic_client
    ):
        """Test switching between different providers."""
        # Start with GROQ
        groq_client = create_llm_client("groq", "key")
        assert "GroqClient" in type(groq_client).__name__

        # Switch to DeepSeek
        deepseek_client = create_llm_client("deepseek", "key")
        assert "DeepSeekClient" in type(deepseek_client).__name__

        # Switch to Claude
        claude_client = create_llm_client("claude", "key")
        assert "ClaudeClient" in type(claude_client).__name__

        # Both should still be usable
        assert groq_client.get_model_name() == "mixtral-8x7b-32768"
        assert deepseek_client.get_model_name() == "deepseek-chat"

    def test_responses_are_standardized(
        self, mock_groq_client, mock_openai_client, sample_messages
    ):
        """Test that all providers return standardized LLMResponse."""
        groq_client = create_llm_client("groq", "key")
        deepseek_client = create_llm_client("deepseek", "key")

        groq_response = groq_client.chat(sample_messages)
        deepseek_response = deepseek_client.chat(sample_messages)

        # Both should return LLMResponse
        assert isinstance(groq_response, LLMResponse)
        assert isinstance(deepseek_response, LLMResponse)

        # Both should have required fields
        for response in [groq_response, deepseek_response]:
            assert hasattr(response, "text")
            assert hasattr(response, "tokens_used")
            assert hasattr(response, "model")
            assert hasattr(response, "input_tokens")
            assert hasattr(response, "output_tokens")


class TestFLMClientSkeleton:
    """Tests for FLM client skeleton behavior."""

    def test_flm_not_yet_available(self):
        """Test that FLM raises NotImplementedError."""
        client = create_llm_client("flm", "key")

        with pytest.raises(NotImplementedError):
            client.analyze_machine_state("test", {"temp": 100})

    def test_flm_health_check_returns_false(self):
        """Test that FLM health check returns False."""
        client = create_llm_client("flm", "key")
        assert client.health_check() is False

    def test_flm_is_available_returns_false(self):
        """Test that FLM is_available returns False."""
        client = create_llm_client("flm", "key")
        assert client.is_available() is False

    def test_flm_availability_info(self):
        """Test FLM availability info."""
        client = create_llm_client("flm", "key")
        info = client.get_availability_info()

        assert info["available"] is False
        assert "alternative_providers" in info
        assert "groq" in info["alternative_providers"]


class TestAnalyzeMachineStateAcrossProviders:
    """Tests for analyze_machine_state across all providers."""

    def test_groq_analyze_machine_state(
        self, mock_groq_client, sample_machine_state, sample_question
    ):
        """Test GROQ analyze_machine_state."""
        client = create_llm_client("groq", "key")
        response = client.analyze_machine_state(sample_question, sample_machine_state)

        assert isinstance(response, LLMResponse)
        assert len(response.text) > 0

    def test_deepseek_analyze_machine_state(
        self, mock_openai_client, sample_machine_state, sample_question
    ):
        """Test DeepSeek analyze_machine_state."""
        client = create_llm_client("deepseek", "key")
        response = client.analyze_machine_state(sample_question, sample_machine_state)

        assert isinstance(response, LLMResponse)
        assert len(response.text) > 0

    def test_claude_analyze_machine_state(
        self, mock_anthropic_client, sample_machine_state, sample_question
    ):
        """Test Claude analyze_machine_state."""
        client = create_llm_client("claude", "key")
        response = client.analyze_machine_state(sample_question, sample_machine_state)

        assert isinstance(response, LLMResponse)
        assert len(response.text) > 0
