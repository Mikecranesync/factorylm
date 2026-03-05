#!/usr/bin/env python3
"""
FactoryLM Vision — Cosmos R2 Diagnosis Engine
==============================================
Orchestrates video/image + PLC registers → Cosmos R2 prompt → diagnosis.

Usage:
    # Diagnose from an image (no PLC data)
    python cookoff/diagnosis_engine.py --image cookoff/clips/screenshot.png

    # Diagnose with PLC register snapshot
    python cookoff/diagnosis_engine.py --image cookoff/clips/screenshot.png --plc-json plc_snapshot.json

    # Diagnose with simulated PLC data (for testing without hardware)
    python cookoff/diagnosis_engine.py --image cookoff/clips/screenshot.png --simulate-plc jam

    # Ask a specific question
    python cookoff/diagnosis_engine.py --image cookoff/clips/screenshot.png --question "Is the conveyor running?"

    # Use video instead of image
    python cookoff/diagnosis_engine.py --video cookoff/clips/normal_20260219.mp4

Environment:
    VLLM_URL  - vLLM endpoint (default: http://localhost:8000/v1/chat/completions)
"""

import argparse
import base64
import io
import json
import os
import sys
import time

# Fix Windows console encoding for Unicode output from R2
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
from pathlib import Path
from typing import Optional

import requests
import yaml

# Add repo root to path
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from diagnosis.conveyor_faults import detect_faults, format_diagnosis_for_technician

# --- Configuration ---
VLLM_URL = os.environ.get("VLLM_URL", "http://localhost:8000/v1/chat/completions")
MODEL_NAME = "nvidia/Cosmos-Reason2-8B"
PROMPTS_PATH = REPO_ROOT / "cookoff" / "prompts" / "factory_diagnosis.yaml"

# Cosmos R2 recommended sampling for reasoning mode
DEFAULT_TEMPERATURE = 0.6
DEFAULT_TOP_P = 0.95
DEFAULT_MAX_TOKENS = 4096  # Long enough for chain-of-thought


def load_prompts() -> dict:
    """Load prompt templates from YAML."""
    with open(PROMPTS_PATH) as f:
        return yaml.safe_load(f)


def encode_media(path: str) -> tuple[str, str]:
    """Encode image or video as base64 with MIME type."""
    ext = Path(path).suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".mp4": "video/mp4",
        ".avi": "video/x-msvideo",
        ".webm": "video/webm",
    }
    mime = mime_map.get(ext, "image/jpeg")
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return b64, mime


def format_plc_registers(tags: dict) -> str:
    """Format PLC tag dict as readable text for R2 prompt."""
    lines = []
    # Booleans first
    bool_tags = {k: v for k, v in tags.items() if isinstance(v, bool)}
    num_tags = {k: v for k, v in tags.items() if not isinstance(v, bool)}

    if bool_tags:
        lines.append("Digital I/O:")
        for k, v in sorted(bool_tags.items()):
            status = "ON" if v else "OFF"
            lines.append(f"  {k}: {status}")

    if num_tags:
        lines.append("Analog Registers:")
        for k, v in sorted(num_tags.items()):
            if isinstance(v, float):
                lines.append(f"  {k}: {v:.1f}")
            else:
                lines.append(f"  {k}: {v}")

    return "\n".join(lines) if lines else "No PLC data available"


def format_fault_analysis(tags: dict) -> str:
    """Run fault detection and format results."""
    faults = detect_faults(tags)
    if not faults:
        return "No automated faults detected."
    return "\n\n".join(format_diagnosis_for_technician(f) for f in faults)


