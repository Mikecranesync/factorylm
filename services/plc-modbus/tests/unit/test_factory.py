"""
Unit tests for the create_plc_client / create_managed_client factory functions.

Tests client type dispatch, environment-variable overrides, and
managed-client creation.

Migrated from plc-client-factoryio/tests/test_factory.py (V2) and
plc-client/tests/integration/test_end_to_end.py (V1 factory tests).
Key V3 changes:
  - Factory module is ``factorylm_plc.factory``
  - FactoryIOMicro820 imported from ``factorylm_plc.factory_io``
"""

import pytest

from factorylm_plc.factory import create_plc_client, create_managed_client
from factorylm_plc.mock_plc import MockPLC
from factorylm_plc.micro820 import Micro820PLC
from factorylm_plc.factory_io import FactoryIOMicro820
from factorylm_plc.connection_manager import PLCConnectionManager
from factorylm_plc.base import BasePLCClient


# ---------------------------------------------------------------------------
# create_plc_client
# ---------------------------------------------------------------------------


class TestCreatePLCClient:
    """Test create_plc_client factory dispatch."""

    def test_create_mock_client(self):
        """'mock' type returns a MockPLC."""
        client = create_plc_client("mock")
        assert isinstance(client, MockPLC)
        assert isinstance(client, BasePLCClient)

    def test_create_micro820_client(self):
        """'micro820' type returns a Micro820PLC."""
        client = create_plc_client("micro820", host="192.168.1.100")
        assert isinstance(client, Micro820PLC)
        assert client.host == "192.168.1.100"
        assert client.port == 502

    def test_create_factoryio_client(self):
        """'factoryio_micro820' type returns a FactoryIOMicro820."""
        client = create_plc_client("factoryio_micro820", host="192.168.1.100")
        assert isinstance(client, FactoryIOMicro820)
        assert client.host == "192.168.1.100"

    def test_create_factoryio_aliases(self):
        """'factoryio' and 'factory_io' are aliases for factoryio_micro820."""
        c1 = create_plc_client("factoryio", host="192.168.1.100")
        c2 = create_plc_client("factory_io", host="192.168.1.100")
        assert isinstance(c1, FactoryIOMicro820)
        assert isinstance(c2, FactoryIOMicro820)

    def test_invalid_plc_type_raises(self):
        """Unknown PLC type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown PLC type"):
            create_plc_client("invalid_type")

    def test_custom_port(self):
        """Custom port is forwarded to the client."""
        client = create_plc_client("micro820", host="192.168.1.100", port=5020)
        assert client.port == 5020

    def test_custom_timeout(self):
        """Custom timeout is forwarded to the client."""
        client = create_plc_client("micro820", host="192.168.1.100", timeout=10.0)
        assert client.timeout == 10.0

    def test_custom_retries(self):
        """Custom retries is forwarded to the client."""
        client = create_plc_client("micro820", host="192.168.1.100", retries=5)
        assert client.retries == 5

    def test_scene_name(self):
        """scene_name is forwarded to FactoryIOMicro820."""
        client = create_plc_client(
            "factoryio_micro820",
            host="192.168.1.100",
            scene_name="assembly_line",
        )
        assert client.scene_name == "assembly_line"


class TestCreatePLCClientEnvironment:
    """Test environment variable overrides."""

    def test_env_use_mock_override(self, monkeypatch):
        """USE_MOCK_PLC=true forces mock client regardless of type."""
        monkeypatch.setenv("USE_MOCK_PLC", "true")
        client = create_plc_client("factoryio_micro820", host="192.168.1.100")
        assert isinstance(client, MockPLC)

    def test_env_defaults(self, monkeypatch):
        """Environment variables provide defaults when args are None."""
        monkeypatch.setenv("PLC_TYPE", "mock")
        monkeypatch.setenv("PLC_HOST", "10.0.0.1")
        monkeypatch.setenv("PLC_PORT", "5020")

        client = create_plc_client()
        assert isinstance(client, MockPLC)

    def test_explicit_params_override_env(self, monkeypatch):
        """Explicit parameters take precedence over env vars."""
        monkeypatch.setenv("PLC_HOST", "10.0.0.1")
        monkeypatch.setenv("PLC_PORT", "5020")

        client = create_plc_client("micro820", host="192.168.1.100", port=502)
        assert client.host == "192.168.1.100"
        assert client.port == 502


# ---------------------------------------------------------------------------
# create_managed_client
# ---------------------------------------------------------------------------


class TestCreateManagedClient:
    """Test create_managed_client wrapper."""

    def test_returns_connection_manager(self):
        """Returns a PLCConnectionManager wrapping the correct client."""
        manager = create_managed_client("mock")
        assert isinstance(manager, PLCConnectionManager)
        assert isinstance(manager.client, MockPLC)

    def test_auto_reconnect_flag(self):
        """auto_reconnect parameter is forwarded."""
        manager = create_managed_client("mock", auto_reconnect=False)
        assert manager.auto_reconnect is False

    def test_managed_client_context_manager(self):
        """Managed client works as a context manager."""
        with create_managed_client("mock") as manager:
            assert manager.is_connected
            state = manager.client.read_state()
            assert state is not None
