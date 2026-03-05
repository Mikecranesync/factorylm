#!/usr/bin/env python3
"""
Modbus TCP Server for Factory I/O
=================================
Runs a Modbus server that Factory I/O connects to as a CLIENT.
Factory I/O reads coils (actuator commands) and writes discrete inputs (sensor data).

This is the standard architecture for PLC control of Factory I/O:
  Factory I/O (Modbus Client) <---> This Server <---> Sorting Logic

The sorting logic runs in a background thread, reading sensor inputs
and setting coil outputs to sort items by height.

Usage:
    python cookoff/modbus_server.py [--host 0.0.0.0] [--port 502]
"""

import argparse
import datetime
import json
import logging
import signal
import sys
import threading
import time

from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
)
try:
    from pymodbus.datastore import ModbusSlaveContext
except ImportError:
    from pymodbus.datastore import ModbusDeviceContext as ModbusSlaveContext
from pymodbus.server import StartTcpServer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# I/O Map — matches Factory I/O ModbusTCPClient scene mapping
# ---------------------------------------------------------------------------

# Discrete Inputs (address 0-13): Factory I/O WRITES sensor data here
DI_NAMES = [
    "high_sensor", "low_sensor", "pallet_sensor", "loaded",
    "at_left_entry", "at_left_exit", "at_right_entry", "at_right_exit",
    "start_button", "reset_button", "stop_button", "e_stop",
    "auto_mode", "fio_running",
]

# Coils (address 0-9): Factory I/O READS actuator commands from here
COIL_NAMES = [
    "conveyor_entry", "load", "unload", "transfer_left", "transfer_right",
    "conveyor_left", "conveyor_right", "start_light", "reset_light", "stop_light",
]

# Holding Registers (address 0): counter value
HR_NAMES = ["counter"]


