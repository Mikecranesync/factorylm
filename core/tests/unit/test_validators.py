"""
Unit Tests for Validators Module

Tests for factorylm.utils.validators module.
"""

import pytest

from factorylm.utils.validators import (
    ValidationError,
    validate_api_key,
    validate_machine_state,
    validate_question,
    validate_messages,
    validate_temperature,
    validate_max_tokens,
)


class TestValidateApiKey:
    """Tests for validate_api_key function."""

    def test_valid_api_key(self):
        """Test validation of valid API key."""
        result = validate_api_key("sk-abc123xyz")
        assert result == "sk-abc123xyz"

    def test_strips_whitespace(self):
        """Test that whitespace is stripped."""
        result = validate_api_key("  sk-abc123  ")
        assert result == "sk-abc123"

    def test_none_raises_error(self):
        """Test that None raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_api_key(None)
        assert exc_info.value.field == "api_key"

    def test_empty_string_raises_error(self):
        """Test that empty string raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_api_key("")

    def test_non_string_raises_error(self):
        """Test that non-string raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_api_key(12345)

    def test_placeholder_values_rejected(self):
        """Test that placeholder values are rejected."""
        placeholders = [
            "your-api-key",
            "your_api_key",
            "api-key-here",
            "api_key_here",
            "xxxxxxxx",
            "placeholder",
            "test-key",
        ]
        for placeholder in placeholders:
            with pytest.raises(ValidationError):
                validate_api_key(placeholder)


class TestValidateMachineState:
    """Tests for validate_machine_state function."""

    def test_valid_machine_state(self):
        """Test validation of valid machine state."""
        state = {"temp": 100, "pressure": 50.5, "status": "running"}
        result = validate_machine_state(state)
        assert result == state

    def test_nested_state(self):
        """Test validation of nested machine state."""
        state = {
            "sensors": {
                "temp": 100,
                "pressure": 50,
            },
            "alarms": ["WARN1", "WARN2"],
        }
        result = validate_machine_state(state)
        assert result == state

    def test_none_raises_error(self):
        """Test that None raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_machine_state(None)

    def test_empty_dict_raises_error(self):
        """Test that empty dict raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_machine_state({})

    def test_non_dict_raises_error(self):
        """Test that non-dict raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_machine_state([1, 2, 3])

    def test_invalid_nested_type(self):
        """Test that invalid nested types are rejected."""

        class CustomClass:
            pass

        with pytest.raises(ValidationError):
            validate_machine_state({"obj": CustomClass()})


class TestValidateQuestion:
    """Tests for validate_question function."""

    def test_valid_question(self):
        """Test validation of valid question."""
        result = validate_question("Why is the motor overheating?")
        assert result == "Why is the motor overheating?"

    def test_strips_whitespace(self):
        """Test that whitespace is stripped."""
        result = validate_question("  What is wrong?  ")
        assert result == "What is wrong?"

    def test_none_raises_error(self):
        """Test that None raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_question(None)

    def test_empty_string_raises_error(self):
        """Test that empty string raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_question("")

    def test_too_short_raises_error(self):
        """Test that too short question raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_question("ab")

    def test_too_long_raises_error(self):
        """Test that too long question raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_question("x" * 10001)

    def test_non_string_raises_error(self):
        """Test that non-string raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_question(123)


class TestValidateMessages:
    """Tests for validate_messages function."""

    def test_valid_messages(self):
        """Test validation of valid messages."""
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]
        result = validate_messages(messages)
        assert len(result) == 2

    def test_all_valid_roles(self):
        """Test that all valid roles are accepted."""
        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "User"},
            {"role": "assistant", "content": "Assistant"},
        ]
        result = validate_messages(messages)
        assert len(result) == 3

    def test_empty_list_raises_error(self):
        """Test that empty list raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_messages([])

    def test_non_list_raises_error(self):
        """Test that non-list raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_messages("not a list")

    def test_missing_role_raises_error(self):
        """Test that missing role raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_messages([{"content": "Hello"}])

    def test_missing_content_raises_error(self):
        """Test that missing content raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_messages([{"role": "user"}])

    def test_invalid_role_raises_error(self):
        """Test that invalid role raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_messages([{"role": "invalid", "content": "test"}])


class TestValidateTemperature:
    """Tests for validate_temperature function."""

    def test_valid_temperature(self):
        """Test validation of valid temperature."""
        assert validate_temperature(0.7) == 0.7
        assert validate_temperature(0) == 0.0
        assert validate_temperature(2.0) == 2.0

    def test_integer_converted_to_float(self):
        """Test that integer is converted to float."""
        result = validate_temperature(1)
        assert result == 1.0
        assert isinstance(result, float)

    def test_too_low_raises_error(self):
        """Test that temperature below 0 raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_temperature(-0.1)

    def test_too_high_raises_error(self):
        """Test that temperature above 2 raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_temperature(2.1)

    def test_non_number_raises_error(self):
        """Test that non-number raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_temperature("warm")


class TestValidateMaxTokens:
    """Tests for validate_max_tokens function."""

    def test_valid_max_tokens(self):
        """Test validation of valid max_tokens."""
        assert validate_max_tokens(100) == 100
        assert validate_max_tokens(1) == 1
        assert validate_max_tokens(100000) == 100000

    def test_zero_raises_error(self):
        """Test that zero raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_max_tokens(0)

    def test_negative_raises_error(self):
        """Test that negative raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_max_tokens(-1)

    def test_too_high_raises_error(self):
        """Test that too high value raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_max_tokens(100001)

    def test_non_integer_raises_error(self):
        """Test that non-integer raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_max_tokens(100.5)


class TestValidationError:
    """Tests for ValidationError exception."""

    def test_basic_error(self):
        """Test basic ValidationError."""
        error = ValidationError("Test error")
        assert str(error) == "Test error"
        assert error.field is None
        assert error.value is None

    def test_error_with_field(self):
        """Test ValidationError with field."""
        error = ValidationError("Invalid", field="api_key", value="bad")
        assert error.field == "api_key"
        assert error.value == "bad"
