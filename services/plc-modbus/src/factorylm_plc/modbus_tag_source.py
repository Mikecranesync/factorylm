"""
Canonical Modbus tag source for Micro 820 PLC.

Reads coils 0-17 and holding registers 100-105 using the canonical
address map from CLAUDE.md, and returns TagSnapshot objects.

Gist verification (2026-03-03): All coil addresses (0-17) and register
addresses (100-105) verified against Mike's GitHub gists
(VFD_MODBUS_PROGRESS.md, tp-link-gs10-setup-guide.md). PLC coil map,
register map, and scaling factors (/10 for current and temperature)
all match. E-stop dual-contact logic (coils[8] AND NOT coils[9])
confirmed. See /cluster/betterclaw/memory/physical-layer.md for the
full cross-reference.

Usage:
    source = ModbusTagSource("192.168.1.100", 502)
    if source.connect():
        snap = source.tick()
        print(snap.to_dict())
"""
from __future__ import annotations

import datetime
import logging
import re

from .models import ERROR_CODES, TagSnapshot

logger = logging.getLogger(__name__)

STARDUST_ZONES = ("launch_1", "launch_2", "station_load", "station_unload")
STARDUST_SIGNALS = ("block_occupied", "lsm_ready", "brake_ready", "fault_latched")

REQUIRED_CANONICAL_TAGS = frozenset(
    {
        "conv_simple.motor_run",
        "conv_simple.vfd_speed_hz",
        "conv_simple.vfd_current_amps",
        "conv_simple.fault_code",
        "conv_simple.comm_ok",
        "conv_simple.height_sensor_mm",
        "conv_simple.sort_divert_active",
        *{
            f"stardust.{zone}.{signal}"
            for zone in STARDUST_ZONES
            for signal in STARDUST_SIGNALS
        },
    }
)

# Canonical tags whose values come from OPTIONAL `io` dict keys rather than
# the always-read coil/register map. The bench Micro820 map (CLAUDE.md) has no
# height-sensor or sort-divert I/O, so ModbusTagSource.tick() never populates
# these keys — canonical_tags_from_snapshot then falls back to 0/False. The
# envelope producer must downgrade their quality to `uncertain` in that case:
# a value the bridge never read from the PLC is never "good".
IO_SOURCED_CANONICAL_TAGS = {
    "conv_simple.height_sensor_mm": "height_sensor_mm",
    "conv_simple.sort_divert_active": "sort_divert_active",
}


def unsourced_canonical_tags(snapshot: TagSnapshot) -> frozenset[str]:
    """Canonical tag paths whose backing `io` key is absent from `snapshot`.

    These tags still appear in canonical_tags_from_snapshot's output (the
    seven-tag shape is the contract), but with a defaulted — not read —
    value, so the producer must not claim `good` quality for them.
    """
    io = snapshot.io or {}
    return frozenset(
        path for path, key in IO_SOURCED_CANONICAL_TAGS.items() if key not in io
    )


CONVEYOR_TAG_ALIASES = {
    "runcommand": "conv_simple.motor_run",
    "motorrun": "conv_simple.motor_run",
    "motor_running": "conv_simple.motor_run",
    "conveyor_running": "conv_simple.motor_run",
    "conveyorhz": "conv_simple.vfd_speed_hz",
    "vfdhz": "conv_simple.vfd_speed_hz",
    "vfd_hz": "conv_simple.vfd_speed_hz",
    "vfdspeedhz": "conv_simple.vfd_speed_hz",
    "vfd_speed_hz": "conv_simple.vfd_speed_hz",
    "motorcurrentx10": "conv_simple.vfd_current_amps",
    "motor_current_x10": "conv_simple.vfd_current_amps",
    "motor_current": "conv_simple.vfd_current_amps",
    "vfd_current": "conv_simple.vfd_current_amps",
    "vfd_amps": "conv_simple.vfd_current_amps",
    "errorcode": "conv_simple.fault_code",
    "error_code": "conv_simple.fault_code",
    "fault_code": "conv_simple.fault_code",
    "vfd_faultcode": "conv_simple.fault_code",
    "vfd_fault_code": "conv_simple.fault_code",
    "commok": "conv_simple.comm_ok",
    "comm_ok": "conv_simple.comm_ok",
    "vfd_comm_ok": "conv_simple.comm_ok",
    "heightsensormm": "conv_simple.height_sensor_mm",
    "height_sensor_mm": "conv_simple.height_sensor_mm",
    "sortdivertactive": "conv_simple.sort_divert_active",
    "sort_divert_active": "conv_simple.sort_divert_active",
}