class SortingController:
    """Background thread that reads sensor inputs and sets actuator coils."""

    def __init__(self, context: ModbusServerContext, cycle_ms: int = 100):
        self.context = context
        self.cycle_ms = cycle_ms
        self.running = True
        self.cycle_count = 0
        self.divert_left_timer = 0
        self.divert_right_timer = 0
        self.events = []
        self.prev_sensors = {}
        self.items_sorted_left = 0
        self.items_sorted_right = 0

    def read_sensor(self, name: str) -> bool:
        """Read a discrete input (sensor) from the datastore."""
        idx = DI_NAMES.index(name)
        # Discrete inputs are at function code 2, address base 0
        # pymodbus stores discrete inputs in block starting at address 0
        store = self.context[1]  # slave ID 1
        values = store.getValues(2, idx, count=1)  # FC2 = discrete inputs
        return bool(values[0])

    def read_all_sensors(self) -> dict:
        store = self.context[1]
        values = store.getValues(2, 0, count=len(DI_NAMES))
        return {name: bool(values[i]) for i, name in enumerate(DI_NAMES)}

    def write_coil(self, name: str, value: bool):
        """Write a coil (actuator command) to the datastore."""
        idx = COIL_NAMES.index(name)
        store = self.context[1]
        store.setValues(1, idx, [value])  # FC1 = coils

    def log_event(self, event: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        entry = {"time": ts, "cycle": self.cycle_count, "event": event}
        self.events.append(entry)
        log.info(event)

    def scan(self):
        """One PLC scan cycle."""
        self.cycle_count += 1
        sensors = self.read_all_sensors()

        # Detect sensor changes
        for name in DI_NAMES:
            prev = self.prev_sensors.get(name)
            curr = sensors[name]
            if prev is not None and prev != curr:
                self.log_event(f"Sensor {name}: {prev} -> {curr}")
        self.prev_sensors = dict(sensors)

        # E-stop override
        if sensors["e_stop"]:
            for name in COIL_NAMES:
                self.write_coil(name, False)
            self.write_coil("stop_light", True)
            return

        # --- Sorting logic ---
        self.write_coil("conveyor_entry", True)
        self.write_coil("conveyor_left", True)
        self.write_coil("conveyor_right", True)

        # Height-based sorting
        if sensors["high_sensor"] and not sensors["low_sensor"]:
            if self.divert_left_timer == 0:
                self.log_event(f"TALL item -> LEFT (total: {self.items_sorted_left + 1})")
                self.items_sorted_left += 1
            self.divert_left_timer = 20
            self.divert_right_timer = 0
        elif sensors["low_sensor"] and not sensors["high_sensor"]:
            if self.divert_right_timer == 0:
                self.log_event(f"SHORT item -> RIGHT (total: {self.items_sorted_right + 1})")
                self.items_sorted_right += 1
            self.divert_right_timer = 20
            self.divert_left_timer = 0

        # Transfer timers
        if self.divert_left_timer > 0:
            self.write_coil("transfer_left", True)
            self.write_coil("transfer_right", False)
            self.divert_left_timer -= 1
        elif self.divert_right_timer > 0:
            self.write_coil("transfer_left", False)
            self.write_coil("transfer_right", True)
            self.divert_right_timer -= 1
        else:
            self.write_coil("transfer_left", False)
            self.write_coil("transfer_right", False)

        # Lights
        self.write_coil("start_light", True)
        self.write_coil("stop_light", False)
        self.write_coil("reset_light", sensors.get("reset_button", False))

        # Load/unload
        self.write_coil("load", sensors.get("loaded", False))
        self.write_coil("unload",
                        sensors.get("at_right_exit", False) or
                        sensors.get("at_left_exit", False))

    def run_loop(self):
        log.info("Sorting controller started (%dms cycle)", self.cycle_ms)
        while self.running:
            self.scan()
            if self.cycle_count % 100 == 0:
                s = self.read_all_sensors()
                active = [n for n, v in s.items() if v]
                log.info("Cycle %d | sensors=%s | sorted: L=%d R=%d",
                         self.cycle_count, active,
                         self.items_sorted_left, self.items_sorted_right)
            time.sleep(self.cycle_ms / 1000.0)

    def save_log(self, path="cookoff/modbus_server_log.json"):
        with open(path, "w") as f:
            json.dump({
                "total_cycles": self.cycle_count,
                "items_sorted_left": self.items_sorted_left,
                "items_sorted_right": self.items_sorted_right,
                "events": self.events[-200:],  # last 200 events
            }, f, indent=2)
        log.info("Saved %d events to %s", len(self.events), path)


def main():
    parser = argparse.ArgumentParser(description="Modbus TCP Server for Factory I/O")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5020,
                        help="Port (default 5020 to avoid conflict with FIO server on 502)")
    parser.add_argument("--cycle-ms", type=int, default=100)
    args = parser.parse_args()

    # Create datastore with enough addresses
    # Coils (FC1/FC5/FC15): 16 addresses
    # Discrete Inputs (FC2): 16 addresses
    # Input Registers (FC4): 16 addresses
    # Holding Registers (FC3/FC6/FC16): 16 addresses
    store = ModbusSlaveContext(
        co=ModbusSequentialDataBlock(0, [False] * 16),   # Coils
        di=ModbusSequentialDataBlock(0, [False] * 16),   # Discrete Inputs
        ir=ModbusSequentialDataBlock(0, [0] * 16),       # Input Registers
        hr=ModbusSequentialDataBlock(0, [0] * 16),       # Holding Registers
    )
    context = ModbusServerContext(devices={1: store}, single=False)

    # Start sorting controller in background thread
    controller = SortingController(context, cycle_ms=args.cycle_ms)
    ctrl_thread = threading.Thread(target=controller.run_loop, daemon=True)
    ctrl_thread.start()

    def shutdown(sig, frame):
        log.info("Shutting down...")
        controller.running = False
        controller.save_log()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    log.info("Modbus TCP Server starting on %s:%d (slave ID 1)", args.host, args.port)
    log.info("Configure Factory I/O: Drivers -> Modbus TCP/IP Client -> %s:%d",
             args.host, args.port)

    StartTcpServer(context=context, address=(args.host, args.port))


if __name__ == "__main__":
    main()
