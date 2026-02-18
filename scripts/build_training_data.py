"""
Build training dataset for fine-tuning Cosmos Reason 2-2B on factory fault video.

Generates LLaVA-style annotation JSON and JSONL for cosmos-rl SFT training.

Usage:
    python scripts/build_training_data.py --from-clips        # From existing video files
    python scripts/build_training_data.py --generate-synthetic # Without real videos
"""

import argparse
import json
import random
import sys
import tempfile
from pathlib import Path

# Ensure repo root is importable
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from sim.plc_simulator import PLCSimulator  # noqa: E402

# ---------------------------------------------------------------------------
# Fault type definitions
# ---------------------------------------------------------------------------

FAULT_TYPES = {
    "normal":   {"error_code": 0, "fault_name": None},
    "overload": {"error_code": 1, "fault_name": "overload"},
    "overheat": {"error_code": 2, "fault_name": "overheat"},
    "jam":      {"error_code": 3, "fault_name": "jam"},
    "sensor":   {"error_code": 4, "fault_name": "sensor"},
    "estop":    {"error_code": 5, "fault_name": "estop"},
}

SYNTHETIC_COUNTS = {
    "normal":   20,
    "overload": 20,
    "overheat": 20,
    "jam":      30,
    "sensor":   20,
    "estop":    15,
}

SYSTEM_PROMPT = (
    "You are an expert industrial equipment fault diagnostician for a factory floor. "
    "You analyze video feeds from Factory I/O conveyor systems alongside real-time PLC "
    "sensor data (Modbus TCP from Allen-Bradley Micro 820) to diagnose equipment faults. "
    "Always provide structured JSON responses with: summary, root_cause, confidence (0-1), "
    "reasoning, and suggested_checks."
)

# ---------------------------------------------------------------------------
# Response templates — varied per fault type
# ---------------------------------------------------------------------------

