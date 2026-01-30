"""
PLC connection manager with retry logic and reconnection handling.

Provides resilient connection management for production deployments.
"""

import logging
import time
from typing import Callable, TypeVar, Optional, Any

from .base import BasePLCClient

logger = logging.getLogger(__name__)

T = TypeVar("T")


class PLCConnectionManager:
    """
    Manages connection to PLC with automatic reconnection and retry logic.

    Wraps any BasePLCClient and provides:
    - Automatic reconnection on connection loss
    - Retry logic for transient failures
    - Connection state tracking
    - Exponential backoff for repeated failures
    """

    DEFAULT_RETRY_COUNT = 3
    DEFAULT_RETRY_DELAY = 1.0
    MAX_BACKOFF_DELAY = 30.0

    def __init__(
        self,
        client: BasePLCClient,
        retry_count: int = DEFAULT_RETRY_COUNT,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        auto_reconnect: bool = True,
    ):
        """
        Initialize PLCConnectionManager.

        Args:
            client: PLC client to manage.
            retry_count: Number of retry attempts for operations.
            retry_delay: Base delay between retries in seconds.
            auto_reconnect: Whether to automatically reconnect on failure.
        """
        self.client = client
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.auto_reconnect = auto_reconnect

        self._connected = False
        self._consecutive_failures = 0
        self._last_error: Optional[Exception] = None

    @property
    def is_connected(self) -> bool:
        """Check if currently connected."""
        return self._connected and self.client.is_connected()

    @property
    def last_error(self) -> Optional[Exception]:
        """Get the last error that occurred."""
        return self._last_error

    def _calculate_backoff(self) -> float:
        """Calculate exponential backoff delay."""
        delay = self.retry_delay * (2 ** min(self._consecutive_failures, 5))
        return min(delay, self.MAX_BACKOFF_DELAY)

    def ensure_connected(self) -> bool:
        """
        Ensure connection to PLC is established.

        Will attempt to reconnect if disconnected and auto_reconnect is enabled.

        Returns:
            bool: True if connected, False otherwise.
        """
        if self.client.is_connected():
            self._connected = True
            return True

        if not self.auto_reconnect:
            return False

        # Attempt to connect with retries
        for attempt in range(self.retry_count):
            try:
                logger.info(f"Connection attempt {attempt + 1}/{self.retry_count}")

                if self.client.connect():
                    self._connected = True
                    self._consecutive_failures = 0
                    self._last_error = None
                    logger.info("Connection established successfully")
                    return True

            except Exception as e:
                self._last_error = e
                logger.warning(f"Connection attempt {attempt + 1} failed: {e}")

            # Wait before retry with backoff
            if attempt < self.retry_count - 1:
                delay = self._calculate_backoff()
                logger.debug(f"Waiting {delay:.1f}s before retry")
                time.sleep(delay)

        self._consecutive_failures += 1
        self._connected = False
        logger.error(f"Failed to connect after {self.retry_count} attempts")
        return False

    def disconnect(self) -> None:
        """Disconnect from PLC."""
        try:
            self.client.disconnect()
        except Exception as e:
            logger.warning(f"Error during disconnect: {e}")
        finally:
            self._connected = False

    def read_with_retry(self, func: Callable[[], T]) -> T:
        """
        Execute a read function with automatic retry and reconnection.

        Args:
            func: Function to execute (should be a read operation on self.client).

        Returns:
            T: Result of the function call.

        Raises:
            ConnectionError: If unable to connect after retries.
            IOError: If operation fails after retries.
        """
        for attempt in range(self.retry_count):
            try:
                # Ensure we're connected
                if not self.ensure_connected():
                    raise ConnectionError("Unable to connect to PLC")

                # Execute the function
                result = func()
                self._consecutive_failures = 0
                return result

            except ConnectionError:
                self._connected = False
                self._consecutive_failures += 1
                self._last_error = ConnectionError("Connection lost")

                if attempt < self.retry_count - 1:
                    delay = self._calculate_backoff()
                    logger.warning(
                        f"Connection lost, retrying in {delay:.1f}s "
                        f"(attempt {attempt + 1}/{self.retry_count})"
                    )
                    time.sleep(delay)
                else:
                    raise

            except IOError as e:
                self._last_error = e
                self._consecutive_failures += 1

                if attempt < self.retry_count - 1:
                    delay = self._calculate_backoff()
                    logger.warning(
                        f"Read error: {e}, retrying in {delay:.1f}s "
                        f"(attempt {attempt + 1}/{self.retry_count})"
                    )
                    time.sleep(delay)
                else:
                    raise

        # Should not reach here, but just in case
        raise IOError("Operation failed after all retries")

    def write_with_retry(self, func: Callable[[], bool]) -> bool:
        """
        Execute a write function with automatic retry and reconnection.

        Args:
            func: Function to execute (should be a write operation on self.client).

        Returns:
            bool: True if write successful after retries.

        Raises:
            ConnectionError: If unable to connect after retries.
            IOError: If operation fails after retries.
        """
        for attempt in range(self.retry_count):
            try:
                # Ensure we're connected
                if not self.ensure_connected():
                    raise ConnectionError("Unable to connect to PLC")

                # Execute the function
                result = func()
                if result:
                    self._consecutive_failures = 0
                    return True

                # Write returned False - might be transient
                raise IOError("Write operation returned False")

            except ConnectionError:
                self._connected = False
                self._consecutive_failures += 1
                self._last_error = ConnectionError("Connection lost")

                if attempt < self.retry_count - 1:
                    delay = self._calculate_backoff()
                    logger.warning(
                        f"Connection lost, retrying in {delay:.1f}s "
                        f"(attempt {attempt + 1}/{self.retry_count})"
                    )
                    time.sleep(delay)
                else:
                    raise

            except IOError as e:
                self._last_error = e
                self._consecutive_failures += 1

                if attempt < self.retry_count - 1:
                    delay = self._calculate_backoff()
                    logger.warning(
                        f"Write error: {e}, retrying in {delay:.1f}s "
                        f"(attempt {attempt + 1}/{self.retry_count})"
                    )
                    time.sleep(delay)
                else:
                    raise

        return False

    def get_status(self) -> dict:
        """
        Get the current connection manager status.

        Returns:
            dict: Status information including connection state and error history.
        """
        return {
            "connected": self.is_connected,
            "consecutive_failures": self._consecutive_failures,
            "last_error": str(self._last_error) if self._last_error else None,
            "auto_reconnect": self.auto_reconnect,
            "retry_count": self.retry_count,
            "retry_delay": self.retry_delay,
        }

    def __enter__(self):
        """Context manager entry - ensure connection."""
        self.ensure_connected()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - disconnect."""
        self.disconnect()
        return False
