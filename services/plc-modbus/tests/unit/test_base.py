"""
Unit tests for BasePLCClient abstract base class.

Tests that the ABC cannot be instantiated directly and that the
context-manager protocol (__enter__ / __exit__) works correctly
through concrete implementations.

NEW for V3 — no direct V1/V2 equivalent.
"""

import pytest

from factorylm_plc.base import BasePLCClient
from factorylm_plc.mock_plc import MockPLC


class TestBasePLCClientABC:
    """Test abstract base class constraints."""

    def test_cannot_instantiate_directly(self):
        """BasePLCClient is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            BasePLCClient()

    def test_mock_is_subclass(self):
        """MockPLC is a valid subclass of BasePLCClient."""
        assert issubclass(MockPLC, BasePLCClient)
        plc = MockPLC()
        assert isinstance(plc, BasePLCClient)


class TestBasePLCClientContextManager:
    """Test context-manager protocol defined in BasePLCClient."""

    def test_enter_calls_connect(self):
        """__enter__ calls connect() and returns the instance."""
        plc = MockPLC()
        result = plc.__enter__()
        assert result is plc
        assert plc.is_connected()

    def test_exit_calls_disconnect(self):
        """__exit__ calls disconnect()."""
        plc = MockPLC()
        plc.__enter__()
        plc.__exit__(None, None, None)
        assert not plc.is_connected()

    def test_exit_returns_false(self):
        """__exit__ returns False (does not suppress exceptions)."""
        plc = MockPLC()
        plc.__enter__()
        result = plc.__exit__(None, None, None)
        assert result is False