# --- Simulated PLC Scenarios ---
SIMULATED_SCENARIOS = {
    "normal": {
        "motor_running": True,
        "motor_stopped": False,
        "motor_speed": 65,
        "motor_current": 2.3,
        "temperature": 42.0,
        "pressure": 78,
        "conveyor_running": True,
        "conveyor_speed": 50,
        "sensor_1_active": False,
        "sensor_2_active": False,
        "fault_alarm": False,
        "e_stop_active": False,
        "error_code": 0,
    },
    "jam": {
        "motor_running": True,
        "motor_stopped": False,
        "motor_speed": 45,
        "motor_current": 5.8,
        "temperature": 68.0,
        "pressure": 72,
        "conveyor_running": True,
        "conveyor_speed": 50,
        "sensor_1_active": True,
        "sensor_2_active": True,
        "fault_alarm": True,
        "e_stop_active": False,
        "error_code": 3,
    },
    "estop": {
        "motor_running": False,
        "motor_stopped": True,
        "motor_speed": 0,
        "motor_current": 0.0,
        "temperature": 55.0,
        "pressure": 75,
        "conveyor_running": False,
        "conveyor_speed": 0,
        "sensor_1_active": False,
        "sensor_2_active": False,
        "fault_alarm": True,
        "e_stop_active": True,
        "error_code": 0,
    },
    "idle": {
        "motor_running": False,
        "motor_stopped": True,
        "motor_speed": 0,
        "motor_current": 0.0,
        "temperature": 25.0,
        "pressure": 80,
        "conveyor_running": False,
        "conveyor_speed": 0,
        "sensor_1_active": False,
        "sensor_2_active": False,
        "fault_alarm": False,
        "e_stop_active": False,
        "error_code": 0,
    },
    "overheat": {
        "motor_running": True,
        "motor_stopped": False,
        "motor_speed": 80,
        "motor_current": 4.5,
        "temperature": 85.0,
        "pressure": 70,
        "conveyor_running": True,
        "conveyor_speed": 80,
        "sensor_1_active": False,
        "sensor_2_active": False,
        "fault_alarm": True,
        "e_stop_active": False,
        "error_code": 2,
    },
}


def diagnose(
    media_path: str,
    plc_tags: Optional[dict] = None,
    question: Optional[str] = None,
    vllm_url: str = VLLM_URL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict:
    """Run a Cosmos R2 diagnosis on a factory image/video with optional PLC data.

    Returns:
        dict with keys: reasoning, diagnosis, raw_response, usage, elapsed_s
    """
    prompts = load_prompts()
    system_prompt = prompts["system"]

    # Build user prompt
    if plc_tags and question:
        user_template = prompts["user_question"]
        user_prompt = user_template.format(
            plc_registers=format_plc_registers(plc_tags),
            fault_analysis=format_fault_analysis(plc_tags),
            user_question=question,
        )
    elif plc_tags:
        user_template = prompts["user_diagnosis"]
        user_prompt = user_template.format(
            plc_registers=format_plc_registers(plc_tags),
            fault_analysis=format_fault_analysis(plc_tags),
        )
    else:
        user_prompt = prompts["user_describe"]

    # Build message content (media first, then text — per R2 docs)
    b64, mime = encode_media(media_path)

    if mime.startswith("video"):
        media_content = {
            "type": "video_url",
            "video_url": {"url": f"data:{mime};base64,{b64}"},
        }
    else:
        media_content = {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"},
        }

    user_content = [media_content, {"type": "text", "text": user_prompt}]

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": max_tokens,
        "temperature": DEFAULT_TEMPERATURE,
        "top_p": DEFAULT_TOP_P,
    }

    # Call vLLM
    t_start = time.time()
    response = requests.post(
        vllm_url,
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=300,
    )
    elapsed = time.time() - t_start

    if response.status_code != 200:
        return {
            "error": f"HTTP {response.status_code}: {response.text[:500]}",
            "elapsed_s": elapsed,
        }

    data = response.json()
    content = data["choices"][0]["message"]["content"]

    # Parse <think> blocks
    reasoning = ""
    diagnosis_text = content
    if "<think>" in content and "</think>" in content:
        think_start = content.index("<think>") + len("<think>")
        think_end = content.index("</think>")
        reasoning = content[think_start:think_end].strip()
        diagnosis_text = content[think_end + len("</think>"):].strip()

    return {
        "reasoning": reasoning,
        "diagnosis": diagnosis_text,
        "raw_response": content,
        "usage": data.get("usage", {}),
        "elapsed_s": round(elapsed, 1),
    }


