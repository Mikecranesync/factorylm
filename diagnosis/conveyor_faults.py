"""
Conveyor Fault Detection & Classification
==========================================
Maps PLC tags to fault conditions with technician-friendly explanations.

Designed for Allen-Bradley Micro820 + conveyor cell.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum


class FaultSeverity(Enum):
    INFO = "info"           # Normal operation note
    WARNING = "warning"     # Degraded but running
    CRITICAL = "critical"   # Stopped, needs attention
    EMERGENCY = "emergency" # E-stop or safety issue


@dataclass
class FaultDiagnosis:
    """Structured fault diagnosis for technician display."""
    fault_code: str
    severity: FaultSeverity
    title: str
    description: str
    likely_causes: List[str]
    suggested_checks: List[str]
    affected_tags: List[str]
    requires_maintenance: bool = False
    requires_safety_review: bool = False


# ============================================================================
# FAULT RULES: Tag patterns -> Fault diagnoses
# ============================================================================

def detect_faults(tags: Dict[str, Any]) -> List[FaultDiagnosis]:
    """
    Analyze PLC tags and return list of detected faults.

    Args:
        tags: Dict of PLC tag values (motor_running, fault_alarm, etc.)

    Returns:
        List of FaultDiagnosis objects, ordered by severity
    """
    faults = []

    # Extract tag values with defaults
    motor_running = bool(tags.get("motor_running", 0))
    motor_speed = int(tags.get("motor_speed", 0))
    motor_current = float(tags.get("motor_current", 0))
    temperature = float(tags.get("temperature", 0))
    pressure = int(tags.get("pressure", 0))
    conveyor_running = bool(tags.get("conveyor_running", 0))
    conveyor_speed = int(tags.get("conveyor_speed", 0))
    sensor_1 = bool(tags.get("sensor_1", 0))
    sensor_2 = bool(tags.get("sensor_2", 0))
    fault_alarm = bool(tags.get("fault_alarm", 0))
    e_stop = bool(tags.get("e_stop", 0))
    error_code = int(tags.get("error_code", 0))
    error_message = str(tags.get("error_message", ""))

    # -------------------------------------------------------------------------
    # EMERGENCY: E-Stop Pressed
    # -------------------------------------------------------------------------
    if e_stop:
        faults.append(FaultDiagnosis(
            fault_code="E001",
            severity=FaultSeverity.EMERGENCY,
            title="Emergency Stop Active",
            description="The emergency stop button has been pressed. All motion is halted.",
            likely_causes=[
                "Operator pressed E-stop button",
                "Safety interlock triggered",
                "Emergency condition detected"
            ],
            suggested_checks=[
                "Verify area is safe before reset",
                "Check for personnel in hazard zones",
                "Inspect equipment for damage",
                "Reset E-stop and clear faults in sequence"
            ],
            affected_tags=["e_stop", "motor_running", "conveyor_running"],
            requires_safety_review=True
        ))

    # -------------------------------------------------------------------------
    # CRITICAL: Motor Overload (High Current)
    # -------------------------------------------------------------------------
    if motor_running and motor_current > 5.0:
        faults.append(FaultDiagnosis(
            fault_code="M001",
            severity=FaultSeverity.CRITICAL,
            title="Motor Overcurrent",
            description=f"Motor current ({motor_current:.1f}A) exceeds safe limit (5.0A). Risk of thermal damage.",
            likely_causes=[
                "Mechanical binding or jam",
                "Bearing failure",
                "Belt tension too high",
                "Overloaded conveyor"
            ],
            suggested_checks=[
                "Check conveyor belt for jams or obstructions",
                "Inspect motor bearings for wear",
                "Verify belt tension is within spec",
                "Remove excess load from conveyor",
                "Check motor thermal overload relay"
            ],
            affected_tags=["motor_current", "motor_running"],
            requires_maintenance=True
        ))

    # -------------------------------------------------------------------------
    # CRITICAL: Overtemperature
    # -------------------------------------------------------------------------
    if temperature > 80.0:
        faults.append(FaultDiagnosis(
            fault_code="T001",
            severity=FaultSeverity.CRITICAL,
            title="High Temperature Alarm",
            description=f"Temperature ({temperature:.1f}C) exceeds safe limit (80C). Equipment at risk.",
            likely_causes=[
                "Cooling fan failure",
                "Blocked ventilation",
                "Ambient temperature too high",
                "Excessive motor load",
                "Bearing friction"
            ],
            suggested_checks=[
                "Check cooling fan operation",
                "Clear any blocked vents",
                "Verify ambient conditions",
                "Reduce motor load temporarily",
                "Allow cooldown before restart"
            ],
            affected_tags=["temperature"],
            requires_maintenance=True
        ))

    # -------------------------------------------------------------------------
    # CRITICAL: Conveyor Jam (Motor running but sensors stuck)
    # -------------------------------------------------------------------------
    if motor_running and conveyor_running and sensor_1 and sensor_2:
        # Both sensors active for extended period = jam
        faults.append(FaultDiagnosis(
            fault_code="C001",
            severity=FaultSeverity.CRITICAL,
            title="Conveyor Jam Detected",
            description="Both part sensors are active simultaneously. Product flow is blocked.",
            likely_causes=[
                "Product jam at transfer point",
                "Misaligned part on conveyor",
                "Sensor mounting shifted",
                "Accumulation backup from downstream"
            ],
            suggested_checks=[
                "Clear jammed product from conveyor",
                "Check downstream equipment status",
                "Verify sensor alignment",
                "Inspect guide rails for obstructions"
            ],
            affected_tags=["sensor_1", "sensor_2", "conveyor_running"],
            requires_maintenance=False
        ))

    # -------------------------------------------------------------------------
    # CRITICAL: Motor Stopped Unexpectedly
    # -------------------------------------------------------------------------
    if not motor_running and conveyor_speed > 0 and not e_stop:
        faults.append(FaultDiagnosis(
            fault_code="M002",
            severity=FaultSeverity.CRITICAL,
            title="Motor Stopped Unexpectedly",
            description="Motor has stopped but conveyor speed setpoint is non-zero. Possible fault.",
            likely_causes=[
                "Thermal overload tripped",
                "Motor contactor failure",
                "VFD fault",
                "Power loss to motor circuit"
            ],
            suggested_checks=[
                "Check motor starter/contactor",
                "Verify VFD status and fault codes",
                "Check thermal overload relay",
                "Verify power at motor terminals"
            ],
            affected_tags=["motor_running", "conveyor_speed"],
            requires_maintenance=True
        ))

    # -------------------------------------------------------------------------
    # WARNING: Low Pressure
    # -------------------------------------------------------------------------
    if pressure < 60 and motor_running:
        faults.append(FaultDiagnosis(
            fault_code="P001",
            severity=FaultSeverity.WARNING,
            title="Low Pneumatic Pressure",
            description=f"System pressure ({pressure} PSI) is below normal (60+ PSI). Actuators may not function properly.",
            likely_causes=[
                "Compressed air supply issue",
                "Air leak in pneumatic system",
                "Filter or regulator clogged",
                "Compressor not keeping up"
            ],
            suggested_checks=[
                "Check main air supply pressure",
                "Listen for air leaks",
                "Inspect air filter and regulator",
                "Verify compressor operation"
            ],
            affected_tags=["pressure"],
            requires_maintenance=False
        ))

    # -------------------------------------------------------------------------
    # WARNING: Motor Running Slow (Speed mismatch)
    # -------------------------------------------------------------------------
    if motor_running and motor_speed < 30 and conveyor_speed > 50:
        faults.append(FaultDiagnosis(
            fault_code="M003",
            severity=FaultSeverity.WARNING,
            title="Motor Speed Mismatch",
            description=f"Motor speed ({motor_speed}%) is lower than setpoint ({conveyor_speed}%). Possible slippage or load issue.",
            likely_causes=[
                "Belt slipping on pulleys",
                "Motor struggling under load",
                "VFD acceleration limited",
                "Mechanical resistance"
            ],
            suggested_checks=[
                "Check belt tension and condition",
                "Verify motor current is not excessive",
                "Check VFD parameters",
                "Inspect drive components"
            ],
            affected_tags=["motor_speed", "conveyor_speed"],
            requires_maintenance=False
        ))

    # -------------------------------------------------------------------------
    # WARNING: Elevated Temperature
    # -------------------------------------------------------------------------
    if 65.0 < temperature <= 80.0:
        faults.append(FaultDiagnosis(
            fault_code="T002",
            severity=FaultSeverity.WARNING,
            title="Elevated Temperature",
            description=f"Temperature ({temperature:.1f}C) is above normal (65C). Monitor closely.",
            likely_causes=[
                "Heavy continuous operation",
                "Reduced cooling efficiency",
                "Increasing bearing wear"
            ],
            suggested_checks=[
                "Monitor temperature trend",
                "Ensure cooling is adequate",
                "Plan maintenance window if trend continues"
            ],
            affected_tags=["temperature"],
            requires_maintenance=False
        ))

    # -------------------------------------------------------------------------
    # WARNING: Generic Fault Alarm (from PLC)
    # -------------------------------------------------------------------------
    if fault_alarm and error_code > 0:
        faults.append(FaultDiagnosis(
            fault_code=f"PLC{error_code:03d}",
            severity=FaultSeverity.CRITICAL,
            title=f"PLC Fault: {error_message or f'Error Code {error_code}'}",
            description=f"The PLC has reported fault code {error_code}. Check PLC diagnostics for details.",
            likely_causes=[
                "See PLC fault documentation",
                "Check recent operations before fault"
            ],
            suggested_checks=[
                "Review PLC fault log",
                "Check associated I/O points",
                "Verify sensor and actuator operation"
            ],
            affected_tags=["fault_alarm", "error_code"],
            requires_maintenance=True
        ))

    # -------------------------------------------------------------------------
    # INFO: Normal Operation
    # -------------------------------------------------------------------------
    if not faults:
        # No faults detected - system is healthy
        if motor_running and conveyor_running:
            faults.append(FaultDiagnosis(
                fault_code="OK",
                severity=FaultSeverity.INFO,
                title="System Running Normally",
                description="All monitored parameters are within normal ranges.",
                likely_causes=[],
                suggested_checks=[],
                affected_tags=[]
            ))
        elif not motor_running and not conveyor_running:
            faults.append(FaultDiagnosis(
                fault_code="IDLE",
                severity=FaultSeverity.INFO,
                title="System Idle",
                description="Equipment is stopped. Ready to start when commanded.",
                likely_causes=[],
                suggested_checks=[],
                affected_tags=[]
            ))

    # Sort by severity (emergency first, info last)
    severity_order = {
        FaultSeverity.EMERGENCY: 0,
        FaultSeverity.CRITICAL: 1,
        FaultSeverity.WARNING: 2,
        FaultSeverity.INFO: 3
    }
    faults.sort(key=lambda f: severity_order[f.severity])

    return faults


def format_diagnosis_for_technician(diagnosis: FaultDiagnosis) -> str:
    """Format a fault diagnosis as plain text for display."""
    lines = [
        f"[{diagnosis.severity.value.upper()}] {diagnosis.fault_code}: {diagnosis.title}",
        "",
        diagnosis.description,
    ]

    if diagnosis.likely_causes:
        lines.append("")
        lines.append("Likely Causes:")
        for cause in diagnosis.likely_causes:
            lines.append(f"  - {cause}")

    if diagnosis.suggested_checks:
        lines.append("")
        lines.append("Suggested Checks:")
        for i, check in enumerate(diagnosis.suggested_checks, 1):
            lines.append(f"  {i}. {check}")

    if diagnosis.requires_safety_review:
        lines.append("")
        lines.append("SAFETY: Requires safety review before restart")

    if diagnosis.requires_maintenance:
        lines.append("")
        lines.append("NOTE: Consider creating maintenance work order")

    return "\n".join(lines)


# ============================================================================
# Quick test
# ============================================================================

if __name__ == "__main__":
    # Test with sample fault condition
    test_tags = {
        "motor_running": True,
        "motor_speed": 60,
        "motor_current": 6.5,  # Overcurrent!
        "temperature": 72,     # Elevated
        "pressure": 55,        # Low
        "conveyor_running": True,
        "conveyor_speed": 50,
        "sensor_1": False,
        "sensor_2": False,
        "fault_alarm": False,
        "e_stop": False,
        "error_code": 0,
        "error_message": ""
    }

    print("=" * 60)
    print("FAULT DETECTION TEST")
    print("=" * 60)

    faults = detect_faults(test_tags)
    for fault in faults:
        print()
        print(format_diagnosis_for_technician(fault))
        print("-" * 40)
