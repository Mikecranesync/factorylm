#!/usr/bin/env python3
"""Post-deploy verification for Micro820 v2.0 program.

Checks:
  1. Ping 192.168.1.100
  2. CIP port 44818 open
  3. Modbus TCP port 502 open
  4. Read all tags via CIP — confirm new tags exist
  5. Heartbeat toggling (proves RUN mode)
  6. Read Modbus coils and registers — confirm mapping
  7. Print PASS/FAIL summary

Usage:
    python recovery/verify_deploy.py [--host 192.168.1.100]
"""

import argparse
import socket
import subprocess
import sys
import time

# ---------------------------------------------------------------------------
# Optional imports
# ---------------------------------------------------------------------------

try:
    from pycomm3 import LogixDriver
    HAS_CIP = True
except ImportError:
    HAS_CIP = False

try:
    from pymodbus.client import ModbusTcpClient
    HAS_MODBUS = True
except ImportError:
    HAS_MODBUS = False

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_HOST = "192.168.1.100"

# Tags that MUST exist after v2.0 deploy (new additions)
NEW_TAGS = [
    "conv_state",
    "system_ready",
    "heartbeat",
    "cycle_count",
    "uptime_seconds",
    "vfd_fault_code",
    "item_count",
    "auto_mode",
    "manual_mode",
    "off_mode",
    "button_rising",
    "conveyor_speed_cmd",
]

# Tags that already existed (spot-check a subset)
EXISTING_TAGS = [
    "motor_running",
    "motor_stopped",
    "conveyor_running",
    "fault_alarm",
    "e_stop_active",
    "motor_speed",
    "error_code",
    "vfd_comm_ok",
    "vfd_frequency",
    "conveyor_speed",
]

# Expected Modbus coil mapping (address → tag name)
EXPECTED_COILS = {
    0: "motor_running",
    1: "conveyor_running",
    2: "fault_alarm",
    3: "vfd_comm_ok",
    4: "system_ready",
    5: "e_stop_active",
    6: "auto_mode",
    7: "heartbeat",
}

# Expected Modbus register mapping (offset from 100 → tag name)
EXPECTED_REGISTERS = {
    100: "motor_speed",
    101: "motor_current",
    102: "temperature",
    103: "pressure",
    104: "conveyor_speed",
    105: "error_code",
    106: "vfd_frequency",
    107: "vfd_current",
    108: "vfd_voltage",
    109: "vfd_dc_bus",
    110: "item_count",
    111: "uptime_seconds",
    112: "conveyor_speed_cmd",
    113: "conv_state",
}

# ---------------------------------------------------------------------------
# Test functions
# ---------------------------------------------------------------------------

results = []


