"""
FactoryLM Test Configuration and Fixtures

Provides shared fixtures and configuration for all tests.
"""

import os
import pytest
from typing import Dict, Any
from unittest.mock import MagicMock, patch


# Set test environment variables before imports
os.environ.setdefault("LLM_PROVIDER", "groq")
os.environ.setdefault("LLM_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("LLM_MODEL", "mixtral-8x7b-32768")
os.environ.setdefault("LOG_LEVEL", "DEBUG")
os.environ.setdefault("DEBUG", "true")


@pytest.fixture
def sample_machine_state() -> Dict[str, Any]:
    """Provide a sample machine state for testing."""
    return {
        "temperature": 150.5,
        "pressure_psi": 45.0,
        "rpm": 1200,
        "motor_current": 12.5,
        "vibration_hz": 60,
        "status": "running",
        "alarms": [],
        "sensors": {
            "inlet_temp": 72.0,
            "outlet_temp": 185.0,
        },
    }


@pytest.fixture
def sample_machine_state_with_issues() -> Dict[str, Any]:
    """Provide a machine state with issues for testing."""
    return {
        "temperature": 250.0,  # High temperature
        "pressure_psi": 120.0,  # High pressure
        "rpm": 0,  # Motor stopped
        "motor_current": 0.0,
        "vibration_hz": 150,  # High vibration
        "status": "fault",
        "alarms": ["HIGH_TEMP", "HIGH_PRESSURE", "MOTOR_FAULT"],
        "error_code": "E-501",
    }


@pytest.fixture
def sample_question() -> str:
    """Provide a sample technician question."""
    return "Why is the motor temperature rising above normal levels?"


@pytest.fixture
def sample_messages():
    """Provide sample chat messages."""
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the status of the pump?"},
    ]


@pytest.fixture
def mock_groq_response():
    """Create a mock GROQ API response."""
    response = MagicMock()
    response.choices = [
        MagicMock(
            message=MagicMock(content="The motor temperature is within normal range."),
            finish_reason="stop",
        )
    ]
    response.usage = MagicMock(
        total_tokens=150,
        prompt_tokens=100,
        completion_tokens=50,
    )
    response.model = "mixtral-8x7b-32768"
    return response


@pytest.fixture
def mock_deepseek_response():
    """Create a mock DeepSeek API response."""
    response = MagicMock()
    response.choices = [
        MagicMock(
            message=MagicMock(content="Analysis complete. No issues detected."),
            finish_reason="stop",
        )
    ]
    response.usage = MagicMock(
        total_tokens=120,
        prompt_tokens=80,
        completion_tokens=40,
    )
    response.model = "deepseek-chat"
    return response


@pytest.fixture
def mock_claude_response():
    """Create a mock Claude API response."""
    response = MagicMock()
    response.content = [MagicMock(text="The system appears to be operating normally.")]
    response.usage = MagicMock(
        input_tokens=100,
        output_tokens=30,
    )
    response.model = "claude-3-sonnet-20240229"
    response.stop_reason = "end_turn"
    return response


@pytest.fixture
def mock_groq_client(mock_groq_response):
    """Create a mock GROQ client."""
    with patch("factorylm.llm.groq_client.Groq") as mock_class:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create.return_value = mock_groq_response
        mock_class.return_value = mock_instance
        yield mock_class


@pytest.fixture
def mock_openai_client(mock_deepseek_response):
    """Create a mock OpenAI client (for DeepSeek)."""
    with patch("factorylm.llm.deepseek_client.OpenAI") as mock_class:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create.return_value = mock_deepseek_response
        mock_class.return_value = mock_instance
        yield mock_class


@pytest.fixture
def mock_anthropic_client(mock_claude_response):
    """Create a mock Anthropic client."""
    with patch("factorylm.llm.claude_client.Anthropic") as mock_class:
        mock_instance = MagicMock()
        mock_instance.messages.create.return_value = mock_claude_response
        mock_class.return_value = mock_instance
        yield mock_class


@pytest.fixture
def clean_env():
    """Provide a clean environment for testing."""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def temp_env(clean_env):
    """Provide temporary environment variables."""

    def _set_env(**kwargs):
        for key, value in kwargs.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = str(value)

    return _set_env


# Pytest markers
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, isolated)")
    config.addinivalue_line(
        "markers", "integration: Integration tests (may require external services)"
    )
    config.addinivalue_line("markers", "slow: Slow tests")
