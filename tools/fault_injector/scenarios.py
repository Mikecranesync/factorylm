"""
Fault Scenarios
===============
Pre-defined fault scenarios for testing the FactoryLM diagnosis system.
"""

import time
import logging
from typing import Dict, Any, Callable, List
from dataclasses import dataclass

from .modbus_control import ModbusController
from .config import FAULT_HOLD_SECONDS

logger = logging.getLogger(__name__)


@dataclass
class FaultScenario:
    """Definition of a fault scenario."""
    name: str
    description: str
    inject_func: str  # Name of ModbusController method
    expected_diagnosis: str  # What Gus should say
    recovery_steps: List[str]  # Steps to fix
    hold_seconds: int = FAULT_HOLD_SECONDS


# ============================================================================
# Scenario Definitions
# ============================================================================

SCENARIOS: Dict[str, FaultScenario] = {
    "motor_overload": FaultScenario(
        name="Motor Overload",
        description="Motor drawing excessive current (12A vs 10A limit)",
        inject_func="inject_motor_overload",
        expected_diagnosis="Motor current too high. Check for mechanical binding or overload.",
        recovery_steps=[
            "Check for mechanical obstructions",
            "Verify motor bearings",
            "Check belt tension",
            "Reduce load or cycle time"
        ],
    ),

    "overheat": FaultScenario(
        name="Overheating",
        description="Temperature sensor reading 85C (limit is 80C)",
        inject_func="inject_overheat",
        expected_diagnosis="Temperature above safe operating range. Cooling system may have failed.",
        recovery_steps=[
            "Check cooling fans",
            "Verify air filters are clean",
            "Check ambient temperature",
            "Reduce duty cycle"
        ],
    ),

    "sensor_jam": FaultScenario(
        name="Sensor Jam / Conveyor Blockage",
        description="Sensor 1 blocked continuously - box stuck on conveyor",
        inject_func="inject_sensor_jam",
        expected_diagnosis="Conveyor jam detected. Sensor 1 continuously blocked.",
        recovery_steps=[
            "Clear jammed material from conveyor",
            "Check photo-eye alignment",
            "Inspect conveyor belt for damage",
            "Verify box dimensions within spec"
        ],
    ),

    "low_pressure": FaultScenario(
        name="Low Pressure",
        description="Pneumatic pressure dropped to 50 PSI (limit is 70 PSI)",
        inject_func="inject_low_pressure",
        expected_diagnosis="Low air pressure. Check compressor or air leaks.",
        recovery_steps=[
            "Check compressor operation",
            "Inspect air lines for leaks",
            "Verify regulator settings",
            "Check filter/dryer"
        ],
    ),

    "emergency_stop": FaultScenario(
        name="Emergency Stop",
        description="E-stop button pressed - all motion stopped",
        inject_func="inject_emergency_stop",
        expected_diagnosis="Emergency stop activated. All motion halted.",
        recovery_steps=[
            "Clear the hazard",
            "Reset E-stop button",
            "Perform safety check",
            "Restart sequence"
        ],
    ),

    "sensor_failure": FaultScenario(
        name="Sensor Failure",
        description="Both sensors showing offline/disconnected",
        inject_func="inject_sensor_failure",
        expected_diagnosis="Sensor communication lost. Check wiring or sensor power.",
        recovery_steps=[
            "Check sensor wiring",
            "Verify 24V power to sensors",
            "Inspect for damaged cables",
            "Replace faulty sensor"
        ],
    ),

    "normal": FaultScenario(
        name="Normal Operation",
        description="Clear all faults and run normally",
        inject_func="set_normal_operation",
        expected_diagnosis="All systems operating normally. No faults detected.",
        recovery_steps=[],
        hold_seconds=0,
    ),
}


def list_scenarios() -> List[Dict[str, str]]:
    """List all available scenarios."""
    return [
        {
            "id": key,
            "name": s.name,
            "description": s.description
        }
        for key, s in SCENARIOS.items()
    ]


def run_scenario(
    scenario_id: str,
    hold_seconds: int = None,
    callback: Callable[[str], None] = None
) -> Dict[str, Any]:
    """
    Run a fault scenario.

    Args:
        scenario_id: ID of the scenario to run
        hold_seconds: Override hold duration (default from scenario)
        callback: Optional callback for status updates

    Returns:
        Dict with scenario results
    """
    if scenario_id not in SCENARIOS:
        available = ", ".join(SCENARIOS.keys())
        raise ValueError(f"Unknown scenario '{scenario_id}'. Available: {available}")

    scenario = SCENARIOS[scenario_id]
    hold = hold_seconds if hold_seconds is not None else scenario.hold_seconds

    def log(msg):
        logger.info(msg)
        if callback:
            callback(msg)

    log(f"Starting scenario: {scenario.name}")
    log(f"Description: {scenario.description}")

    result = {
        "scenario": scenario_id,
        "name": scenario.name,
        "success": False,
        "state_before": None,
        "state_after": None,
    }

    try:
        with ModbusController() as modbus:
            # Capture state before
            result["state_before"] = modbus.read_all_state()
            log(f"State before: fault_alarm={result['state_before'].get('fault_alarm')}")

            # Inject the fault
            inject_method = getattr(modbus, scenario.inject_func)
            inject_method()
            log(f"Fault injected: {scenario.inject_func}")

            # Capture state after injection
            result["state_after"] = modbus.read_all_state()
            log(f"State after: fault_alarm={result['state_after'].get('fault_alarm')}, "
                f"error_code={result['state_after'].get('error_code')}")

            # Hold the fault state
            if hold > 0:
                log(f"Holding fault for {hold} seconds...")
                log(">>> Now test with Telegram: 'What's wrong with the equipment?'")
                time.sleep(hold)
                log("Hold complete")

            result["success"] = True
            result["expected_diagnosis"] = scenario.expected_diagnosis
            result["recovery_steps"] = scenario.recovery_steps

    except Exception as e:
        logger.error(f"Scenario failed: {e}")
        result["error"] = str(e)

    return result
