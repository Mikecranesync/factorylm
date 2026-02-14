#!/usr/bin/env python3
"""
FactoryLM System Watch
======================

Monitor Matrix API tags and Telegram bot activity during fault injection testing.

Usage:
    python tools/fault_injector/watch.py
    python tools/fault_injector/watch.py --interval 1
"""

import argparse
import sys
import time
import httpx
from datetime import datetime

sys.path.insert(0, str(__file__).replace("\\", "/").rsplit("/", 3)[0])

from tools.fault_injector.config import MATRIX_API, DEMO_UI


def watch_matrix(interval: float = 2.0):
    """Watch Matrix API for tag changes."""
    print()
    print("=" * 60)
    print("  FactoryLM System Watch")
    print(f"  Polling Matrix API every {interval}s")
    print("  Press Ctrl+C to stop")
    print("=" * 60)
    print()

    http = httpx.Client(timeout=10)
    last_fault = None
    last_error = None

    while True:
        try:
            # Get latest tags
            resp = http.get(f"{MATRIX_API}/api/tags?limit=1")
            tags = resp.json()

            if not tags:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] No tags available")
                time.sleep(interval)
                continue

            tag = tags[0]

            # Extract key values
            fault = tag.get("fault_alarm", False)
            error = tag.get("error_code", 0)
            motor = "ON" if tag.get("motor_running") else "OFF"
            conveyor = "ON" if tag.get("conveyor_running") else "OFF"
            estop = "PRESSED" if tag.get("e_stop") else "ok"
            temp = tag.get("temperature", 0)
            pressure = tag.get("pressure", 0)
            s1 = "X" if tag.get("sensor_1") else "-"
            s2 = "X" if tag.get("sensor_2") else "-"

            # Detect changes
            fault_changed = fault != last_fault
            error_changed = error != last_error

            # Format output
            timestamp = datetime.now().strftime("%H:%M:%S")

            if fault_changed or error_changed:
                # Highlight changes
                print()
                print("!" * 60)
                if fault:
                    print(f"[{timestamp}] FAULT DETECTED!")
                    print(f"         Error Code: {error} - {get_error_name(error)}")
                else:
                    print(f"[{timestamp}] Fault cleared")
                print("!" * 60)
            else:
                # Normal update
                status = "FAULT" if fault else "OK"
                line = (
                    f"[{timestamp}] {status:5} | "
                    f"Motor:{motor:3} Conv:{conveyor:3} | "
                    f"E-Stop:{estop:7} | "
                    f"S1:{s1} S2:{s2} | "
                    f"Temp:{temp:3}C Press:{pressure:3}PSI | "
                    f"Err:{error}"
                )
                print(line)

            last_fault = fault
            last_error = error

        except httpx.ConnectError:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Matrix API offline")
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Error: {e}")

        time.sleep(interval)


def get_error_name(code: int) -> str:
    """Get error name from code."""
    errors = {
        0: "No error",
        1: "Motor overload",
        2: "Sensor failure",
        3: "Communication error",
        4: "Overheat",
        5: "Low pressure",
        6: "Conveyor jam",
        7: "Emergency stop",
    }
    return errors.get(code, f"Unknown ({code})")


def main():
    parser = argparse.ArgumentParser(description="Watch FactoryLM system state")
    parser.add_argument(
        "--interval", "-i",
        type=float,
        default=2.0,
        help="Poll interval in seconds (default: 2)"
    )
    args = parser.parse_args()

    try:
        watch_matrix(args.interval)
    except KeyboardInterrupt:
        print("\n\nStopped.")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