RESPONSE_TEMPLATES: dict[int, list[dict]] = {
    0: [
        {
            "summary": "No active fault detected. System operating within normal parameters.",
            "root_cause": "N/A — no fault present",
            "confidence": 0.95,
            "reasoning": "All tag values within expected ranges. Motor current, temperature, and pressure readings are nominal.",
            "suggested_checks": ["Continue normal monitoring"],
        },
        {
            "summary": "Normal operation confirmed. Conveyor and motor running at standard setpoints.",
            "root_cause": "N/A — system healthy",
            "confidence": 0.97,
            "reasoning": "Motor current proportional to speed setpoint, temperature stable below 45°C, sensors cycling normally as parts pass.",
            "suggested_checks": ["Log baseline values for trend analysis"],
        },
        {
            "summary": "System in steady-state. No anomalies detected in any monitored parameter.",
            "root_cause": "N/A — all clear",
            "confidence": 0.93,
            "reasoning": "Pressure within 90-110 range, conveyor speed matches setpoint, photoeye sensors toggling as expected with part flow.",
            "suggested_checks": ["Schedule routine preventive maintenance per calendar"],
        },
        {
            "summary": "Equipment running nominally. All sensors and actuators responding correctly.",
            "root_cause": "N/A — no fault condition",
            "confidence": 0.96,
            "reasoning": "Motor draw consistent with load, temperature trending flat, no fault alarms active. Belt tracking appears centered.",
            "suggested_checks": ["Verify lubrication schedule is current", "Check belt wear at next planned stop"],
        },
    ],
    1: [
        {
            "summary": "Motor overload detected. Current draw exceeds rated capacity.",
            "root_cause": "Mechanical binding or excessive load on motor shaft",
            "confidence": 0.82,
            "reasoning": "Motor current at {motor_current}A exceeds expected range for speed {motor_speed}%. This pattern is consistent with mechanical resistance — either a jammed workpiece or bearing degradation.",
            "suggested_checks": [
                "Inspect motor shaft for mechanical binding",
                "Check conveyor belt alignment and tension",
                "Verify motor bearings with vibration analysis",
                "Review motor nameplate amps vs. measured current",
            ],
        },
        {
            "summary": "Overload condition on conveyor drive motor. Current spike detected.",
            "root_cause": "Excessive mechanical load — possible belt misalignment or product accumulation",
            "confidence": 0.85,
            "reasoning": "Current reading of {motor_current}A at {motor_speed}% speed indicates approximately 2x normal draw. Sustained overload will trip the overload relay within minutes.",
            "suggested_checks": [
                "Reduce motor speed to 40% and observe current",
                "Check for product pile-up at diverter gate",
                "Inspect drive chain/belt for damage",
                "Measure motor winding resistance",
            ],
        },
        {
            "summary": "Motor drawing excessive current. Overload fault active.",
            "root_cause": "Increased friction in drive train or seized bearing",
            "confidence": 0.79,
            "reasoning": "At {motor_speed}% speed, expected current is ~{expected_current}A but measured {motor_current}A. Delta suggests significant added resistance in the mechanical path.",
            "suggested_checks": [
                "Check gearbox oil level and condition",
                "Listen for abnormal motor noise (grinding, clicking)",
                "Verify VFD parameters match motor nameplate",
                "Thermal scan motor housing and bearings",
            ],
        },
    ],
    2: [
        {
            "summary": "High temperature alarm. Process temperature exceeding safe threshold.",
            "root_cause": "Insufficient cooling or sustained high-load operation",
            "confidence": 0.78,
            "reasoning": "Temperature reading at {temperature}°C. Thermal runaway pattern suggests cooling system degradation or ambient temperature exceeding design limits.",
            "suggested_checks": [
                "Check cooling fan operation",
                "Inspect air filters for blockage",
                "Verify ambient temperature in enclosure",
                "Check thermal paste on heat sinks",
            ],
        },
        {
            "summary": "Temperature rising above safe operating limits. Overheat condition detected.",
            "root_cause": "Blocked ventilation or cooling fan failure",
            "confidence": 0.81,
            "reasoning": "Temperature at {temperature}°C with upward trend. Normal operating range is 25-45°C. Rate of rise suggests active heat source with no effective cooling.",
            "suggested_checks": [
                "Confirm cooling fan is spinning at rated RPM",
                "Check enclosure door seals for gaps allowing hot air ingress",
                "Verify thermocouple calibration",
                "Reduce motor load until temperature stabilizes",
            ],
        },
        {
            "summary": "Thermal alarm triggered. Equipment temperature {temperature}°C exceeds 60°C threshold.",
            "root_cause": "Motor overwork combined with reduced airflow",
            "confidence": 0.76,
            "reasoning": "Temperature exceeds alarm setpoint. Motor current is within range, suggesting the heat source may be external (ambient) or due to restricted airflow rather than electrical overload.",
            "suggested_checks": [
                "Clean cabinet air filters immediately",
                "Check for obstructions around ventilation openings",
                "Inspect motor cooling fins for dust buildup",
                "Consider temporary auxiliary cooling",
            ],
        },
    ],
    3: [
        {
            "summary": "Conveyor jam detected. Material flow interrupted.",
            "root_cause": "Physical obstruction in conveyor path",
            "confidence": 0.88,
            "reasoning": "Conveyor motor drawing current but photoeye sensors show sustained blockage. Belt speed has dropped to zero while motor remains energized — classic jam signature.",
            "suggested_checks": [
                "Clear jammed material from conveyor path",
                "Inspect photoeye sensors for alignment",
                "Check conveyor belt tracking",
                "Verify guide rail spacing",
            ],
        },
        {
            "summary": "Conveyor belt stalled. Jam condition confirmed by sensor and current data.",
            "root_cause": "Product wedged between guide rails and belt surface",
            "confidence": 0.91,
            "reasoning": "Belt speed reads 0 while motor current is elevated at {motor_current}A, indicating the motor is stalled against a fixed obstruction. Sensor_1 stuck TRUE confirms product is stationary at photoeye location.",
            "suggested_checks": [
                "Lockout/tagout before clearing jam",
                "Remove wedged product carefully",
                "Check guide rail width — may need adjustment",
                "Inspect belt surface for damage from jam",
            ],
        },
        {
            "summary": "Material jam on sorting conveyor. Zero belt speed with elevated motor draw.",
            "root_cause": "Misaligned or oversized product causing blockage at sorting gate",
            "confidence": 0.86,
            "reasoning": "Speed = 0 with sensor_1 latched TRUE indicates a stationary object blocking the photoeye. Motor current at {motor_current}A shows the drive is attempting to push through the obstruction.",
            "suggested_checks": [
                "Check diverter gate position and clearance",
                "Verify incoming product dimensions are within spec",
                "Inspect belt splice for separation",
                "Review jam frequency — recurring jams indicate systemic issue",
            ],
        },
        {
            "summary": "Jam fault active. Conveyor motion halted by physical obstruction.",
            "root_cause": "Accumulated debris or fallen product on belt path",
            "confidence": 0.84,
            "reasoning": "Conveyor speed dropped to zero abruptly. Photoeye remains blocked. Motor current spike to {motor_current}A suggests sudden stop rather than gradual slowdown.",
            "suggested_checks": [
                "Visually inspect full conveyor length for debris",
                "Clear obstruction and jog belt in manual mode",
                "Check product spacing — insufficient gaps cause pile-ups",
                "Adjust upstream feed rate to prevent recurrence",
            ],
        },
    ],
    4: [
        {
            "summary": "Sensor failure detected. One or more sensors not responding.",
            "root_cause": "Sensor wiring fault or component failure",
            "confidence": 0.72,
            "reasoning": "Sensor readings show flat-line or erratic values inconsistent with physical process state. Likely a wiring issue or end-of-life sensor.",
            "suggested_checks": [
                "Check sensor wiring connections",
                "Verify sensor supply voltage",
                "Test sensor with known target",
                "Replace sensor if beyond calibration",
            ],
        },
        {
            "summary": "Erratic sensor data detected. Readings inconsistent with process state.",
            "root_cause": "Intermittent wiring connection or electromagnetic interference",
            "confidence": 0.69,
            "reasoning": "Sensor values are fluctuating rapidly without corresponding physical changes. Pattern suggests loose connection or EMI from nearby VFD.",
            "suggested_checks": [
                "Tighten all sensor terminal connections",
                "Route sensor cables away from power conductors",
                "Add shielded cable or ferrite cores",
                "Check sensor output with oscilloscope",
            ],
        },
        {
            "summary": "Sensor reading flatlined. No state changes detected despite active process.",
            "root_cause": "Sensor lens contamination or failed output transistor",
            "confidence": 0.74,
            "reasoning": "Sensor output is stuck in one state while conveyor is confirmed running. Physical inspection of sensor is required to differentiate between dirty lens and hardware failure.",
            "suggested_checks": [
                "Clean sensor lens with approved cleaner",
                "Check indicator LED on sensor body",
                "Swap sensor with known good unit",
                "Verify PLC input module channel is functional",
            ],
        },
    ],
    5: [
        {
            "summary": "Emergency stop activated. All motion ceased.",
            "root_cause": "E-stop button pressed — manual safety intervention",
            "confidence": 0.92,
            "reasoning": "E-stop input is TRUE, all motor and conveyor outputs are de-energized. This is a deliberate operator action, not an equipment fault.",
            "suggested_checks": [
                "Identify which e-stop station was activated",
                "Investigate reason for emergency stop",
                "Inspect area for hazards before resetting",
                "Follow lockout/tagout procedure before restart",
            ],
        },
        {
            "summary": "E-stop engaged. System in safe shutdown state.",
            "root_cause": "Operator-initiated emergency stop",
            "confidence": 0.94,
            "reasoning": "All outputs are off, e_stop flag is TRUE. No preceding fault alarms were active, suggesting this was a precautionary stop rather than a response to equipment failure.",
            "suggested_checks": [
                "Confirm all personnel are clear of equipment",
                "Check e-stop circuit for proper reset capability",
                "Document reason for stop in shift log",
                "Perform walk-around inspection before restart",
            ],
        },
        {
            "summary": "Emergency stop active. Complete system halt in effect.",
            "root_cause": "Safety circuit opened — e-stop or safety gate",
            "confidence": 0.89,
            "reasoning": "Motor and conveyor both de-energized simultaneously, consistent with safety circuit interruption. E-stop TRUE confirms the safety chain is open.",
            "suggested_checks": [
                "Check all e-stop buttons for latched state",
                "Verify safety gate interlocks are closed",
                "Test e-stop reset procedure",
                "Confirm safety relay is ready for reset",
            ],
        },
    ],
}


