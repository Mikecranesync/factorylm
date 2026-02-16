"""
Pytest configuration and shared fixtures for factorylm_plc tests.

Provides reusable fixtures for MockPLC, connection managers, and
factory-created clients used across unit and integration tests.
"""

import pytest

from factorylm_plc.mock_plc import MockPLC
from factorylm_plc.connection_manager import PLCConnectionManager
from factorylm_plc.factory import create_plc_client


@pytest.fixture
def mock_plc():
    """Provide a disconnected MockPLC instance."""
    return MockPLC()


@pytest.fixture
def connected_mock_plc():
    """Provide a connected MockPLC instance, disconnected after test."""
    plc = MockPLC()
    plc.connect()
    yield plc
    if plc.is_connected():
        plc.disconnect()


@pytest.fixture
def connection_manager():
    """Provide a PLCConnectionManager wrapping a MockPLC."""
    plc = MockPLC()
    return PLCConnectionManager(plc)


@pytest.fixture
def factory_mock_client():
    """Provide a MockPLC created via the factory function."""
    return create_plc_client("mock")
