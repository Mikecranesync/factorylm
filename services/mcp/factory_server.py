"""MCP server for Factory IO — PLC state reading, fault injection, and tag monitoring.

Exposes tools for reading Factory IO state, injecting faults, and watching
tag changes via Modbus TCP. Uses the existing ModbusController and scenario
definitions from tools/fault_injector/.

# SAFETY: Tools that write to e_stop (coil 6) log warnings and require
# explicit confirmation via the MCP permission system.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Ensure monorepo root is on path for imports
_monorepo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _monorepo not in sys.path:
    sys.path.insert(0, _monorepo)

app = FastMCP("factorylm-factory")

_controller = None


def _get_controller():
    """Lazy-init ModbusController with connection."""
    global _controller
    if _controller is None:
        from tools.fault_injector.modbus_control import ModbusController
        _controller = ModbusController()
    if _controller.client is None or not _controller.client.is_socket_open():
        connected = _controller.connect()
        if not connected:
            raise RuntimeError(
                f"Cannot connect to Modbus at {_controller.host}:{_controller.port}. "
                "Is Factory IO running with the Modbus TCP server enabled?"
            )
    return _controller


# ---------------------------------------------------------------------------
# Tools — Read
# ---------------------------------------------------------------------------


@app.tool()
def factory_read_state() -> dict[str, Any]:
    """Read complete Factory IO state — all coils and registers.

    Returns a dict with coil values (bool) and register values (int).
    Register values use raw Modbus integers (motor_current and temperature
    are scaled ×10, e.g. 25 = 2.5A, 650 = 65.0°C).
    """
    try:
        ctrl = _get_controller()
        state = ctrl.read_all_state()
        # Add human-readable scaled values
        if state.get("motor_current") is not None:
            state["motor_current_amps"] = state["motor_current"] / 10.0
        if state.get("temperature") is not None:
            state["temperature_celsius"] = state["temperature"] / 10.0
        return {"status": "ok", "tags": state}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.tool()
def factory_list_scenarios() -> list[dict[str, str]]:
    """List all available fault injection scenarios.

    Returns scenario IDs, names, and descriptions that can be passed
    to factory_inject_fault().
    """
    from tools.fault_injector.scenarios import list_scenarios
    return list_scenarios()


# ---------------------------------------------------------------------------
# Tools — Write (fault injection)
# ---------------------------------------------------------------------------


@app.tool()
def factory_inject_fault(scenario: str, hold_seconds: int = 10) -> dict[str, Any]:
    """Inject a fault scenario into Factory IO via Modbus.

    Available scenarios: motor_overload, overheat, sensor_jam, low_pressure,
    emergency_stop, sensor_failure, normal.

    The fault is injected and held for hold_seconds. During this time,
    the diagnosis system should detect and classify the fault.

    Args:
        scenario: Scenario ID (use factory_list_scenarios to see options)
        hold_seconds: How long to hold the fault state (default 10s)
    """
    from tools.fault_injector.scenarios import run_scenario

    messages = []

    def callback(msg: str):
        messages.append(msg)

    try:
        result = run_scenario(scenario, hold_seconds=hold_seconds, callback=callback)
        result["messages"] = messages
        return result
    except Exception as e:
        return {"status": "error", "error": str(e), "messages": messages}


@app.tool()
def factory_clear_faults() -> dict[str, Any]:
    """Clear all fault conditions and return Factory IO to normal operation.

    Resets: fault_alarm, e_stop, error_code, temperature, pressure, motor_current.
    """
    try:
        ctrl = _get_controller()
        ctrl.clear_all_faults()
        state = ctrl.read_all_state()
        return {"status": "ok", "message": "All faults cleared", "tags": state}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.tool()
def factory_write_coil(name: str, value: bool) -> dict[str, Any]:
    """Write a single coil value in Factory IO.

    # SAFETY: Writing to e_stop (coil 6) will halt all motion.
    This action is logged and should only be used for testing.

    Available coils: motor_running (0), motor_stopped (1), fault_alarm (2),
    conveyor_running (3), sensor_1 (4), sensor_2 (5), e_stop (6).

    Args:
        name: Coil name (e.g. "motor_running", "fault_alarm")
        value: Boolean value to write
    """
    if name == "e_stop":
        logger.warning("# SAFETY: Writing to e_stop coil — all motion will halt")

    try:
        ctrl = _get_controller()
        ctrl.write_coil(name, value)
        return {"status": "ok", "coil": name, "value": value}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.tool()
def factory_write_register(name: str, value: int) -> dict[str, Any]:
    """Write a single holding register value in Factory IO.

    Available registers: motor_speed (100), motor_current (101),
    temperature (102), pressure (103), conveyor_speed (104), error_code (105).

    Note: motor_current and temperature use ×10 scaling
    (e.g. write 25 for 2.5A, write 850 for 85.0°C).

    Args:
        name: Register name (e.g. "motor_speed", "temperature")
        value: Integer value to write
    """
    try:
        ctrl = _get_controller()
        ctrl.write_register(name, value)
        return {"status": "ok", "register": name, "value": value}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Tools — Monitor
# ---------------------------------------------------------------------------


@app.tool()
def factory_watch_tags(seconds: int = 10, interval_ms: int = 1000) -> dict[str, Any]:
    """Watch Factory IO tags for changes over a time period.

    Polls at the specified interval and returns a list of snapshots
    showing how tags changed over time. Useful for observing fault
    progression or verifying diagnosis response.

    Args:
        seconds: How long to watch (default 10s, max 60s)
        interval_ms: Poll interval in milliseconds (default 1000ms)
    """
    seconds = min(seconds, 60)
    interval = interval_ms / 1000.0
    snapshots = []

    try:
        ctrl = _get_controller()
        start = time.time()
        while time.time() - start < seconds:
            state = ctrl.read_all_state()
            snapshots.append({
                "t": round(time.time() - start, 2),
                "tags": state,
            })
            time.sleep(interval)

        return {
            "status": "ok",
            "duration_seconds": seconds,
            "snapshot_count": len(snapshots),
            "snapshots": snapshots,
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "snapshots": snapshots}


@app.tool()
def factory_connection_info() -> dict[str, Any]:
    """Show Factory IO connection configuration.

    Returns the Modbus host, port, and connection status.
    """
    from tools.fault_injector.config import PLC_HOST, MODBUS_PORT, MATRIX_API

    connected = False
    if _controller and _controller.client:
        try:
            connected = _controller.client.is_socket_open()
        except Exception:
            pass

    return {
        "plc_host": PLC_HOST,
        "modbus_port": MODBUS_PORT,
        "matrix_api": MATRIX_API,
        "connected": connected,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run()