# ---------------------------------------------------------------------------
# ANSI colours
# ---------------------------------------------------------------------------

class _C:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def _step(n: int, msg: str) -> None:
    print(f"{_C.CYAN}{_C.BOLD}[{n}]{_C.RESET} {msg}")


# ---------------------------------------------------------------------------
# Tag snapshot generation using PLCSimulator
# ---------------------------------------------------------------------------

def _generate_tags(fault_type: str, sim: PLCSimulator) -> dict:
    """Reset the simulator, inject a fault, tick a few times, and return a tag dict."""
    # Reset to clean state
    sim.inject_fault("release")
    sim.inject_fault("clear")

    # Randomise baseline values for variety
    sim.motor_speed = random.randint(45, 75)
    sim.conveyor_speed = random.randint(40, 60)
    sim.temperature = round(random.uniform(24.0, 38.0), 1)
    sim.pressure = random.randint(95, 108)

    # Inject the fault
    fault_name = FAULT_TYPES[fault_type]["fault_name"]
    if fault_name:
        sim.inject_fault(fault_name)

    # Tick a few times to let values settle
    ticks = random.randint(3, 8)
    for _ in range(ticks):
        snap = sim.tick()

    # For estop, error_code from simulator is 5 (comms) but we want 5 for e-stop.
    # The simulator sets error_code via FAULT_MAP; estop goes through a different path.
    # Build the tag dict from the snapshot.
    d = snap.to_dict()

    # Apply additional variation per fault type that the simulator doesn't cover
    if fault_type == "overload":
        d["motor_current"] = round(random.uniform(7.0, 12.0), 2)
    elif fault_type == "overheat":
        d["temperature"] = round(random.uniform(65.0, 95.0), 1)
    elif fault_type == "sensor":
        # Erratic sensor: randomly flip or flatline
        d["sensor_1"] = random.choice([True, False])
        d["sensor_2"] = random.choice([True, False])
        d["error_code"] = 4
        d["fault_alarm"] = True
        d["error_message"] = "Sensor failure"
    elif fault_type == "estop":
        d["e_stop"] = True
        d["motor_running"] = False
        d["conveyor_running"] = False
        d["conveyor_speed"] = 0
        d["motor_speed"] = 0
        d["motor_current"] = 0.0
        d["fault_alarm"] = True
        d["error_code"] = 5
        d["error_message"] = "E-stop activated"

    # Return a compact subset used in the prompt
    return {
        "motor_running": d["motor_running"],
        "motor_speed": d["motor_speed"],
        "motor_current": d["motor_current"],
        "temperature": d["temperature"],
        "pressure": d["pressure"],
        "conveyor_running": d["conveyor_running"],
        "conveyor_speed": d["conveyor_speed"],
        "sensor_1": d["sensor_1"],
        "sensor_2": d["sensor_2"],
        "fault_alarm": d["fault_alarm"],
        "e_stop": d["e_stop"],
        "error_code": d["error_code"],
    }


