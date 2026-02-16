"""
Unit tests for PLCConnectionManager.

Tests connection management, retry logic, exponential backoff,
read_with_retry / write_with_retry, and status reporting.

Migrated from plc-client-factoryio/tests/test_connection_manager.py (V2).
Adapted for V3 API — no significant changes needed.
"""

import pytest

from factorylm_plc.connection_manager import PLCConnectionManager
from factorylm_plc.mock_plc import MockPLC


class TestPLCConnectionManager:
    """Core connection-manager tests."""

    def test_ensure_connected_success(self):
        """ensure_connected returns True after successful connection."""
        plc = MockPLC()
        manager = PLCConnectionManager(plc)

        result = manager.ensure_connected()
        assert result is True
        assert manager.is_connected

    def test_context_manager(self):
        """Context manager connects on enter, disconnects on exit."""
        plc = MockPLC()
        with PLCConnectionManager(plc) as manager:
            assert manager.is_connected
        assert not manager.is_connected

    def test_disconnect(self):
        """disconnect() sets is_connected to False."""
        plc = MockPLC()
        manager = PLCConnectionManager(plc)
        manager.ensure_connected()
        manager.disconnect()
        assert not manager.is_connected

    def test_auto_reconnect_disabled(self):
        """auto_reconnect flag is stored correctly."""
        plc = MockPLC()
        manager = PLCConnectionManager(plc, auto_reconnect=False)
        assert manager.auto_reconnect is False

    def test_get_status(self):
        """get_status returns expected keys and values."""
        plc = MockPLC()
        manager = PLCConnectionManager(plc, retry_count=5, retry_delay=2.0)
        manager.ensure_connected()

        status = manager.get_status()
        assert status["connected"] is True
        assert status["retry_count"] == 5
        assert status["retry_delay"] == 2.0
        assert status["consecutive_failures"] == 0
        assert status["last_error"] is None


class TestPLCConnectionManagerReadWrite:
    """Test read_with_retry and write_with_retry."""

    def test_read_with_retry_success(self):
        """read_with_retry returns the result of a successful read."""
        plc = MockPLC()
        manager = PLCConnectionManager(plc)

        result = manager.read_with_retry(lambda: plc.read_state())
        assert result is not None
        assert hasattr(result, "motor_running")

    def test_write_with_retry_success(self):
        """write_with_retry returns True for a successful write."""
        plc = MockPLC()
        manager = PLCConnectionManager(plc)
        manager.ensure_connected()

        result = manager.write_with_retry(lambda: plc.write_coil(0, True))
        assert result is True


class TestPLCConnectionManagerBackoff:
    """Test exponential backoff calculation."""

    def test_base_delay(self):
        """Zero failures → base delay."""
        plc = MockPLC()
        manager = PLCConnectionManager(plc, retry_delay=1.0)
        manager._consecutive_failures = 0
        assert manager._calculate_backoff() == 1.0

    def test_one_failure_backoff(self):
        """One failure → 2× delay."""
        plc = MockPLC()
        manager = PLCConnectionManager(plc, retry_delay=1.0)
        manager._consecutive_failures = 1
        assert manager._calculate_backoff() == 2.0

    def test_two_failures_backoff(self):
        """Two failures → 4× delay."""
        plc = MockPLC()
        manager = PLCConnectionManager(plc, retry_delay=1.0)
        manager._consecutive_failures = 2
        assert manager._calculate_backoff() == 4.0

    def test_backoff_capped_at_max(self):
        """Many failures → capped at MAX_BACKOFF_DELAY."""
        plc = MockPLC()
        manager = PLCConnectionManager(plc, retry_delay=1.0)
        manager._consecutive_failures = 10
        assert manager._calculate_backoff() == manager.MAX_BACKOFF_DELAY

    def test_consecutive_failures_tracking(self):
        """Consecutive failures counter starts at zero."""
        plc = MockPLC()
        manager = PLCConnectionManager(plc)
        assert manager._consecutive_failures == 0

        manager.ensure_connected()
        assert manager._consecutive_failures == 0
