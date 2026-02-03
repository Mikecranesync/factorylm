"""
Unit Tests for Configuration Module

Tests for factorylm.config module.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from factorylm.config import (
    FactoryLMConfig,
    get_config,
    validate_config,
    load_env_file,
    VALID_PROVIDERS,
    DEFAULT_MODELS,
    get_llm_provider,
    get_llm_api_key,
    get_llm_model,
)


class TestFactoryLMConfig:
    """Tests for FactoryLMConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = FactoryLMConfig()
        assert config.llm_provider == "groq"
        assert config.llm_api_key == ""
        assert config.llm_model == DEFAULT_MODELS["groq"]
        assert config.log_level == "INFO"
        assert config.debug is False

    def test_custom_values(self):
        """Test custom configuration values."""
        config = FactoryLMConfig(
            llm_provider="claude",
            llm_api_key="test-key",
            llm_model="claude-3-opus-20240229",
            log_level="DEBUG",
            debug=True,
        )
        assert config.llm_provider == "claude"
        assert config.llm_api_key == "test-key"
        assert config.llm_model == "claude-3-opus-20240229"
        assert config.log_level == "DEBUG"
        assert config.debug is True

    def test_provider_lowercase_normalization(self):
        """Test that provider is normalized to lowercase."""
        config = FactoryLMConfig(llm_provider="GROQ")
        assert config.llm_provider == "groq"

        config = FactoryLMConfig(llm_provider="DeepSeek")
        assert config.llm_provider == "deepseek"

    def test_invalid_provider_raises_error(self):
        """Test that invalid provider raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            FactoryLMConfig(llm_provider="invalid_provider")
        assert "Invalid LLM provider" in str(exc_info.value)

    def test_default_model_per_provider(self):
        """Test that default model is set per provider."""
        for provider in VALID_PROVIDERS:
            config = FactoryLMConfig(llm_provider=provider, llm_model=None)
            assert config.llm_model == DEFAULT_MODELS[provider]

    def test_to_dict_excludes_api_key(self):
        """Test that to_dict doesn't expose the actual API key."""
        config = FactoryLMConfig(llm_api_key="secret-key-123")
        result = config.to_dict()
        assert "api_key_set" in result
        assert result["api_key_set"] is True
        assert "secret-key-123" not in str(result)

    def test_get_model(self):
        """Test get_model method."""
        config = FactoryLMConfig(llm_model="custom-model")
        assert config.get_model() == "custom-model"

        config = FactoryLMConfig(llm_provider="deepseek", llm_model=None)
        assert config.get_model() == DEFAULT_MODELS["deepseek"]


class TestValidateConfig:
    """Tests for validate_config function."""

    def test_valid_config(self):
        """Test validation of valid configuration."""
        config = FactoryLMConfig(llm_api_key="valid-key")
        result = validate_config(config)
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_missing_api_key(self):
        """Test validation fails when API key is missing."""
        config = FactoryLMConfig(llm_api_key="")
        result = validate_config(config)
        assert result["valid"] is False
        assert any("API_KEY" in err for err in result["errors"])

    def test_invalid_log_level(self):
        """Test validation fails for invalid log level."""
        config = FactoryLMConfig(llm_api_key="key", log_level="INVALID")
        result = validate_config(config)
        assert result["valid"] is False
        assert any("log level" in err.lower() for err in result["errors"])

    def test_valid_log_levels(self):
        """Test validation passes for valid log levels."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for level in valid_levels:
            config = FactoryLMConfig(llm_api_key="key", log_level=level)
            result = validate_config(config)
            assert result["valid"] is True


class TestGetConfig:
    """Tests for get_config function."""

    def test_loads_from_environment(self, temp_env):
        """Test configuration loads from environment variables."""
        temp_env(
            LLM_PROVIDER="deepseek",
            LLM_API_KEY="env-api-key",
            LLM_MODEL="deepseek-coder",
            LOG_LEVEL="WARNING",
            DEBUG="true",
        )

        # Force reload of config
        import factorylm.config as config_module
        config_module._config = None

        config = get_config()
        assert config.llm_provider == "deepseek"
        assert config.llm_api_key == "env-api-key"
        assert config.llm_model == "deepseek-coder"
        assert config.log_level == "WARNING"
        assert config.debug is True

    def test_default_values_when_env_not_set(self, clean_env):
        """Test default values are used when env vars not set."""
        # Clear relevant env vars
        for key in ["LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL", "LOG_LEVEL", "DEBUG"]:
            os.environ.pop(key, None)

        import factorylm.config as config_module
        config_module._config = None

        config = get_config()
        assert config.llm_provider == "groq"
        assert config.llm_api_key == ""
        assert config.log_level == "INFO"
        assert config.debug is False


class TestValidProviders:
    """Tests for provider validation."""

    def test_all_valid_providers(self):
        """Test all valid providers are accepted."""
        expected = ["groq", "deepseek", "claude", "flm"]
        assert set(VALID_PROVIDERS) == set(expected)

    def test_all_providers_have_default_models(self):
        """Test all providers have default models defined."""
        for provider in VALID_PROVIDERS:
            assert provider in DEFAULT_MODELS
            assert DEFAULT_MODELS[provider] is not None


class TestConvenienceFunctions:
    """Tests for convenience accessor functions."""

    def test_get_llm_provider(self, temp_env):
        """Test get_llm_provider function."""
        temp_env(LLM_PROVIDER="claude")

        import factorylm.config as config_module
        config_module._config = None

        result = get_llm_provider()
        assert result == "claude"

    def test_get_llm_api_key(self, temp_env):
        """Test get_llm_api_key function."""
        temp_env(LLM_API_KEY="my-secret-key")

        import factorylm.config as config_module
        config_module._config = None

        result = get_llm_api_key()
        assert result == "my-secret-key"

    def test_get_llm_model(self, temp_env):
        """Test get_llm_model function."""
        temp_env(LLM_MODEL="custom-model-v1")

        import factorylm.config as config_module
        config_module._config = None

        result = get_llm_model()
        assert result == "custom-model-v1"
