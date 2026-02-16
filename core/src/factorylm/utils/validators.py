"""
FactoryLM Validation Utilities

Provides input validation for LLM requests and machine state data.
"""

from typing import Dict, Any, List, Optional, Tuple
import re


class ValidationError(Exception):
    """Raised when validation fails."""

    def __init__(self, message: str, field: str = None, value: Any = None):
        self.message = message
        self.field = field
        self.value = value
        super().__init__(self.message)


def validate_api_key(api_key: Any, provider: str = "unknown") -> str:
    """
    Validate an API key.

    Args:
        api_key: The API key to validate
        provider: Provider name for error messages

    Returns:
        The validated API key (stripped of whitespace)

    Raises:
        ValidationError: If API key is invalid
    """
    if api_key is None:
        raise ValidationError(
            f"API key for {provider} is required",
            field="api_key",
            value=None,
        )

    if not isinstance(api_key, str):
        raise ValidationError(
            f"API key must be a string, got {type(api_key).__name__}",
            field="api_key",
            value=type(api_key).__name__,
        )

    api_key = api_key.strip()

    if not api_key:
        raise ValidationError(
            f"API key for {provider} cannot be empty",
            field="api_key",
            value="",
        )

    # Check for placeholder values
    placeholder_patterns = [
        r"^your[_-]?api[_-]?key",
        r"^api[_-]?key[_-]?here",
        r"^xxx+$",
        r"^placeholder",
        r"^test[_-]?key",
    ]

    for pattern in placeholder_patterns:
        if re.match(pattern, api_key.lower()):
            raise ValidationError(
                f"API key appears to be a placeholder value",
                field="api_key",
                value=api_key[:10] + "...",
            )

    return api_key


def validate_machine_state(machine_state: Any) -> Dict[str, Any]:
    """
    Validate machine state data.

    Args:
        machine_state: The machine state to validate

    Returns:
        The validated machine state dictionary

    Raises:
        ValidationError: If machine state is invalid
    """
    if machine_state is None:
        raise ValidationError(
            "Machine state is required",
            field="machine_state",
            value=None,
        )

    if not isinstance(machine_state, dict):
        raise ValidationError(
            f"Machine state must be a dictionary, got {type(machine_state).__name__}",
            field="machine_state",
            value=type(machine_state).__name__,
        )

    if not machine_state:
        raise ValidationError(
            "Machine state cannot be empty",
            field="machine_state",
            value={},
        )

    # Validate all values are JSON-serializable types
    valid_types = (int, float, str, bool, list, dict, type(None))

    def check_value(key: str, value: Any, path: str = "") -> None:
        current_path = f"{path}.{key}" if path else key

        if not isinstance(value, valid_types):
            raise ValidationError(
                f"Invalid type for '{current_path}': {type(value).__name__}",
                field=current_path,
                value=type(value).__name__,
            )

        if isinstance(value, dict):
            for k, v in value.items():
                check_value(k, v, current_path)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                check_value(f"[{i}]", item, current_path)

    for key, value in machine_state.items():
        check_value(key, value)

    return machine_state


def validate_question(question: Any) -> str:
    """
    Validate a technician question.

    Args:
        question: The question to validate

    Returns:
        The validated question string (stripped of whitespace)

    Raises:
        ValidationError: If question is invalid
    """
    if question is None:
        raise ValidationError(
            "Question is required",
            field="question",
            value=None,
        )

    if not isinstance(question, str):
        raise ValidationError(
            f"Question must be a string, got {type(question).__name__}",
            field="question",
            value=type(question).__name__,
        )

    question = question.strip()

    if not question:
        raise ValidationError(
            "Question cannot be empty",
            field="question",
            value="",
        )

    # Check minimum length (reasonable question should have some content)
    if len(question) < 3:
        raise ValidationError(
            "Question is too short (minimum 3 characters)",
            field="question",
            value=question,
        )

    # Check maximum length (prevent abuse)
    max_length = 10000
    if len(question) > max_length:
        raise ValidationError(
            f"Question is too long (maximum {max_length} characters)",
            field="question",
            value=f"{question[:50]}... ({len(question)} chars)",
        )

    return question


def validate_messages(messages: Any) -> List[Dict[str, str]]:
    """
    Validate chat messages format.

    Args:
        messages: List of message dictionaries

    Returns:
        Validated messages list

    Raises:
        ValidationError: If messages format is invalid
    """
    if not isinstance(messages, list):
        raise ValidationError(
            f"Messages must be a list, got {type(messages).__name__}",
            field="messages",
            value=type(messages).__name__,
        )

    if not messages:
        raise ValidationError(
            "Messages list cannot be empty",
            field="messages",
            value=[],
        )

    valid_roles = {"system", "user", "assistant"}
    validated = []

    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            raise ValidationError(
                f"Message {i} must be a dictionary",
                field=f"messages[{i}]",
                value=type(msg).__name__,
            )

        if "role" not in msg:
            raise ValidationError(
                f"Message {i} missing 'role' field",
                field=f"messages[{i}].role",
                value=None,
            )

        if "content" not in msg:
            raise ValidationError(
                f"Message {i} missing 'content' field",
                field=f"messages[{i}].content",
                value=None,
            )

        role = msg["role"]
        if role not in valid_roles:
            raise ValidationError(
                f"Invalid role '{role}' in message {i}. Valid: {valid_roles}",
                field=f"messages[{i}].role",
                value=role,
            )

        content = msg["content"]
        if not isinstance(content, str):
            raise ValidationError(
                f"Message {i} content must be a string",
                field=f"messages[{i}].content",
                value=type(content).__name__,
            )

        validated.append({"role": role, "content": content})

    return validated


def validate_temperature(temperature: Any) -> float:
    """
    Validate temperature parameter.

    Args:
        temperature: Temperature value

    Returns:
        Validated temperature float

    Raises:
        ValidationError: If temperature is invalid
    """
    if not isinstance(temperature, (int, float)):
        raise ValidationError(
            f"Temperature must be a number, got {type(temperature).__name__}",
            field="temperature",
            value=type(temperature).__name__,
        )

    temperature = float(temperature)

    if temperature < 0.0 or temperature > 2.0:
        raise ValidationError(
            f"Temperature must be between 0.0 and 2.0, got {temperature}",
            field="temperature",
            value=temperature,
        )

    return temperature


def validate_max_tokens(max_tokens: Any) -> int:
    """
    Validate max_tokens parameter.

    Args:
        max_tokens: Maximum tokens value

    Returns:
        Validated max_tokens integer

    Raises:
        ValidationError: If max_tokens is invalid
    """
    if not isinstance(max_tokens, int):
        raise ValidationError(
            f"max_tokens must be an integer, got {type(max_tokens).__name__}",
            field="max_tokens",
            value=type(max_tokens).__name__,
        )

    if max_tokens < 1:
        raise ValidationError(
            f"max_tokens must be at least 1, got {max_tokens}",
            field="max_tokens",
            value=max_tokens,
        )

    if max_tokens > 100000:
        raise ValidationError(
            f"max_tokens exceeds maximum (100000), got {max_tokens}",
            field="max_tokens",
            value=max_tokens,
        )

    return max_tokens
