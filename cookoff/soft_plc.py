#!/usr/bin/env python3
"""
Soft PLC — Sorting by Height Controller
========================================
Python-based PLC program that reads Factory I/O sensors via Modbus TCP
and commands actuators to sort items by height.

Logic:
  - Entry conveyor runs continuously
  - High sensor detects tall items -> divert LEFT
  - Low sensor detects short items -> divert RIGHT
  - Left/right conveyors run to clear sorted items
  - Start/stop lights reflect running state

This replaces a hardware PLC for demo purposes, proving that
FactoryLM can read sensor data AND control actuators over Modbus.

Usage:
    python cookoff/soft_plc.py [--host 100.72.2.99] [--cycle-ms 100]
"""

import argparse
import datetime
import json
import signal
import sys
import time

from pymodbus.client import ModbusTcpClient

# ---------------------------------------------------------------------------
# I/O Map (matches scene XML and config/factoryio.yaml)
# ---------------------------------------------------------------------------

# Discrete Inputs (sensors) — read via FC2
DI = {
    "high_sensor":    0,
    "low_sensor":     1,
    "pallet_sensor":  2,
    "loaded":         3,
    "at_left_entry":  4,
    "at_left_exit":   5,
    "at_right_entry": 6,
    "at_right_exit":  7,
    "start_button":   8,
    "reset_button":   9,
    "stop_button":   10,
    "e_stop":        11,
    "auto_mode":     12,
    "fio_running":   13,
}

# Coils (actuators) — write via FC5/FC15
COIL = {
    "conveyor_entry":  0,
    "load":            1,
    "unload":          2,
    "transfer_left":   3,
    "transfer_right":  4,
    "conveyor_left":   5,
    "conveyor_right":  6,
    "start_light":     7,
    "reset_light":     8,
    "stop_light":      9,
}

# ---------------------------------------------------------------------------
# Scan cycle
# ---------------------------------------------------------------------------

