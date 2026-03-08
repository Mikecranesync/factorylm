"""
Integration Tests for LiteLLM Client

Tests that verify the LiteLLM client module exports and helper functions work.
These tests mock the OpenAI client to avoid requiring a running LiteLLM Proxy.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestLiteLLMClientModule:
    """Tests for the LiteLLM client module."""

    def test_module_exports(self):
        """Test that the module exports the expected symbols."""
        from factorylm.llm.client import llm_client, llm_async_client, diagnose_fault, async_diagnose, classify_intent
        assert llm_client is not None
        assert llm_async_client is not None
        assert callable(diagnose_fault)
        assert callable(async_diagnose)
        assert callable(classify_intent)

    def test_init_exports(self):
        """Test that __init__.py re-exports client symbols."""
        from factorylm.llm import llm_client, llm_async_client, diagnose_fault, LLMResponse
        assert llm_client is not None
        assert llm_async_client is not None
        assert callable(diagnose_fault)
        assert LLMResponse is not None

    @patch("factorylm.llm.client.llm_client")
    def test_diagnose_fault(self, mock_client):
        """Test diagnose_fault calls LiteLLM correctly."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Check the VFD frequency setpoint."
        mock_client.chat.completions.create.return_value = mock_response

        from factorylm.llm.client import diagnose_fault
        result = diagnose_fault("You are a tech.", "What does V003 mean?")

        assert result == "Check the VFD frequency setpoint."
        mock_client.chat.completions.create.assert_called_once()

    @patch("factorylm.llm.client.llm_client")
    def test_diagnose_fault_handles_error(self, mock_client):
        """Test diagnose_fault returns None on error."""
        mock_client.chat.completions.create.side_effect = Exception("Connection refused")

        from factorylm.llm.client import diagnose_fault
        result = diagnose_fault("system", "question")
        assert result is None

    @patch("factorylm.llm.client.llm_client")
    def test_classify_intent(self, mock_client):
        """Test classify_intent uses local-gemma model."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "fault_report"
        mock_client.chat.completions.create.return_value = mock_response

        from factorylm.llm.client import classify_intent
        result = classify_intent("conveyor 3 is throwing a fault")

        assert result == "fault_report"
        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == "local-gemma"
