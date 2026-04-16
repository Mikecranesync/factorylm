"""Pure machine-state detection from a plc-modbus IO snapshot.

This module has NO I/O — no DB, no HTTP.  It is a set of pure
functions that map IO data to a MachineStateEnum + optional downtime
reason_code.  This makes it trivially unit-testable.

State transition logic (from PRD-MES-CORE.md §4.4):

    VFDStatus=1, ErrorCode=0          → RUNNING
    VFDStatus=2  OR  ErrorCode > 0    → DOWN   (+ reason_code)
    VFDStatus=0, ErrorCode=0          → IDLE
    PLCOfflineError (HTTP failure)    → OFFLINE  (handled by poller)

ErrorCode → reason_code map:
    0 → None           (no fault)
    1 → OVERLOAD
    2 → OVERHEAT
    3 → SENSOR_FAIL
    4 → JAM
    7 → E_STOP
    other → UNKNOWN
"""

from typing import Optional, Tuple

from backend.models.db_models import MachineStateEnum

# Maps plc-modbus ErrorCode register values to downtime_reasons.code keys.
# Seeded in migration 0001.
ERROR_CODE_REASON_MAP: dict = {
    1: "OVERLOAD",
    2: "OVERHEAT",
    3: "SENSOR_FAIL",
    4: "JAM",
    7: "E_STOP",
}


def detect_state(
    io_data: dict,
) -> Tuple[MachineStateEnum, Optional[str]]:
    """Derive machine state from a plc-modbus IO snapshot.

    Args:
        io_data: Parsed JSON from GET /api/plc/io.

    Returns:
        Tuple of (MachineStateEnum, reason_code_or_None).
        reason_code is only set when state is DOWN.
    """
    registers = io_data.get("registers", {})
    vfd_status = registers.get("VFDStatus", 0)
    error_code = registers.get("ErrorCode", 0)

    # Fault takes priority — VFD may still claim running during transition
    if vfd_status == 2 or error_code > 0:
        reason = ERROR_CODE_REASON_MAP.get(error_code, "UNKNOWN")
        return MachineStateEnum.DOWN, reason

    if vfd_status == 1:
        return MachineStateEnum.RUNNING, None

    # vfd_status == 0, no error → idle
    return MachineStateEnum.IDLE, None


def is_transition(
    current: Optional[MachineStateEnum],
    new: MachineStateEnum,
) -> bool:
    """Return True if state has changed (or current is unknown)."""
    return current is None or current != new


def state_label(state: MachineStateEnum) -> str:
    """Human-readable state label for logs and API responses."""
    return state.value
