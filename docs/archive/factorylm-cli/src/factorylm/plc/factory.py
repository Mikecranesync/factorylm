"""PLC client factory — auto-detect protocol and create the right driver."""

from __future__ import annotations

from factorylm.plc.base import BasePLCClient


def create_client(
    plc_type: str = "modbus",
    host: str = "192.168.1.100",
    port: int = 502,
    unit_id: int = 1,
    rack: int = 0,
    slot: int = 1,
    tags: list | None = None,
) -> BasePLCClient:
    """Create a PLC client based on protocol type.

    Args:
        plc_type: One of "modbus", "enip", "s7".
        host: PLC IP address.
        port: Protocol port.
        unit_id: Modbus unit/slave ID.
        rack: S7 rack number.
        slot: S7 slot number.
        tags: List of tag names (enip) or tag tuples (s7).
    """
    plc_type = plc_type.lower().strip()

    if plc_type == "modbus":
        from factorylm.plc.modbus import ModbusPLCClient
        return ModbusPLCClient(host=host, port=port, unit_id=unit_id)

    if plc_type == "enip":
        from factorylm.plc.enip import EtherNetIPClient
        kwargs: dict = {"host": host, "port": port}
        if tags:
            kwargs["tags"] = tags
        return EtherNetIPClient(**kwargs)

    if plc_type == "s7":
        from factorylm.plc.s7 import S7Client
        kwargs = {"host": host, "port": port, "rack": rack, "slot": slot}
        if tags:
            kwargs["tags"] = tags
        return S7Client(**kwargs)

    raise ValueError(f"Unknown PLC type: {plc_type!r}. Choose from: modbus, enip, s7")


def create_client_from_config(cfg) -> BasePLCClient:
    """Create a PLC client from a FactoryLMConfig.plc section."""
    return create_client(
        plc_type=cfg.type,
        host=cfg.host,
        port=cfg.port,
        unit_id=cfg.unit_id,
        rack=cfg.rack,
        slot=cfg.slot,
        tags=cfg.tags if cfg.type in ("enip", "s7") else None,
    )
