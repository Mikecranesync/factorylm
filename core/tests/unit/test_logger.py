"""
Unit Tests for Logger Module

Tests for factorylm.utils.logger module.
"""

import pytest
import logging
import os
import tempfile

from factorylm.utils.logger import (
    setup_logging,
    get_logger,
    LogContext,
    log_llm_request,
)


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_default_logging(self):
        """Test setup with default parameters."""
        logger = setup_logging()
        assert logger.name == "factorylm"
        assert logger.level == logging.INFO

    def test_setup_debug_logging(self):
        """Test setup with DEBUG level."""
        logger = setup_logging(level="DEBUG")
        assert logger.level == logging.DEBUG

    def test_setup_warning_logging(self):
        """Test setup with WARNING level."""
        logger = setup_logging(level="WARNING")
        assert logger.level == logging.WARNING

    def test_setup_with_file(self):
        """Test setup with log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            logger = setup_logging(log_file=log_file)

            # Log a message
            logger.info("Test message")

            # Check file was created and contains message
            assert os.path.exists(log_file)
            with open(log_file) as f:
                content = f.read()
                assert "Test message" in content

            # Close handlers to release file lock on Windows
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)

    def test_setup_replaces_handlers(self):
        """Test that setup replaces existing handlers."""
        logger = setup_logging()
        initial_handlers = len(logger.handlers)

        # Call setup again
        setup_logging()

        # Should still have same number of handlers
        assert len(logger.handlers) == initial_handlers


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_package_logger(self):
        """Test getting the package logger."""
        logger = get_logger()
        assert logger.name == "factorylm"

    def test_get_child_logger(self):
        """Test getting a child logger."""
        logger = get_logger("llm.groq")
        assert logger.name == "factorylm.llm.groq"

    def test_get_another_child_logger(self):
        """Test getting another child logger."""
        logger = get_logger("config")
        assert logger.name == "factorylm.config"


class TestLogContext:
    """Tests for LogContext context manager."""

    def test_log_context_changes_level(self):
        """Test that LogContext changes log level."""
        setup_logging(level="INFO")
        logger = get_logger()

        original_level = logger.level

        with LogContext(level="DEBUG"):
            assert logger.level == logging.DEBUG

        # Should be restored
        assert logger.level == original_level

    def test_log_context_restores_on_exception(self):
        """Test that LogContext restores level even on exception."""
        setup_logging(level="INFO")
        logger = get_logger()

        original_level = logger.level

        try:
            with LogContext(level="DEBUG"):
                raise ValueError("Test error")
        except ValueError:
            pass

        # Should be restored
        assert logger.level == original_level


class TestLogLLMRequest:
    """Tests for log_llm_request function."""

    def test_log_successful_request(self, caplog):
        """Test logging a successful request."""
        setup_logging(level="INFO")

        with caplog.at_level(logging.INFO, logger="factorylm.llm"):
            log_llm_request(
                provider="groq",
                model="mixtral-8x7b-32768",
                tokens=150,
                cost=0.000036,
                success=True,
            )

        assert "groq" in caplog.text
        assert "mixtral" in caplog.text
        assert "150" in caplog.text

    def test_log_failed_request(self, caplog):
        """Test logging a failed request."""
        setup_logging(level="ERROR")

        with caplog.at_level(logging.ERROR, logger="factorylm.llm"):
            log_llm_request(
                provider="deepseek",
                model="deepseek-chat",
                tokens=0,
                cost=0.0,
                success=False,
                error="Rate limit exceeded",
            )

        assert "deepseek" in caplog.text
        assert "Rate limit" in caplog.text
        assert "Failed" in caplog.text