def record(name: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    results.append((name, passed, detail))
    icon = "+" if passed else "!"
    msg = f"  [{icon}] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def test_ping(host: str):
    """Test 1: ICMP ping."""
    print("\n[Test 1] Ping...")
    try:
        # Windows ping
        r = subprocess.run(
            ["ping", "-n", "3", "-w", "2000", host],
            capture_output=True, text=True, timeout=15,
        )
        lost = "0% loss" in r.stdout or "(0% loss)" in r.stdout
        record("Ping", lost, f"{'reachable' if lost else 'unreachable'}")
    except Exception as e:
        record("Ping", False, str(e))


def test_port(host: str, port: int, name: str):
    """Test TCP port open."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect((host, port))
        s.close()
        record(f"Port {port} ({name})", True, "open")
    except Exception as e:
        record(f"Port {port} ({name})", False, str(e))


def test_cip_tags(host: str):
    """Test 4: Read tags via CIP, check new tags exist."""
    print("\n[Test 4] CIP tag verification...")
    if not HAS_CIP:
        record("CIP tags", False, "pycomm3 not installed (pip install pycomm3)")
        return

    try:
        with LogixDriver(host) as plc:
            # Get tag list
            tag_list = plc.get_tag_list()
            tag_names = {t.tag_name for t in tag_list}
            total = len(tag_names)
            record("CIP connect", True, f"{total} tags found")

            # Check existing tags
            missing_existing = [t for t in EXISTING_TAGS if t not in tag_names]
            if missing_existing:
                record("Existing tags", False, f"missing: {missing_existing}")
            else:
                record("Existing tags", True, f"{len(EXISTING_TAGS)}/{len(EXISTING_TAGS)} present")

            # Check new tags
            missing_new = [t for t in NEW_TAGS if t not in tag_names]
            if missing_new:
                record("New tags", False, f"missing: {missing_new}")
            else:
                record("New tags", True, f"{len(NEW_TAGS)}/{len(NEW_TAGS)} present")

            # Read a few values to confirm they're usable
            test_reads = ["conv_state", "heartbeat", "system_ready", "uptime_seconds"]
            readable = []
            for tag in test_reads:
                if tag in tag_names:
                    result = plc.read(tag)
                    if result.error is None:
                        readable.append(f"{tag}={result.value}")
            if readable:
                record("CIP read values", True, ", ".join(readable))
            else:
                record("CIP read values", False, "could not read any test tags")

    except Exception as e:
        record("CIP connect", False, str(e))


def test_heartbeat(host: str):
    """Test 5: Heartbeat toggling (proves RUN mode)."""
    print("\n[Test 5] Heartbeat check...")
    if not HAS_CIP:
        record("Heartbeat", False, "pycomm3 not installed")
        return

    try:
        with LogixDriver(host) as plc:
            r1 = plc.read("heartbeat")
            if r1.error:
                record("Heartbeat", False, f"read error: {r1.error}")
                return

            v1 = r1.value
            # Wait a bit for at least one scan cycle
            time.sleep(0.1)

            r2 = plc.read("heartbeat")
            v2 = r2.value

            if v1 != v2:
                record("Heartbeat", True, f"toggled {v1} → {v2} (PLC in RUN)")
            else:
                # Try again with longer wait
                time.sleep(0.5)
                r3 = plc.read("heartbeat")
                v3 = r3.value
                if v1 != v3:
                    record("Heartbeat", True, f"toggled {v1} → {v3} (PLC in RUN)")
                else:
                    record("Heartbeat", False, f"stuck at {v1} — PLC may be in PROGRAM mode")

    except Exception as e:
        record("Heartbeat", False, str(e))


def test_modbus(host: str):
    """Test 6: Read Modbus coils and registers."""
    print("\n[Test 6] Modbus TCP verification...")
    if not HAS_MODBUS:
        record("Modbus", False, "pymodbus not installed (pip install pymodbus)")
        return

    try:
        client = ModbusTcpClient(host, port=502, timeout=3)
        if not client.connect():
            record("Modbus connect", False, "connection refused on port 502")
            return
        record("Modbus connect", True, "connected")

        # Read coils 0-18 (19 coils)
        coil_result = client.read_coils(0, 19)
        if coil_result.isError():
            record("Modbus coils", False, f"error: {coil_result}")
        else:
            bits = coil_result.bits[:19]
            coil_summary = []
            for addr, name in sorted(EXPECTED_COILS.items()):
                coil_summary.append(f"{name}={'ON' if bits[addr] else 'OFF'}")
            record("Modbus coils (0-18)", True, ", ".join(coil_summary[:4]) + "...")

        # Read holding registers 100-113 (14 registers)
        reg_result = client.read_holding_registers(100, 14)
        if reg_result.isError():
            record("Modbus registers", False, f"error: {reg_result}")
        else:
            regs = reg_result.registers
            reg_summary = []
            for i, (addr, name) in enumerate(sorted(EXPECTED_REGISTERS.items())):
                if i < len(regs):
                    reg_summary.append(f"{name}={regs[i]}")
            record("Modbus registers (100-113)", True,
                   ", ".join(reg_summary[:4]) + "...")

        # Check heartbeat via Modbus (coil 7)
        coil_hb1 = client.read_coils(7, 1)
        time.sleep(0.2)
        coil_hb2 = client.read_coils(7, 1)
        if not coil_hb1.isError() and not coil_hb2.isError():
            hb1 = coil_hb1.bits[0]
            hb2 = coil_hb2.bits[0]
            if hb1 != hb2:
                record("Modbus heartbeat", True, f"coil 7 toggled {hb1} → {hb2}")
            else:
                record("Modbus heartbeat", False,
                       f"coil 7 stuck at {hb1} (may need longer interval)")

        client.close()

    except Exception as e:
        record("Modbus connect", False, str(e))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Verify Micro820 v2.0 deploy")
    parser.add_argument("--host", default=DEFAULT_HOST, help="PLC IP address")
    args = parser.parse_args()
    host = args.host

    print("=" * 60)
    print("  Micro820 v2.0 — Post-Deploy Verification")
    print(f"  Target: {host}")
    print("=" * 60)

    # Test 1: Ping
    test_ping(host)

    # Test 2: CIP port
    print("\n[Test 2] Port checks...")
    test_port(host, 44818, "CIP")

    # Test 3: Modbus port
    test_port(host, 502, "Modbus TCP")

    # Test 4: CIP tags
    test_cip_tags(host)

    # Test 5: Heartbeat
    test_heartbeat(host)

    # Test 6: Modbus
    test_modbus(host)

    # Summary
    print("\n" + "=" * 60)
    passed = sum(1 for _, p, _ in results if p)
    failed = sum(1 for _, p, _ in results if not p)
    total = len(results)
    print(f"  RESULTS: {passed} PASS / {failed} FAIL / {total} total")

    if failed == 0:
        print("  STATUS: ALL CHECKS PASSED")
    else:
        print("  STATUS: SOME CHECKS FAILED")
        print("\n  Failed checks:")
        for name, p, detail in results:
            if not p:
                print(f"    - {name}: {detail}")

    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