class SoftPLC:
    def __init__(self, host: str, port: int = 502):
        self.client = ModbusTcpClient(host, port=port, timeout=3)
        self.sensors = {}
        self.outputs = {name: False for name in COIL}
        self.running = False
        self.cycle_count = 0
        self.divert_left_timer = 0
        self.divert_right_timer = 0
        self.events = []

    def connect(self) -> bool:
        if self.client.connect():
            print(f"Connected to {self.client.comm_params.host}:{self.client.comm_params.port}")
            return True
        print("Connection failed")
        return False

    def read_inputs(self):
        """Read all discrete inputs (sensors)."""
        result = self.client.read_discrete_inputs(address=0, count=14)
        if result.isError():
            return False
        for name, addr in DI.items():
            self.sensors[name] = bool(result.bits[addr])
        return True

    def write_outputs(self):
        """Write all coils (actuators)."""
        values = [self.outputs[name] for name in sorted(COIL, key=COIL.get)]
        self.client.write_coils(address=0, values=values)

    def log_event(self, event: str):
        """Log a timestamped event for evidence."""
        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        entry = {"time": ts, "cycle": self.cycle_count, "event": event}
        self.events.append(entry)
        print(f"  [{ts}] {event}")

    # ------------------------------------------------------------------
    # Control logic — Sorting by Height
    # ------------------------------------------------------------------

    def scan(self):
        """One PLC scan cycle. Read -> Logic -> Write."""
        self.cycle_count += 1

        if not self.read_inputs():
            return

        s = self.sensors
        o = self.outputs
        prev_outputs = dict(o)

        # Emergency stop overrides everything
        if s["e_stop"]:
            for name in COIL:
                o[name] = False
            o["stop_light"] = True
            if prev_outputs.get("conveyor_entry"):
                self.log_event("E-STOP activated — all outputs OFF")
            self.write_outputs()
            return

        # --- Core sorting logic ---

        # Entry conveyor: always run (brings items to the sorting point)
        o["conveyor_entry"] = True

        # Left and right branch conveyors: always run to clear items
        o["conveyor_left"] = True
        o["conveyor_right"] = True

        # Sorting decision at the height sensor
        # High sensor ON + Low sensor OFF = TALL item -> go LEFT
        # Low sensor ON + High sensor OFF = SHORT item -> go RIGHT
        # Both ON = item passing through (pallet with item) -> check height
        # Both OFF = no item at sensor

        if s["high_sensor"] and not s["low_sensor"]:
            # Tall item detected — divert left
            if self.divert_left_timer == 0:
                self.log_event("TALL item detected -> divert LEFT")
            self.divert_left_timer = 15  # hold for 15 cycles (~1.5s at 100ms)
            self.divert_right_timer = 0

        elif s["low_sensor"] and not s["high_sensor"]:
            # Short item detected — divert right
            if self.divert_right_timer == 0:
                self.log_event("SHORT item detected -> divert RIGHT")
            self.divert_right_timer = 15
            self.divert_left_timer = 0

        # Decrement timers
        if self.divert_left_timer > 0:
            o["transfer_left"] = True
            o["transfer_right"] = False
            self.divert_left_timer -= 1
        elif self.divert_right_timer > 0:
            o["transfer_left"] = False
            o["transfer_right"] = True
            self.divert_right_timer -= 1
        else:
            # No active divert — keep both off (items continue straight)
            o["transfer_left"] = False
            o["transfer_right"] = False

        # Indicator lights
        o["start_light"] = True
        o["stop_light"] = False
        o["reset_light"] = s["reset_button"]

        # Load/unload: activate when items are at endpoints
        o["load"] = s["loaded"]
        o["unload"] = s["at_right_exit"] or s["at_left_exit"]

        # Log state changes
        for name in COIL:
            if o[name] != prev_outputs.get(name):
                self.log_event(f"Output {name} -> {'ON' if o[name] else 'OFF'}")

        self.write_outputs()

    def stop_all(self):
        """Turn off all outputs."""
        for name in COIL:
            self.outputs[name] = False
        self.write_outputs()
        print("All outputs OFF")

    def save_log(self, path: str = "cookoff/soft_plc_log.json"):
        """Save event log to file."""
        with open(path, "w") as f:
            json.dump({
                "total_cycles": self.cycle_count,
                "total_events": len(self.events),
                "events": self.events,
            }, f, indent=2)
        print(f"Saved {len(self.events)} events to {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Soft PLC — Sorting by Height")
    parser.add_argument("--host", default="100.72.2.99")
    parser.add_argument("--port", type=int, default=502)
    parser.add_argument("--cycle-ms", type=int, default=100, help="Scan cycle time (ms)")
    parser.add_argument("--max-cycles", type=int, default=0, help="Stop after N cycles (0=infinite)")
    args = parser.parse_args()

    plc = SoftPLC(args.host, args.port)
    if not plc.connect():
        sys.exit(1)

    # Graceful shutdown
    def shutdown(sig, frame):
        print("\nShutting down...")
        plc.stop_all()
        plc.save_log()
        plc.client.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"Soft PLC running — cycle time {args.cycle_ms}ms")
    print(f"Sorting logic: TALL->LEFT, SHORT->RIGHT")
    print(f"Press Ctrl+C to stop\n")

    cycle = 0
    while True:
        plc.scan()
        cycle += 1

        # Print status every 50 cycles (~5s)
        if cycle % 50 == 0:
            s = plc.sensors
            active_sensors = [n for n, v in s.items() if v]
            active_outputs = [n for n, v in plc.outputs.items() if v]
            print(f"  [cycle {cycle}] sensors={active_sensors}")
            print(f"              outputs={active_outputs}")

        if args.max_cycles and cycle >= args.max_cycles:
            break

        time.sleep(args.cycle_ms / 1000.0)

    plc.stop_all()
    plc.save_log()
    plc.client.close()


if __name__ == "__main__":
    main()