# ---------------------------------------------------------------------------
# Response generation with variation
# ---------------------------------------------------------------------------

def _build_response(fault_type: str, tags: dict) -> dict:
    """Pick a response template and fill in tag-specific values."""
    error_code = FAULT_TYPES[fault_type]["error_code"]
    templates = RESPONSE_TEMPLATES[error_code]
    template = random.choice(templates)

    # Deep copy so we don't mutate the template
    resp = {k: v if not isinstance(v, list) else list(v) for k, v in template.items()}

    # Add variation to confidence
    base_conf = resp["confidence"]
    resp["confidence"] = round(max(0.50, min(0.99, base_conf + random.uniform(-0.06, 0.06))), 2)

    # Format reasoning string with tag values
    fmt_vals = {
        "motor_current": tags.get("motor_current", "N/A"),
        "motor_speed": tags.get("motor_speed", "N/A"),
        "temperature": tags.get("temperature", "N/A"),
        "expected_current": round(tags.get("motor_speed", 60) * 0.05, 1),
    }
    if isinstance(resp["reasoning"], str):
        resp["reasoning"] = resp["reasoning"].format_map(
            {k: v for k, v in fmt_vals.items()}
            | {k: v for k, v in fmt_vals.items()}  # defaultdict fallback not needed; all keys present
        )
    if isinstance(resp["summary"], str):
        resp["summary"] = resp["summary"].format_map(fmt_vals)

    return resp


