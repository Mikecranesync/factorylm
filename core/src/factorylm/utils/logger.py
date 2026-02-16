"""
FactoryLM Logging Utilities

Provides configured logging for FactoryLM components.
"""

import logging
import sys
from typing import Optional
from pathlib import Path


# Default log format
DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Package logger
_package_logger: Optional[logging.Logger] = None


def setup_logging(
    level: str = "INFO",
    format_string: str = DEFAULT_FORMAT,
    date_format: str = DEFAULT_DATE_FORMAT,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """
    Set up logging for FactoryLM.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Log message format
        date_format: Date format for timestamps
        log_file: Optional file path to write logs to

    Returns:
        Configured logger instance

    Example:
        >>> logger = setup_logging(level="DEBUG")
        >>> logger.debug("This is a debug message")
    """
    global _package_logger

    # Get numeric level
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(format_string, date_format)

    # Create/configure package logger
    logger = logging.getLogger("factorylm")
    logger.setLevel(numeric_level)

    # Remove existing handlers
    logger.handlers.clear()

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Add file handler if specified
    if log_file:
        file_path = Path(log_file)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    _package_logger = logger
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger for FactoryLM components.

    Args:
        name: Optional name for child logger (e.g., "llm.groq")
              If None, returns the package logger

    Returns:
        Logger instance

    Example:
        >>> logger = get_logger("llm.groq")
        >>> logger.info("GROQ client initialized")
    """
    global _package_logger

    # Ensure package logger is configured
    if _package_logger is None:
        setup_logging()

    if name:
        return logging.getLogger(f"factorylm.{name}")
    return logging.getLogger("factorylm")


class LogContext:
    """
    Context manager for temporary log level changes.

    Example:
        >>> logger = get_logger()
        >>> with LogContext(level="DEBUG"):
        ...     logger.debug("This will be logged")
        >>> logger.debug("This might not be logged")
    """

    def __init__(self, level: str = "DEBUG", logger_name: str = "factorylm"):
        """
        Initialize log context.

        Args:
            level: Temporary log level
            logger_name: Logger to modify
        """
        self.level = getattr(logging, level.upper(), logging.DEBUG)
        self.logger = logging.getLogger(logger_name)
        self.original_level = self.logger.level

    def __enter__(self):
        """Set temporary log level."""
        self.logger.setLevel(self.level)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore original log level."""
        self.logger.setLevel(self.original_level)
        return False


def log_llm_request(
    provider: str,
    model: str,
    tokens: int,
    cost: float,
    success: bool = True,
    error: Optional[str] = None,
) -> None:
    """
    Log an LLM API request for tracking.

    Args:
        provider: LLM provider name
        model: Model used
        tokens: Total tokens consumed
        cost: Estimated cost in USD
        success: Whether request succeeded
        error: Error message if failed
    """
    logger = get_logger("llm")

    if success:
        logger.info(
            f"LLM Request: provider={provider} model={model} "
            f"tokens={tokens} cost=${cost:.6f}"
        )
    else:
        logger.error(
            f"LLM Request Failed: provider={provider} model={model} "
            f"error={error}"
        )
