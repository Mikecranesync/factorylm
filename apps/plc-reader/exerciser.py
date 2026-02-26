#!/usr/bin/env python3
"""PLC Exerciser — write test patterns to Micro820 via Jarvis Node bridge.

Sends Python one-liners to the Jarvis Node /shell endpoint, which executes
them on the PLC Laptop that has direct Modbus TCP access to the PLC.

Usage:
    python exerciser.py --scenario motor_start
    python exerciser.py --scenario e_stop
    python exerciser.py --scenario fault
    python exerciser.py --scenario idle
    python exerciser.py --cycle
    python exerciser.py --bridge-url http://100.72.2.99:8765
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

# Defaults
DEFAULT_BRIDGE_URL = "http://100.72.2.99:8765"
DEFAULT_PLC_HOST = "192.168.1.100"
DEFAULT_PLC_PORT = 502

# Tag addresses (from factorylm-cli modbus.py)
COILS = {
    "motor_running": 0,
    "motor_stopped": 1,
    "fault_alarm": 2,
    "conveyor_running": 3,
    "sensor_1": 4,
    "sensor_2": 5,
    "e_stop": 6,
}
REGISTERS = {
    "motor_speed": 100,
    "motor_current": 101,
    "temperature": 102,
    "pressure": 103,
    "conveyor_speed": 104,
    "error_code": 105,
}
SCALE_FACTORS = {
    "motor_current": 10.0,
    "temperature": 10.0,
}


def shell(bridge_url: str, command: str, timeout: int = 10) -> dict:
    """Execute a command on the PLC Laptop via Jarvis Node /shell."""
    payload = json.dumps({"command": command, "timeout": timeout}).encode()
    req = urllib.request.Request(
        f"{bridge_url}/shell",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout + 5) as resp:
        return json.loads(resp.read())


def write_coil(bridge_url: str, host: str, port: int, name: str, value: bool) -> bool:
    addr = COILS[name]
    val = "True" if value else "False"
    script = (
        f"from pymodbus.client import ModbusTcpClient; "
        f"c=ModbusTcpClient(host='{host}',port={port},timeout=5); c.connect(); "
        f"r=c.write_coil(address={addr},value={val}); c.close(); "
        f"print('OK' if r and not r.isError() else 'FAIL')"
    )
    result = shell(bridge_url, f'python -c "{script}"')
    ok = result.get("stdout", "").strip() == "OK"
    tag_str = f"  {'OK' if ok else 'FAIL'}: {name} (coil {addr}) = {value}"
    print(tag_str)
    return ok


def write_register(bridge_url: str, host: str, port: int, name: str, value: float) -> bool:
    addr = REGISTERS[name]
    if name in SCALE_FACTORS:
        raw = int(value * SCALE_FACTORS[name])
    else:
        raw = int(value)
    script = (
        f"from pymodbus.client import ModbusTcpClient; "
        f"c=ModbusTcpClient(host='{host}',port={port},timeout=5); c.connect(); "
        f"r=c.write_register(address={addr},value={raw}); c.close(); "
        f"print('OK' if r and not r.isError() else 'FAIL')"
    )
    result = shell(bridge_url, f'python -c "{script}"')
    ok = result.get("stdout", "").strip() == "OK"
    display = f"{value} (raw {raw})" if name in SCALE_FACTORS else str(raw)
    tag_str = f"  {'OK' if ok else 'FAIL'}: {name} (reg {addr}) = {display}"
    print(tag_str)
    return ok


def scenario_idle(bridge_url: str, host: str, port: int) -> None:
    """All coils False, all registers 0."""
    print("[idle] Clearing all tags...")
    for name in COILS:
        write_coil(bridge_url, host, port, name, False)
    for name in REGISTERS:
        write_register(bridge_url, host, port, name, 0)
    print("[idle] Done.")


def scenario_motor_start(bridge_url: str, host: str, port: int) -> None:
    """Motor start sequence with ramp-up."""
    print("[motor_start] Starting motor...")
    write_coil(bridge_url, host, port, "motor_running", True)
    write_coil(bridge_url, host, port, "motor_stopped", False)
    write_register(bridge_url, host, port, "motor_speed", 150)
    print("[motor_start] Waiting 5s for ramp-up...")
    time.sleep(5)
    print("[motor_start] Ramping to full speed...")
    write_register(bridge_url, host, port, "motor_speed", 200)
    write_register(bridge_url, host, port, "motor_current", 4.5)  # raw 45
    write_register(bridge_url, host, port, "temperature", 35.0)   # raw 350
    print("[motor_start] Done.")


def scenario_e_stop(bridge_url: str, host: str, port: int) -> None:
    """Trigger e-stop, wait, clear."""
    print("[e_stop] Triggering e-stop...")
    write_coil(bridge_url, host, port, "e_stop", True)
    write_coil(bridge_url, host, port, "motor_running", False)
    write_register(bridge_url, host, port, "motor_speed", 0)
    print("[e_stop] Waiting 3s...")
    time.sleep(3)
    print("[e_stop] Clearing e-stop...")
    write_coil(bridge_url, host, port, "e_stop", False)
    print("[e_stop] Done.")


def scenario_fault(bridge_url: str, host: str, port: int) -> None:
    """Trigger fault, wait, clear."""
    print("[fault] Triggering fault...")
    write_coil(bridge_url, host, port, "fault_alarm", True)
    write_register(bridge_url, host, port, "error_code", 2)
    print("[fault] Waiting 3s...")
    time.sleep(3)
    print("[fault] Clearing fault...")
    write_coil(bridge_url, host, port, "fault_alarm", False)
    write_register(bridge_url, host, port, "error_code", 0)
    print("[fault] Done.")


def run_cycle(bridge_url: str, host: str, port: int) -> None:
    """Full test cycle: idle -> motor_start -> e_stop -> idle -> fault -> idle."""
    print("=" * 50)
    print("  PLC EXERCISER — FULL TEST CYCLE")
    print("=" * 50)

    scenario_idle(bridge_url, host, port)
    print()
    time.sleep(2)

    scenario_motor_start(bridge_url, host, port)
    print()
    print("[cycle] Holding running state 5s...")
    time.sleep(5)

    scenario_e_stop(bridge_url, host, port)
    print()
    time.sleep(2)

    scenario_idle(bridge_url, host, port)
    print()
    time.sleep(2)

    scenario_fault(bridge_url, host, port)
    print()
    time.sleep(2)

    scenario_idle(bridge_url, host, port)
    print()
    print("=" * 50)
    print("  CYCLE COMPLETE")
    print("=" * 50)


SCENARIOS = {
    "motor_start": scenario_motor_start,
    "e_stop": scenario_e_stop,
    "fault": scenario_fault,
    "idle": scenario_idle,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="PLC Exerciser — write test patterns to Micro820")
    parser.add_argument("--scenario", choices=list(SCENARIOS.keys()), help="Run a single scenario")
    parser.add_argument("--cycle", action="store_true", help="Run full test cycle")
    parser.add_argument("--bridge-url", default=DEFAULT_BRIDGE_URL, help=f"Jarvis Node URL (default: {DEFAULT_BRIDGE_URL})")
    parser.add_argument("--plc-host", default=DEFAULT_PLC_HOST, help=f"PLC IP (default: {DEFAULT_PLC_HOST})")
    parser.add_argument("--plc-port", type=int, default=DEFAULT_PLC_PORT, help=f"PLC port (default: {DEFAULT_PLC_PORT})")
    args = parser.parse_args()

    if not args.scenario and not args.cycle:
        parser.print_help()
        sys.exit(1)

    # Quick health check
    print(f"Bridge: {args.bridge_url}")
    print(f"PLC:    {args.plc_host}:{args.plc_port}")
    try:
        req = urllib.request.Request(f"{args.bridge_url}/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            health = json.loads(resp.read())
        if health.get("status") != "online":
            print(f"WARNING: Jarvis Node status = {health.get('status')}")
        else:
            print("Jarvis Node: online")
    except Exception as exc:
        print(f"ERROR: Cannot reach Jarvis Node at {args.bridge_url}: {exc}")
        sys.exit(1)
    print()

    if args.cycle:
        run_cycle(args.bridge_url, args.plc_host, args.plc_port)
    elif args.scenario:
        SCENARIOS[args.scenario](args.bridge_url, args.plc_host, args.plc_port)


if __name__ == "__main__":
    main()