# ---------------------------------------------------------------------------
# Conversation builder
# ---------------------------------------------------------------------------

def _build_conversation(video_path: str, tags: dict, response: dict) -> dict:
    """Build a single LLaVA-style conversation entry."""
    tag_str = json.dumps(tags)
    user_msg = (
        "<video>\n"
        f"Analyze this factory floor video along with the PLC sensor data. "
        f"Equipment Node: factoryio-sim. Current Tags: {tag_str}. "
        f"Provide a structured diagnosis including: summary, root_cause, "
        f"confidence (0-1), reasoning, and suggested_checks."
    )
    gpt_msg = json.dumps(response)

    return {
        "video": video_path,
        "conversations": [
            {"from": "human", "value": user_msg},
            {"from": "gpt", "value": gpt_msg},
        ],
    }


# ---------------------------------------------------------------------------
# Mode: --from-clips
# ---------------------------------------------------------------------------

def build_from_clips(clips_dir: Path, sim: PLCSimulator) -> list[dict]:
    """Scan clips_dir for video files and build annotations from filenames."""
    entries: list[dict] = []
    extensions = {".mp4", ".webm", ".mov", ".avi"}

    if not clips_dir.exists():
        print(f"{_C.YELLOW}Warning: {clips_dir} does not exist. No clips found.{_C.RESET}")
        return entries

    files = sorted(p for p in clips_dir.iterdir() if p.suffix.lower() in extensions)
    if not files:
        print(f"{_C.YELLOW}Warning: No video files found in {clips_dir}{_C.RESET}")
        return entries

    for vf in files:
        stem = vf.stem.lower()
        # Infer fault type from filename prefix (e.g. jam_001, normal_005)
        fault_type = None
        for ft in FAULT_TYPES:
            if stem.startswith(ft):
                fault_type = ft
                break
        if fault_type is None:
            print(f"  Skipping {vf.name} — cannot infer fault type from filename")
            continue

        rel_path = f"clips/{vf.name}"
        tags = _generate_tags(fault_type, sim)
        response = _build_response(fault_type, tags)
        entries.append(_build_conversation(rel_path, tags, response))

    return entries


# ---------------------------------------------------------------------------
# Mode: --generate-synthetic
# ---------------------------------------------------------------------------

def build_synthetic(sim: PLCSimulator) -> list[dict]:
    """Generate synthetic annotation entries without real video files."""
    entries: list[dict] = []

    for fault_type, count in SYNTHETIC_COUNTS.items():
        for i in range(1, count + 1):
            filename = f"clips/{fault_type}_{i:03d}.mp4"
            tags = _generate_tags(fault_type, sim)
            response = _build_response(fault_type, tags)
            entries.append(_build_conversation(filename, tags, response))

    random.shuffle(entries)
    return entries


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_outputs(entries: list[dict], output_dir: Path) -> tuple[Path, Path]:
    """Write annotations.json and train.jsonl, return their paths."""
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "annotations.json"
    jsonl_path = output_dir / "train.jsonl"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)

    with jsonl_path.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")

    return json_path, jsonl_path


# ---------------------------------------------------------------------------
# TOML config writer
# ---------------------------------------------------------------------------

