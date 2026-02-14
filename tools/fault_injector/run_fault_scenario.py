#!/usr/bin/env python3
"""
FactoryLM Fault Scenario Runner
===============================

Inject faults into Factory I/O to test the Telegram bot diagnosis system.

Usage:
    python tools/fault_injector/run_fault_scenario.py --list
    python tools/fault_injector/run_fault_scenario.py --scenario sensor_jam
    python tools/fault_injector/run_fault_scenario.py --scenario motor_overload --hold 60
    python tools/fault_injector/run_fault_scenario.py --scenario normal  # Clear faults

Examples:
    # List available scenarios
    python tools/fault_injector/run_fault_scenario.py --list

    # Run a jam scenario for 30 seconds
    python tools/fault_injector/run_fault_scenario.py --scenario sensor_jam

    # Clear all faults
    python tools/fault_injector/run_fault_scenario.py --scenario normal
"""

import argparse
import sys
import logging
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(__file__).replace("\\", "/").rsplit("/", 3)[0])

from tools.fault_injector.scenarios import SCENARIOS, list_scenarios, run_scenario
from tools.fault_injector.remote import (
    is_factory_io_running,
    start_factory_io,
    get_factory_io_status,
    jarvis_health
)
from tools.fault_injector.config import (
    PLC_HOST, MODBUS_PORT, MATRIX_API, DEMO_UI, FAULT_HOLD_SECONDS
)


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        level=level,
        datefmt="%H:%M:%S"
    )


def print_banner():
    """Print tool banner."""
    print()
    print("=" * 60)
    print("  FactoryLM Fault Injector")
    print("  Test your AI diagnosis system with real fault scenarios")
    print("=" * 60)
    print()


def print_scenarios():
    """Print available scenarios."""
    print("Available Fault Scenarios:")
    print("-" * 50)
    for s in list_scenarios():
        print(f"  {s['id']:20} - {s['name']}")
        print(f"  {' '*20}   {s['description']}")
        print()


def check_prerequisites() -> bool:
    """Check that all required services are available."""
    print("Checking prerequisites...")

    # Check Jarvis
    jarvis = jarvis_health()
    if jarvis.get("status") != "healthy":
        print(f"  [FAIL] Jarvis Node not available at {PLC_HOST}:8765")
        print(f"         Error: {jarvis.get('error', 'Unknown')}")
        return False
    print(f"  [OK] Jarvis Node: {jarvis.get('machine', 'Unknown')}")

    # Check Factory I/O
    if not is_factory_io_running():
        print(f"  [WARN] Factory I/O not running")
        print(f"         Starting Factory I/O...")
        if not start_factory_io():
            print(f"  [FAIL] Could not start Factory I/O")
            return False
        print(f"  [OK] Factory I/O started")
    else:
        print(f"  [OK] Factory I/O running")

    # Check Modbus
    status = get_factory_io_status()
    if not status.get("modbus_listening"):
        print(f"  [WARN] Modbus port 502 not listening")
        print(f"         Make sure Factory I/O Modbus server is enabled")
    else:
        print(f"  [OK] Modbus TCP listening on port 502")

    print()
    return True


def main():
    parser = argparse.ArgumentParser(
        description="FactoryLM Fault Scenario Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --list                      List available scenarios
  %(prog)s --scenario sensor_jam       Inject sensor jam fault
  %(prog)s --scenario motor_overload   Inject motor overload
  %(prog)s --scenario normal           Clear all faults
  %(prog)s --scenario overheat --hold 60  Hold fault for 60 seconds
        """
    )

    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available fault scenarios"
    )
    parser.add_argument(
        "--scenario", "-s",
        type=str,
        help="Scenario ID to run (use --list to see options)"
    )
    parser.add_argument(
        "--hold", "-t",
        type=int,
        default=None,
        help=f"Seconds to hold fault state (default: {FAULT_HOLD_SECONDS})"
    )
    parser.add_argument(
        "--skip-checks",
        action="store_true",
        help="Skip prerequisite checks"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    print_banner()

    # List scenarios
    if args.list:
        print_scenarios()
        return 0

    # Require scenario
    if not args.scenario:
        print("Error: --scenario required (use --list to see options)")
        print()
        parser.print_help()
        return 1

    # Validate scenario
    if args.scenario not in SCENARIOS:
        print(f"Error: Unknown scenario '{args.scenario}'")
        print()
        print_scenarios()
        return 1

    # Check prerequisites
    if not args.skip_checks:
        if not check_prerequisites():
            print("Prerequisites not met. Use --skip-checks to bypass.")
            return 1

    # Run scenario
    scenario = SCENARIOS[args.scenario]
    print(f"Running Scenario: {scenario.name}")
    print(f"Description: {scenario.description}")
    print("-" * 50)

    def status_callback(msg):
        print(f"  >> {msg}")

    result = run_scenario(
        args.scenario,
        hold_seconds=args.hold,
        callback=status_callback
    )

    print()
    print("-" * 50)

    if result["success"]:
        print("[SUCCESS] Scenario completed")
        print()
        print("Expected Gus Response:")
        print(f"  \"{result.get('expected_diagnosis', 'N/A')}\"")
        print()
        if result.get("recovery_steps"):
            print("Recovery Steps:")
            for i, step in enumerate(result["recovery_steps"], 1):
                print(f"  {i}. {step}")
        print()
        print("=" * 50)
        print("NOW TEST WITH TELEGRAM:")
        print("  Send to @UltronVPS_bot: \"What's wrong with the equipment?\"")
        print("=" * 50)
    else:
        print(f"[FAILED] {result.get('error', 'Unknown error')}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
