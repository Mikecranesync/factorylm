"""Tests for PLC driver interfaces and factory."""

from factorylm.plc.base import BasePLCClient
from factorylm.plc.factory import create_client


def test_create_client_modbus():
    """Factory should create ModbusPLCClient for type='modbus'."""
    client = create_client(plc_type="modbus", host="127.0.0.1", port=5020)
    assert isinstance(client, BasePLCClient)
    assert hasattr(client, "connect")
    assert hasattr(client, "read_tags")
    assert hasattr(client, "write_tag")


def test_create_client_enip():
    client = create_client(plc_type="enip", host="127.0.0.1")
    assert isinstance(client, BasePLCClient)


def test_create_client_s7():
    client = create_client(plc_type="s7", host="127.0.0.1")
    assert isinstance(client, BasePLCClient)


def test_create_client_unknown():
    import pytest
    with pytest.raises(ValueError, match="Unknown PLC type"):
        create_client(plc_type="profinet")


def test_modbus_client_attributes():
    """ModbusPLCClient should store config."""
    from factorylm.plc.modbus import ModbusPLCClient
    client = ModbusPLCClient(host="10.0.0.1", port=5020, unit_id=2)
    assert client.host == "10.0.0.1"
    assert client.port == 5020
    assert client.unit_id == 2
    assert not client.is_connected()
