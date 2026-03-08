#!/usr/bin/env python3
"""
DTU Scenario Runner -- Factory IO Fault Detection Tests
=======================================================
Loads YAML scenarios, optionally injects faults via Modbus,
polls factory_server /api/faults, and reports pass/fail.

Usage:
    python tests/scenario_runner.py --all --cycles 1
"""

import argparse
import datetime
import json
import os
import sys
import time
from pathlib import Path

import requests
import yaml

FACTORY_SERVER_URL = os.getenv("FACTORY_SERVER_URL", "http://127.0.0.1:8600")
MODBUS_HOST = os.getenv("MODBUS_HOST", "127.0.0.1")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "5020"))
SCENARIOS_DIR = Path(__file__).parent / "scenarios"
RESULTS_DIR = Path(__file__).parent / "results"


def load_scenarios(pattern="*.yaml"):
    scenarios = []
    for f in sorted(SCENARIOS_DIR.glob(pattern)):
        with open(f) as fh:
            scenarios.append(yaml.safe_load(fh))
    return scenarios


def _normalize_coil_list(raw):
    """Normalize coil list from either format to [{address, value}]."""
    result = []
    for c in raw:
        addr = c.get("address", c.get("coil"))
        val = c.get("value", False)
        if addr is not None:
            result.append({"address": addr, "value": val})
    return result


def inject_modbus(coils):
    """Write to Modbus coils block to inject faults."""
    try:
        from pymodbus.client import ModbusTcpClient
        coils = _normalize_coil_list(coils)
        client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT)
        if not client.connect():
            print(f"  [WARN] Cannot connect to Modbus {MODBUS_HOST}:{MODBUS_PORT}")
            return False
        for c in coils:
            client.write_coil(c["address"], c["value"], device_id=1)
        client.close()
        return True
    except Exception as e:
        print(f"  [WARN] Modbus inject failed: {e}")
        return False


def clear_all_coils():
    """Reset all 14 sensor coils to False between scenarios."""
    try:
        from pymodbus.client import ModbusTcpClient
        client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT)
        if client.connect():
            for addr in range(14):
                client.write_coil(addr, False, device_id=1)
            client.close()
    except Exception:
        pass


def cleanup_modbus(coils):
    """Restore coils to safe state after test."""
    try:
        from pymodbus.client import ModbusTcpClient
        coils = _normalize_coil_list(coils)
        client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT)
        if client.connect():
            for c in coils:
                client.write_coil(c["address"], c["value"], device_id=1)
            client.close()
    except Exception:
        pass


def poll_faults(expected_code, timeout_s, poll_interval=2.0):
    """Poll /api/faults until expected fault code appears or timeout."""
    deadline = time.time() + timeout_s
    observed = []
    while time.time() < deadline:
        try:
            resp = requests.get(f"{FACTORY_SERVER_URL}/api/faults", timeout=5)
            faults = resp.json()
            codes = [f["code"] for f in faults]
            observed = codes
            if expected_code in codes:
                return True, observed
        except Exception as e:
            observed = [f"error: {e}"]
        time.sleep(poll_interval)
    return False, observed


def run_scenario(scenario, cycle=1):
    """Execute a single scenario and return result dict."""
    sid = scenario["scenario_id"]
    expected = scenario["expected_fault_code"]
    timeout = scenario.get("timeout_seconds", 10)
    inject_cfg = scenario.get("inject")
    cleanup_cfg = scenario.get("cleanup")

    print("")
    print(f"--- Scenario: {sid} (cycle {cycle}) ---")
    print(f"  Expected fault: {expected}")

    hold_seconds = scenario.get("hold_seconds", 3)
    start = time.time()

    # Clean state between scenarios
    clear_all_coils()
    time.sleep(1.5)

    # Handle both formats: {modbus_coil: [...]} or direct [...]
    coil_list = None
    if isinstance(inject_cfg, dict) and inject_cfg.get("modbus_coil"):
        coil_list = inject_cfg["modbus_coil"]
    elif isinstance(inject_cfg, list):
        coil_list = inject_cfg
    if coil_list:
        print(f"  Injecting via Modbus: {coil_list}")
        inject_modbus(coil_list)

    # Hold for jam scenarios (stuck_counts needs 10+ polls at 500ms = 5.5s)
    print(f"  Holding {hold_seconds}s...")
    time.sleep(hold_seconds)

    passed, observed = poll_faults(expected, timeout)
    duration = round(time.time() - start, 2)

    status = "PASS" if passed else "FAIL"
    print(f"  Result: {status} ({duration}s)")
    print(f"  Observed faults: {observed}")

    cleanup_list = None
    if isinstance(cleanup_cfg, dict) and cleanup_cfg.get("modbus_coil"):
        cleanup_list = cleanup_cfg["modbus_coil"]
    elif isinstance(cleanup_cfg, list):
        cleanup_list = cleanup_cfg
    if cleanup_list:
        cleanup_modbus(cleanup_list)

    return {
        "scenario_id": sid,
        "expected_fault_code": expected,
        "observed_faults": observed,
        "passed": passed,
        "duration_s": duration,
        "cycle": cycle,
    }


def main():
    parser = argparse.ArgumentParser(description="DTU Scenario Runner")
    parser.add_argument("--all", action="store_true", help="Run all scenarios")
    parser.add_argument("--scenario", type=str, help="Run a specific scenario by ID")
    parser.add_argument("--cycles", type=int, default=1, help="Number of cycles")
    args = parser.parse_args()

    scenarios = load_scenarios()
    if not scenarios:
        print(f"No scenarios found in {SCENARIOS_DIR}")
        sys.exit(1)

    if args.scenario:
        scenarios = [s for s in scenarios if s["scenario_id"] == args.scenario]
        if not scenarios:
            print(f"Scenario not found: {args.scenario}")
            sys.exit(1)

    print("DTU Scenario Runner")
    print(f"Factory Server: {FACTORY_SERVER_URL}")
    print(f"Scenarios: {len(scenarios)}")
    print(f"Cycles: {args.cycles}")

    all_results = []
    for cycle in range(1, args.cycles + 1):
        for scenario in scenarios:
            result = run_scenario(scenario, cycle)
            all_results.append(result)

    passed_count = sum(1 for r in all_results if r["passed"])
    total = len(all_results)
    failures = [r for r in all_results if not r["passed"]]

    print("")
    print("=" * 50)
    print(f"SUMMARY: {passed_count}/{total} passed")
    if failures:
        print("FAILURES:")
        for fail in failures:
            sid = fail["scenario_id"]
            cyc = fail["cycle"]
            exp = fail["expected_fault_code"]
            obs = fail["observed_faults"]
            print(f"  - {sid} (cycle {cyc}): expected {exp}, got {obs}")
    print("=" * 50)

    RESULTS_DIR.mkdir(exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = RESULTS_DIR / f"run_{ts}.json"
    with open(result_file, "w") as fh:
        json.dump({
            "timestamp": ts,
            "factory_server": FACTORY_SERVER_URL,
            "cycles": args.cycles,
            "total": total,
            "passed": passed_count,
            "failed": total - passed_count,
            "results": all_results,
        }, fh, indent=2)
    print(f"Results saved: {result_file}")

    sys.exit(0 if passed_count == total else 1)


if __name__ == "__main__":
    main()