def _normalize_tag_name(raw_name: str) -> str:
    """Normalize PLC, Ignition, or operator-facing tag labels for matching."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", raw_name)
    return re.sub(r"[^a-z0-9]+", "_", spaced.lower()).strip("_")


def canonical_tag_name(raw_name: str) -> str | None:
    """Map raw PLC/ride tag names to Hub canonical tag names."""
    normalized = _normalize_tag_name(raw_name)
    compact = normalized.replace("_", "")
    conveyor = CONVEYOR_TAG_ALIASES.get(normalized) or CONVEYOR_TAG_ALIASES.get(compact)
    if conveyor:
        return conveyor

    if "stardust" not in compact:
        return None

    zone_match = None
    for zone in STARDUST_ZONES:
        zone_compact = zone.replace("_", "")
        if zone in normalized or zone_compact in compact:
            zone_match = zone
            break
    if zone_match is None:
        return None

    for signal in STARDUST_SIGNALS:
        signal_compact = signal.replace("_", "")
        if signal in normalized or signal_compact in compact:
            return f"stardust.{zone_match}.{signal}"

    return None


def canonical_tags_from_snapshot(snapshot: TagSnapshot) -> dict[str, bool | int | float]:
    """Project a Micro820 snapshot into the Hub one-board canonical tags."""
    io = snapshot.io or {}
    running = bool(snapshot.motor_running or snapshot.conveyor_running)
    speed_hz = (snapshot.motor_speed or snapshot.conveyor_speed) if running else 0

    return {
        "conv_simple.motor_run": running,
        "conv_simple.vfd_speed_hz": int(speed_hz),
        "conv_simple.vfd_current_amps": float(snapshot.motor_current),
        "conv_simple.fault_code": int(snapshot.error_code),
        "conv_simple.comm_ok": int(snapshot.error_code) != 5,
        "conv_simple.height_sensor_mm": int(io.get("height_sensor_mm", 0)),
        "conv_simple.sort_divert_active": bool(io.get("sort_divert_active", False)),
    }


class ModbusTagSource:
    """Reads canonical Micro 820 tags via Modbus TCP and returns TagSnapshot."""

    def __init__(self, host: str, port: int = 502) -> None:
        self.host = host
        self.port = port
        self._client = None

    def connect(self) -> bool:
        """Create a Modbus TCP connection. Returns True on success."""
        try:
            from pymodbus.client import ModbusTcpClient
        except ImportError:
            logger.error("pymodbus not installed — pip install pymodbus")
            return False

        self._client = ModbusTcpClient(self.host, port=self.port, timeout=3)
        if self._client.connect():
            logger.info(
                "ModbusTagSource connected to %s:%d", self.host, self.port
            )
            return True

        logger.warning(
            "ModbusTagSource connection failed to %s:%d", self.host, self.port
        )
        self._client = None
        return False

    @property
    def connected(self) -> bool:
        return self._client is not None and self._client.is_socket_open()

    def tick(self) -> TagSnapshot:
        """Read all canonical tags and return a TagSnapshot.

        Auto-reconnects if the socket is dead.
        Returns a comms-fault snapshot on read failure.
        """
        if not self.connected:
            if not self.connect():
                return self._error_snapshot("connection failed")

        try:
            # Read coils 0-17
            coil_result = self._client.read_coils(address=0, count=18)
            if coil_result.isError():
                self._client.close()
                self._client = None
                return self._error_snapshot("coil read error")

            coils = [bool(b) for b in coil_result.bits[:18]]
            coils_int = [int(b) for b in coils]

            io = {
                "conveyor":     coils_int[0],
                "emitter":      coils_int[1],
                "sensor_start": coils_int[2],
                "sensor_end":   coils_int[3],
                "run_command":  coils_int[4],
                "di_center":    coils_int[7],
                "di_estop_no":  coils_int[8],
                "di_estop_nc":  coils_int[9],
                "di_right":     coils_int[10],
                "di_green_btn": coils_int[11],
                "do_fwd":       coils_int[15],
                "do_rev":       coils_int[16],
                "do_aux":       coils_int[17],
            }

            e_stop_ok = not coils[8] and coils[9]

            # Read holding registers 100-105
            reg_result = self._client.read_holding_registers(
                address=100, count=6
            )
            if reg_result.isError():
                self._client.close()
                self._client = None
                return self._error_snapshot("register read error")

            regs = reg_result.registers

            # --- Map to TagSnapshot fields ---

            # Coil 0 -> conveyor_running / motor_running
            conveyor_running = coils[0]
            motor_running = coils[0]

            # Coils 2, 3 -> SensorStart, SensorEnd
            sensor_1 = coils[2]
            sensor_2 = coils[3]

            # E-stop dual-contact validation: coil[8] AND NOT coil[9]
            e_stop_no = coils[8]
            e_stop_nc = coils[9]
            fault_alarm = e_stop_no and not e_stop_nc
            e_stop = fault_alarm

            # Registers (with scaling)
            motor_speed = regs[1]           # reg 101, 1x
            motor_current = regs[2] / 10.0  # reg 102, /10
            temperature = regs[3] / 10.0    # reg 103, /10
            pressure = regs[4]              # reg 104, 1x
            error_code = regs[5]            # reg 105, 1x

            return TagSnapshot(
                timestamp=datetime.datetime.now(
                    tz=datetime.timezone.utc
                ).isoformat(),
                node_id=f"plc-{self.host}",
                motor_running=motor_running,
                motor_speed=motor_speed,
                motor_current=round(motor_current, 1),
                temperature=round(temperature, 1),
                pressure=pressure,
                conveyor_running=conveyor_running,
                conveyor_speed=motor_speed,
                sensor_1=sensor_1,
                sensor_2=sensor_2,
                fault_alarm=fault_alarm,
                e_stop=e_stop,
                error_code=error_code,
                error_message=ERROR_CODES.get(
                    error_code, f"Unknown error {error_code}"
                ),
                coils=coils_int,
                io=io,
                e_stop_ok=e_stop_ok,
            )

        except Exception as e:
            logger.warning("ModbusTagSource read error: %s", e)
            if self._client:
                self._client.close()
                self._client = None
            return self._error_snapshot(str(e))

    def _error_snapshot(self, reason: str) -> TagSnapshot:
        """Return a comms-fault snapshot (error_code=5)."""
        return TagSnapshot(
            timestamp=datetime.datetime.now(
                tz=datetime.timezone.utc
            ).isoformat(),
            node_id=f"plc-{self.host}",
            motor_running=False,
            motor_speed=0,
            motor_current=0.0,
            temperature=0.0,
            pressure=0,
            conveyor_running=False,
            conveyor_speed=0,
            sensor_1=False,
            sensor_2=False,
            fault_alarm=True,
            e_stop=False,
            error_code=5,
            error_message=f"Communication loss: {reason}",
            coils=[0] * 18,
            io={
                "conveyor": 0, "emitter": 0, "sensor_start": 0,
                "sensor_end": 0, "run_command": 0, "di_center": 0,
                "di_estop_no": 0, "di_estop_nc": 0, "di_right": 0,
                "di_green_btn": 0, "do_fwd": 0, "do_rev": 0, "do_aux": 0,
            },
            e_stop_ok=False,
        )
