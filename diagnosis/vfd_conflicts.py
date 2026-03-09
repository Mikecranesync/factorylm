"""
VFD Conflict Detection — Cross-reference PLC + VFD + Belt Vision.

Six conflict detectors (V001-V006) that catch mismatches between
the PLC commanding the motor, VFD drive status, and vision-measured
belt behavior.

Usage:
    conflicts = detect_conflicts(plc_tags, vfd_tags, belt_status)
    for c in conflicts:
        print(f"[{c.code}] {c.title} — {c.severity}")
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Conflict:
    code: str                       # V001-V006
    severity: str                   # "warning" | "critical"
    title: str
    description: str
    affected_tags: list[str] = field(default_factory=list)


def detect_conflicts(
    plc_tags: dict,
    vfd_tags: dict | None,
    belt_status: dict | None,
) -> list[Conflict]:
    """Analyze PLC + VFD + belt data and return active conflicts.

    Returns empty list when VFD is not connected or not configured.
    Skips vision-dependent checks when belt_status is None.
    """
    conflicts: list[Conflict] = []

    # No VFD data → nothing to cross-reference
    if vfd_tags is None or not vfd_tags.get("vfd_connected", False):
        return conflicts

    # Extract VFD values with safe defaults
    vfd_output_hz = float(vfd_tags.get("vfd_output_hz", 0))
    vfd_control_word = int(vfd_tags.get("vfd_control_word", 0))
    vfd_output_amps = float(vfd_tags.get("vfd_output_amps", 0))
    vfd_setpoint_hz = float(vfd_tags.get("vfd_setpoint_hz", 0))
    vfd_motor_rpm = float(vfd_tags.get("vfd_motor_rpm", 0))
    vfd_drive_temp_c = float(vfd_tags.get("vfd_drive_temp_c", 0))
    vfd_fault_code = int(vfd_tags.get("vfd_fault_code", 0))

    # Extract PLC values
    conveyor_running = bool(plc_tags.get("conveyor_running", False))

    # Extract belt vision values
    belt_stat = None
    belt_rpm = 0.0
    if belt_status is not None:
        belt_stat = belt_status.get("belt_status", "")
        belt_rpm = float(belt_status.get("belt_rpm", 0))

    # V001 — Belt stopped while VFD running
    if belt_status is not None and belt_stat == "STOPPED" and vfd_output_hz > 0.5:
        conflicts.append(Conflict(
            code="V001",
            severity="critical",
            title="Belt stopped while VFD running",
            description=(
                f"VFD outputting {vfd_output_hz:.1f} Hz but belt vision reports STOPPED. "
                "Possible mechanical disconnect, broken belt, or slip."
            ),
            affected_tags=["belt_status", "vfd_output_hz"],
        ))

    # V002 — No current despite run command
    if vfd_control_word in (0x0001, 0x0003) and vfd_output_amps < 0.1:
        conflicts.append(Conflict(
            code="V002",
            severity="critical",
            title="No current despite run command",
            description=(
                f"VFD control word = 0x{vfd_control_word:04X} (run) but output current "
                f"is {vfd_output_amps:.1f} A. Possible wiring fault or open circuit."
            ),
            affected_tags=["vfd_control_word", "vfd_output_amps"],
        ))

    # V003 — Can't reach setpoint frequency
    if (
        vfd_output_hz > 0
        and vfd_setpoint_hz > 0
        and abs(vfd_output_hz - vfd_setpoint_hz) > 2.0
    ):
        conflicts.append(Conflict(
            code="V003",
            severity="warning",
            title="Cannot reach setpoint frequency",
            description=(
                f"VFD setpoint is {vfd_setpoint_hz:.1f} Hz but actual output is "
                f"{vfd_output_hz:.1f} Hz (delta {abs(vfd_output_hz - vfd_setpoint_hz):.1f} Hz). "
                "Possible overload or current limit active."
            ),
            affected_tags=["vfd_setpoint_hz", "vfd_output_hz"],
        ))

    # V004 — Belt speed mismatch vs VFD
    if belt_status is not None and belt_rpm > 0 and vfd_motor_rpm > 0:
        ratio = belt_rpm / vfd_motor_rpm
        if abs(1.0 - ratio) > 0.30:
            conflicts.append(Conflict(
                code="V004",
                severity="warning",
                title="Belt speed mismatch vs VFD",
                description=(
                    f"Vision belt RPM ({belt_rpm:.0f}) differs from VFD motor RPM "
                    f"({vfd_motor_rpm:.0f}) by {abs(1.0 - ratio) * 100:.0f}%. "
                    "Possible belt slip or gearbox issue."
                ),
                affected_tags=["belt_rpm", "vfd_motor_rpm"],
            ))

    # V005 — VFD drive overtemperature
    if vfd_drive_temp_c > 75.0:
        severity = "critical" if vfd_drive_temp_c > 90.0 else "warning"
        conflicts.append(Conflict(
            code="V005",
            severity=severity,
            title="VFD drive overtemperature",
            description=(
                f"VFD heatsink temperature is {vfd_drive_temp_c:.1f} C "
                f"({'CRITICAL' if severity == 'critical' else 'elevated'}). "
                "Check cooling fan and ambient temperature."
            ),
            affected_tags=["vfd_drive_temp_c"],
        ))

    # V006 — VFD fault while PLC commanding run
    if vfd_fault_code > 0 and conveyor_running:
        from net.drivers.vfd_reader import VFD_FAULT_CODES

        fault_desc = VFD_FAULT_CODES.get(vfd_fault_code, f"Unknown ({vfd_fault_code})")
        conflicts.append(Conflict(
            code="V006",
            severity="critical",
            title="VFD fault while PLC commanding run",
            description=(
                f"VFD fault code {vfd_fault_code} ({fault_desc}) but PLC coil 0 "
                "is ON (conveyor_running). PLC may not know about VFD fault."
            ),
            affected_tags=["vfd_fault_code", "conveyor_running"],
        ))

    return conflicts
