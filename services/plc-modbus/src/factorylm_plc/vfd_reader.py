"""Async Modbus TCP reader for VFD (Variable Frequency Drive) live tags.

Reads holding registers and coils from a VFD over Modbus TCP, applies
scale factors, derives fault descriptions and calculated tags, and
caches the last known good reading for graceful degradation.

Register map is overridable via JSON file at VFD_REGISTER_MAP env var
or /etc/pifactory/vfd_register_map.json.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# VFD fault code table — plain English
# ---------------------------------------------------------------------------

VFD_FAULTS: Dict[int, str] = {
    0: "No Fault",
    1: "Overcurrent (OC) — motor drawing too much, check for jam",
    2: "Overvoltage (OV) — regen or input spike, check decel ramp",
    3: "Undervoltage (UV) — input power sag/loss, check supply",
    4: "Overtemperature — drive or motor too hot, check fan",
    5: "Ground Fault — motor winding or cable fault, megger test",
    6: "Input Phase Loss — missing phase on input, check 3-phase supply",
    7: "Output Phase Loss — motor or cable open phase, check terminals",
    8: "Comms Loss — Modbus timeout, check Ethernet cable",
    9: "External Fault — input from PLC/safety relay, check E-stop",
}


# ---------------------------------------------------------------------------
# Default register map (common across most VFDs)
# ---------------------------------------------------------------------------

DEFAULT_REGISTER_MAP: Dict[str, Dict[str, Any]] = {
    "vfd_output_hz":      {"address": 100, "scale": 0.1, "type": "holding"},
    "vfd_setpoint_hz":    {"address": 101, "scale": 0.1, "type": "holding"},
    "vfd_output_amps":    {"address": 102, "scale": 0.1, "type": "holding"},
    "vfd_output_volts":   {"address": 103, "scale": 0.1, "type": "holding"},
    "vfd_dc_bus_volts":   {"address": 104, "scale": 0.1, "type": "holding"},
    "vfd_motor_rpm":      {"address": 105, "scale": 1,   "type": "holding"},
    "vfd_torque_pct":     {"address": 106, "scale": 0.1, "type": "holding"},
    "vfd_drive_temp_c":   {"address": 107, "scale": 0.1, "type": "holding"},
    "vfd_power_kw":       {"address": 108, "scale": 0.01, "type": "holding"},
    "vfd_fault_code":     {"address": 109, "scale": 1,   "type": "holding"},
    "vfd_accel_time_sec": {"address": 110, "scale": 0.1, "type": "holding"},
    "vfd_decel_time_sec": {"address": 111, "scale": 0.1, "type": "holding"},
    "vfd_run_status":     {"address": 0,   "scale": 1,   "type": "coil"},
}

# Paths to check for register map override (first match wins)
_REGISTER_MAP_PATHS = [
    "/etc/pifactory/vfd_register_map.json",
]


def _load_register_map(path: str = "") -> Dict[str, Dict[str, Any]]:
    """Load register map from JSON file, falling back to built-in defaults."""
    search_paths: List[str] = []
    if path:
        search_paths.append(path)
    search_paths.extend(_REGISTER_MAP_PATHS)

    for p in search_paths:
        fp = Path(p)
        if fp.exists():
            try:
                data = json.loads(fp.read_text())
                logger.info("Loaded VFD register map from %s", fp)
                return data
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load register map %s: %s", fp, exc)

    return dict(DEFAULT_REGISTER_MAP)


# ---------------------------------------------------------------------------
# VFDReader
# ---------------------------------------------------------------------------

class VFDReader:
    """Async Modbus TCP reader for all VFD tags."""

    def __init__(
        self,
        host: str = "",
        port: int = 502,
        slave_id: int = 1,
        register_map_path: str = "",
        brand: str = "generic",
    ) -> None:
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.brand = brand
        self.register_map = _load_register_map(register_map_path)

        # Last known good reading (returned on comms failure)
        self._last_reading: Dict[str, Any] = self._zeroed_tags()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def read_all_tags(self) -> Dict[str, Any]:
        """Read all VFD registers and return a tag dict.

        On connection failure, returns last known good values with
        vfd_comms_ok=False.  Never raises.
        """
        if not self.host:
            return self._zeroed_tags()

        try:
            from pymodbus.client import AsyncModbusTcpClient  # type: ignore[import-untyped]
        except ImportError:
            logger.warning("pymodbus not installed — VFD reader disabled")
            result = dict(self._last_reading)
            result["vfd_comms_ok"] = False
            result["vfd_comms_error"] = "pymodbus not installed"
            return result

        try:
            client = AsyncModbusTcpClient(self.host, port=self.port)
            await client.connect()

            if not client.connected:
                raise ConnectionError(f"Cannot connect to {self.host}:{self.port}")

            tags: Dict[str, Any] = {}

            # Separate holding registers from coils
            holding_tags = {
                k: v for k, v in self.register_map.items()
                if v.get("type", "holding") == "holding"
            }
            coil_tags = {
                k: v for k, v in self.register_map.items()
                if v.get("type") == "coil"
            }

            # Read holding registers in batch if contiguous
            if holding_tags:
                addresses = [v["address"] for v in holding_tags.values()]
                min_addr = min(addresses)
                max_addr = max(addresses)
                count = max_addr - min_addr + 1

                resp = await client.read_holding_registers(
                    min_addr, count=count, slave=self.slave_id,
                )
                if resp.isError():
                    raise ConnectionError(f"Modbus error reading registers: {resp}")

                for tag_name, reg_info in holding_tags.items():
                    idx = reg_info["address"] - min_addr
                    raw = resp.registers[idx]
                    tags[tag_name] = round(raw * reg_info.get("scale", 1), 2)

            # Read coils
            for tag_name, reg_info in coil_tags.items():
                resp = await client.read_coils(
                    reg_info["address"], count=1, slave=self.slave_id,
                )
                if resp.isError():
                    tags[tag_name] = False
                else:
                    tags[tag_name] = bool(resp.bits[0])

            client.close()

            # Derived: fault description
            fault_code = int(tags.get("vfd_fault_code", 0))
            tags["vfd_fault_description"] = VFD_FAULTS.get(fault_code, f"Unknown fault ({fault_code})")

            # Derived: setpoint vs actual gap
            setpoint = float(tags.get("vfd_setpoint_hz", 0))
            actual = float(tags.get("vfd_output_hz", 0))
            tags["vfd_setpoint_vs_actual_hz"] = round(setpoint - actual, 1)

            # Comms status
            tags["vfd_comms_ok"] = True
            tags["vfd_comms_error"] = ""

            self._last_reading = tags
            return tags

        except Exception as exc:
            logger.warning("VFD read failed (%s:%d): %s", self.host, self.port, exc)
            result = dict(self._last_reading)
            result["vfd_comms_ok"] = False
            result["vfd_comms_error"] = str(exc)
            return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _zeroed_tags() -> Dict[str, Any]:
        """Return a tag dict with all values zeroed / defaulted."""
        return {
            "vfd_output_hz": 0.0,
            "vfd_setpoint_hz": 0.0,
            "vfd_output_amps": 0.0,
            "vfd_output_volts": 0.0,
            "vfd_dc_bus_volts": 0.0,
            "vfd_motor_rpm": 0,
            "vfd_torque_pct": 0.0,
            "vfd_drive_temp_c": 0.0,
            "vfd_power_kw": 0.0,
            "vfd_fault_code": 0,
            "vfd_accel_time_sec": 0.0,
            "vfd_decel_time_sec": 0.0,
            "vfd_run_status": False,
            "vfd_fault_description": "No Fault",
            "vfd_setpoint_vs_actual_hz": 0.0,
            "vfd_comms_ok": False,
            "vfd_comms_error": "VFD not connected — set VFD_HOST to enable",
        }
