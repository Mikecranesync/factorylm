"""
Factory I/O Fault Injector — Demo fault injection via Web API.

Uses Factory I/O's force/release endpoints to simulate equipment faults
for the Cosmos Cookoff diagnosis demo.

Usage:
    python sim/fault_injector.py --fault sensor         # Force sensor failure
    python sim/fault_injector.py --fault jam             # Simulate conveyor jam
    python sim/fault_injector.py --fault estop           # Trigger E-stop
    python sim/fault_injector.py --fault motor           # Motor overload (stop conveyor)
    python sim/fault_injector.py --clear                 # Release all forced tags
    python sim/fault_injector.py --list                  # Show available faults
    python sim/fault_injector.py --interactive           # Interactive mode
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from sim.sorting_controller import FactoryIOClient, load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("fault_injector")


# Fault definitions using actual Factory I/O tag names for "Sorting by Height (Basic)"
FAULTS = {
    "sensor": {
        "name": "Sensor Failure",
        "description": "Height sensors forced OFF — parts pass unsorted",
        "force": {"High sensor": False, "Low sensor": False},
    },
    "jam": {
        "name": "Conveyor Jam",
        "description": "Pallet sensor stuck ON — appears as permanent blockage",
        "force": {"Pallet sensor": True},
    },
    "estop": {
        "name": "Emergency Stop",
        "description": "E-stop forced active (False = pressed in Factory I/O)",
        "force": {"Emergency stop": False},
    },
    "motor": {
        "name": "Motor Failure",
        "description": "Entry conveyor stops — parts pile up",
        "force": {"Conveyor entry": False},
    },
    "sorter_stuck_left": {
        "name": "Sorter Stuck Left",
        "description": "Left transfer arm stays engaged — all parts go left",
        "force": {"Transf. left": True, "Transf. right": False},
    },
    "sorter_stuck_right": {
        "name": "Sorter Stuck Right",
        "description": "Right transfer arm stays engaged — all parts go right",
        "force": {"Transf. right": True, "Transf. left": False},
    },
    "blind": {
        "name": "Sensor Blind",
        "description": "Low sensor forced OFF — controller can't detect any parts",
        "force": {"Low sensor": False},
    },
    "emitter_off": {
        "name": "No Parts",
        "description": "Emitter forced OFF — no new parts entering system",
        "force": {"Emitter": False},
    },
}


class FaultInjector:
    """Inject and clear faults via Factory I/O Web API force endpoints."""

    def __init__(self, client: FactoryIOClient):
        self.fio = client
        self._active_faults: dict[str, list[str]] = {}

    def inject(self, fault_id: str, duration: float = 0) -> bool:
        if fault_id not in FAULTS:
            logger.error("Unknown fault: %s. Available: %s", fault_id, list(FAULTS.keys()))
            return False

        fault = FAULTS[fault_id]
        logger.info("Injecting: %s — %s", fault["name"], fault["description"])

        forced_tags = []
        for tag_name, value in fault["force"].items():
            if self.fio.force_tag(tag_name, value):
                forced_tags.append(tag_name)
                logger.info("  Forced: %s = %s", tag_name, value)
            else:
                logger.warning("  FAILED to force: %s", tag_name)

        self._active_faults[fault_id] = forced_tags

        if duration > 0:
            logger.info("Auto-clear in %.1fs", duration)
            time.sleep(duration)
            self.clear(fault_id)

        return len(forced_tags) > 0

    def clear(self, fault_id: str = "") -> bool:
        if fault_id and fault_id in self._active_faults:
            for tag_name in self._active_faults.pop(fault_id):
                self.fio.release_tag(tag_name)
                logger.info("  Released: %s", tag_name)
            logger.info("Cleared: %s", fault_id)
            return True
        elif not fault_id:
            # Clear everything
            all_tags = set()
            for tags in self._active_faults.values():
                all_tags.update(tags)
            for tag_name in all_tags:
                self.fio.release_tag(tag_name)
                logger.info("  Released: %s", tag_name)
            # Safety: also release all known fault tags
            for fault in FAULTS.values():
                for tag_name in fault["force"]:
                    self.fio.release_tag(tag_name)
            count = len(self._active_faults)
            self._active_faults.clear()
            logger.info("Cleared all faults (%d)", count)
            return True
        else:
            logger.warning("Fault '%s' not active", fault_id)
            return False

    @property
    def active_faults(self) -> list[str]:
        return list(self._active_faults.keys())

    def status(self) -> dict:
        return {
            "active": [
                {"id": fid, "name": FAULTS[fid]["name"], "forced_tags": tags}
                for fid, tags in self._active_faults.items()
            ],
            "available": [
                {"id": fid, "name": f["name"], "description": f["description"]}
                for fid, f in FAULTS.items()
            ],
        }


def main():
    parser = argparse.ArgumentParser(description="Factory I/O Fault Injector")
    parser.add_argument("--api-url", default=os.getenv("FACTORYIO_URL", "http://localhost:7410"))
    parser.add_argument("--config", default="config/sorting_tags.yaml")
    parser.add_argument("--fault", help="Fault ID to inject")
    parser.add_argument("--duration", type=float, default=0, help="Auto-clear after N seconds")
    parser.add_argument("--clear", action="store_true", help="Clear all faults")
    parser.add_argument("--list", action="store_true", help="List available faults")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    args = parser.parse_args()

    if args.list:
        print(f"\n{'='*60}")
        print("Available Faults")
        print(f"{'='*60}")
        for fid, f in FAULTS.items():
            print(f"  {fid:<20} {f['name']}")
            print(f"  {'':20} {f['description']}")
            print(f"  {'':20} Forces: {json.dumps(f['force'])}")
            print()
        return

    config = load_config(args.config)
    client = FactoryIOClient(base_url=args.api_url)

    if not client.check_connection():
        logger.error("Cannot connect to Factory I/O at %s", args.api_url)
        sys.exit(1)

    injector = FaultInjector(client)

    if args.clear:
        injector.clear()
        return

    if args.fault:
        injector.inject(args.fault, duration=args.duration)
        return

    if args.interactive:
        print("\nInteractive Fault Injector")
        print("Commands: inject <fault>, clear [fault], status, list, quit\n")
        while True:
            try:
                cmd = input("fault> ").strip().split()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not cmd:
                continue
            if cmd[0] in ("quit", "exit"):
                break
            elif cmd[0] == "inject" and len(cmd) > 1:
                dur = float(cmd[2]) if len(cmd) > 2 else 0
                injector.inject(cmd[1], duration=dur)
            elif cmd[0] == "clear":
                injector.clear(cmd[1] if len(cmd) > 1 else "")
            elif cmd[0] == "status":
                print(json.dumps(injector.status(), indent=2))
            elif cmd[0] == "list":
                for fid in FAULTS:
                    print(f"  {fid}: {FAULTS[fid]['name']}")
            else:
                print(f"Unknown: {cmd[0]}")
        injector.clear()
        return

    parser.print_help()


if __name__ == "__main__":
    main()