SFT_TOML = """\
redis = "12800"

[custom.dataset]
annotation_path = "/workspace/factorylm/data/training/annotations.json"
media_path = "/workspace/factorylm/data/training"
system_prompt = "You are an expert industrial equipment fault diagnostician for a factory floor. You analyze video feeds from Factory I/O conveyor systems alongside real-time PLC sensor data (Modbus TCP from Allen-Bradley Micro 820) to diagnose equipment faults. Always provide structured JSON responses with: summary, root_cause, confidence (0-1), reasoning, and suggested_checks."

[train]
output_dir = "/workspace/cosmos-reason2/outputs/factory_sft"
compile = false
train_batch_per_replica = 4

[policy]
model_name_or_path = "nvidia/Cosmos-Reason2-2B"
model_max_length = 4096

[logging]
logger = ['console', 'wandb']
project_name = "cosmos-factory"
experiment_name = "factory-fault-sft-v1"

[train.train_policy]
type = "sft"
mini_batch = 2

[train.ckpt]
enable_checkpoint = true

[policy.parallelism]
tp_size = 1
cp_size = 1
dp_shard_size = 1
pp_size = 1
"""


def write_toml(config_dir: Path) -> Path:
    """Write the SFT TOML config file."""
    config_dir.mkdir(parents=True, exist_ok=True)
    toml_path = config_dir / "factory_sft.toml"
    toml_path.write_text(SFT_TOML, encoding="utf-8")
    return toml_path


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def print_summary(entries: list[dict], json_path: Path, jsonl_path: Path, toml_path: Path) -> None:
    """Print a coloured summary of what was generated."""
    # Count per fault type
    counts: dict[str, int] = {}
    for entry in entries:
        video = entry["video"]
        stem = Path(video).stem.lower()
        for ft in FAULT_TYPES:
            if stem.startswith(ft):
                counts[ft] = counts.get(ft, 0) + 1
                break

    print()
    print(f"{_C.GREEN}{_C.BOLD}=== Training Data Summary ==={_C.RESET}")
    for ft in FAULT_TYPES:
        c = counts.get(ft, 0)
        error_code = FAULT_TYPES[ft]["error_code"]
        print(f"  {ft:<10s}  (error_code={error_code})  {c:>4d} samples")
    print(f"  {'-' * 38}")
    print(f"  {'TOTAL':<10s}                   {len(entries):>4d} samples")
    print()
    print(f"{_C.GREEN}Output files:{_C.RESET}")
    print(f"  {json_path}")
    print(f"  {jsonl_path}")
    print(f"  {toml_path}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build training dataset for Cosmos Reason 2-2B factory fault fine-tuning.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--from-clips",
        action="store_true",
        help="Scan data/training/clips/ for existing video files and build annotations.",
    )
    mode.add_argument(
        "--generate-synthetic",
        action="store_true",
        help="Generate ~125 synthetic annotation entries without real video files.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory (default: data/training/ under repo root).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42).",
    )
    args = parser.parse_args()

    random.seed(args.seed)

    output_dir = Path(args.output_dir) if args.output_dir else REPO_ROOT / "data" / "training"
    clips_dir = output_dir / "clips"
    config_dir = REPO_ROOT / "config"

    # Create simulator with a temp DB so we don't pollute sim/tags.db
    _step(1, "Initialising PLC simulator")
    _tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    _tmp_db.close()
    sim = PLCSimulator(db_path=_tmp_db.name)

    # Build entries
    if args.from_clips:
        _step(2, f"Scanning {clips_dir} for video files")
        entries = build_from_clips(clips_dir, sim)
    else:
        _step(2, "Generating synthetic training entries")
        entries = build_synthetic(sim)

    if not entries:
        print(f"{_C.YELLOW}No entries generated. Exiting.{_C.RESET}")
        sys.exit(1)

    # Write outputs
    _step(3, f"Writing annotation files to {output_dir}")
    json_path, jsonl_path = write_outputs(entries, output_dir)

    _step(4, f"Writing SFT config to {config_dir / 'factory_sft.toml'}")
    toml_path = write_toml(config_dir)

    _step(5, "Done!")
    print_summary(entries, json_path, jsonl_path, toml_path)


if __name__ == "__main__":
    main()