def read_live_plc(host: str = "192.168.1.100", port: int = 502) -> dict:
    """Read live PLC registers via Modbus TCP.

    Uses the real Micro 820 'From A to B' coil/register map from CLAUDE.md.
    Returns a tag dict compatible with the diagnosis engine.
    """
    from pymodbus.client import ModbusTcpClient

    client = ModbusTcpClient(host, port=port, timeout=3)
    if not client.connect():
        print(f"WARNING: Cannot connect to PLC at {host}:{port}")
        print("Falling back to video-only diagnosis.")
        return None

    tags = {}
    try:
        # Read coils 0-17 (From A to B scene + physical I/O)
        coil_result = client.read_coils(address=0, count=18)
        if not coil_result.isError():
            bits = [bool(b) for b in coil_result.bits[:18]]
            # Scene coils
            tags["conveyor_running"] = bits[0]
            tags["emitter_active"] = bits[1]
            tags["sensor_1_active"] = bits[2]   # SensorStart
            tags["sensor_2_active"] = bits[3]   # SensorEnd
            tags["run_command"] = bits[4]
            # Physical I/O
            tags["switch_center"] = bits[7]      # 3-pos switch CENTER
            tags["e_stop_active"] = bits[8]      # E-stop NO contact
            tags["e_stop_nc"] = bits[9]          # E-stop NC (ON when released)
            tags["switch_right"] = bits[10]      # 3-pos switch RIGHT
            tags["pushbutton"] = bits[11]        # Left pushbutton
            # Derive motor state from conveyor
            tags["motor_running"] = bits[0]
            tags["motor_stopped"] = not bits[0]
            tags["fault_alarm"] = bits[8] and not bits[9]  # E-stop pressed

        # Read holding registers 100-105
        reg_result = client.read_holding_registers(address=100, count=6)
        if not reg_result.isError():
            tags["item_count"] = reg_result.registers[0]
            tags["motor_speed"] = reg_result.registers[1] if len(reg_result.registers) > 1 else 0
            tags["motor_current"] = reg_result.registers[2] / 10.0 if len(reg_result.registers) > 2 else 0.0
            tags["temperature"] = reg_result.registers[3] / 10.0 if len(reg_result.registers) > 3 else 0.0
            tags["pressure"] = reg_result.registers[4] if len(reg_result.registers) > 4 else 0
            tags["error_code"] = reg_result.registers[5] if len(reg_result.registers) > 5 else 0

        print(f"PLC read OK: {len(tags)} tags from {host}")
        for k, v in sorted(tags.items()):
            print(f"  {k}: {v}")
    finally:
        client.close()

    return tags


def main():
    parser = argparse.ArgumentParser(description="FactoryLM Vision — Cosmos R2 Diagnosis")
    media = parser.add_mutually_exclusive_group(required=True)
    media.add_argument("--image", help="Path to factory image (PNG/JPG)")
    media.add_argument("--video", help="Path to factory video (MP4)")

    parser.add_argument("--plc-json", help="Path to PLC register JSON snapshot")
    parser.add_argument("--simulate-plc", choices=list(SIMULATED_SCENARIOS.keys()),
                        help="Use simulated PLC scenario")
    parser.add_argument("--live-plc", action="store_true",
                        help="Read live PLC registers via Modbus TCP")
    parser.add_argument("--plc-host", default="192.168.1.100",
                        help="PLC IP address for --live-plc (default: 192.168.1.100)")
    parser.add_argument("--plc-port", type=int, default=502,
                        help="PLC Modbus TCP port (default: 502)")
    parser.add_argument("--question", help="Specific question to ask about the factory")
    parser.add_argument("--url", default=VLLM_URL, help="vLLM endpoint URL")
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    media_path = args.image or args.video
    if not os.path.exists(media_path):
        print(f"Error: File not found: {media_path}")
        sys.exit(1)

    # Load PLC data
    plc_tags = None
    plc_source = "none (video-only)"
    if args.live_plc:
        plc_tags = read_live_plc(args.plc_host, args.plc_port)
        plc_source = f"LIVE Modbus @ {args.plc_host}:{args.plc_port}"
    elif args.plc_json:
        with open(args.plc_json) as f:
            plc_tags = json.load(f)
        plc_source = args.plc_json
    elif args.simulate_plc:
        plc_tags = SIMULATED_SCENARIOS[args.simulate_plc]
        plc_source = f"simulated:{args.simulate_plc}"

    print(f"FactoryLM Vision — Cosmos R2 Diagnosis Engine")
    print(f"{'='*60}")
    print(f"Media: {media_path}")
    print(f"PLC: {plc_source}")
    print(f"Question: {args.question or 'general diagnosis'}")
    print(f"Endpoint: {args.url}")
    print(f"{'='*60}\n")

    result = diagnose(
        media_path=media_path,
        plc_tags=plc_tags,
        question=args.question,
        vllm_url=args.url,
        max_tokens=args.max_tokens,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if "error" in result:
            print(f"ERROR: {result['error']}")
            sys.exit(1)

        if result["reasoning"]:
            print("REASONING (chain-of-thought):")
            print("-" * 40)
            print(result["reasoning"])
            print()

        print("DIAGNOSIS:")
        print("-" * 40)
        print(result["diagnosis"])
        print()
        print(f"[{result['elapsed_s']}s | {result['usage'].get('completion_tokens', '?')} tokens]")


if __name__ == "__main__":
    main()
