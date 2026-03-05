"""
Factory I/O + Micro 820 PLC Event Monitor
==========================================
Polls PLC coils (0-17) and registers (100-105) every 250ms.
Logs every state change with timestamps to a JSONL audit file.
Tracks: coil changes, sensor transitions, start/stop events.
"""

import json
import time
import sys
import os
from datetime import datetime
from pathlib import Path

try:
    from pymodbus.client import ModbusTcpClient
except ImportError:
    print("ERROR: pymodbus not installed. Run: pip install pymodbus")
    sys.exit(1)

# --- Configuration ---
PLC_IP = "192.168.1.100"
PLC_PORT = 502
POLL_INTERVAL = 0.25  # 250ms
NUM_COILS = 18
NUM_REGISTERS = 6
REGISTER_START = 100

COIL_NAMES = {
    0: "Conveyor", 1: "Emitter", 2: "SensorStart", 3: "SensorEnd",
    4: "RunCommand", 5: "program_var_5", 6: "program_var_6",
    7: "DI_00_3pos_CENTER", 8: "DI_01_Estop_NO", 9: "DI_02_Estop_NC",
    10: "DI_03_3pos_RIGHT", 11: "DI_04_LeftPB", 12: "DI_05",
    13: "DI_06", 14: "DI_07", 15: "DO_00", 16: "DO_01", 17: "DO_03",
}

REGISTER_NAMES = {
    100: "ItemCount", 101: "reg_101", 102: "reg_102",
    103: "reg_103", 104: "reg_104", 105: "reg_105",
}

# --- Setup log file ---
log_dir = Path("C:/Users/hharp/Desktop/factorylm-monorepo/logs")
log_dir.mkdir(parents=True, exist_ok=True)
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
log_path = log_dir / ("plc_events_" + ts + ".jsonl")

print("PLC Event Monitor starting...")
print("  PLC: %s:%d" % (PLC_IP, PLC_PORT))
print("  Poll: %ss" % POLL_INTERVAL)
print("  Log: %s" % log_path)

# --- Connect ---
client = ModbusTcpClient(PLC_IP, port=PLC_PORT, timeout=3)
if not client.connect():
    print("FATAL: Cannot connect to PLC at %s:%d" % (PLC_IP, PLC_PORT))
    sys.exit(1)

print("Connected to PLC at %s:%d" % (PLC_IP, PLC_PORT))

# --- State tracking ---
prev_coils = None
prev_registers = None
event_count = 0
start_time = datetime.now()


def log_event(event_type, details):
    global event_count
    event_count += 1
    entry = {
        "seq": event_count,
        "timestamp": datetime.now().isoformat(),
        "elapsed_s": round((datetime.now() - start_time).total_seconds(), 3),
        "type": event_type,
    }
    entry.update(details)
    line = json.dumps(entry)
    with open(log_path, "a") as f:
        f.write(line)
        f.write("\n")
    print("[%s] %s: %s" % (entry["timestamp"], event_type, json.dumps(details)))


# Log startup
log_event("MONITOR_START", {
    "plc_ip": PLC_IP,
    "poll_interval": POLL_INTERVAL,
    "log_file": str(log_path),
})

# --- Main polling loop ---
try:
    while True:
        try:
            # Read coils
            coil_result = client.read_coils(address=0, count=NUM_COILS)
            if coil_result.isError():
                log_event("READ_ERROR", {"target": "coils", "error": str(coil_result)})
                time.sleep(POLL_INTERVAL)
                continue
            current_coils = [bool(b) for b in coil_result.bits[:NUM_COILS]]

            # Read registers
            reg_result = client.read_holding_registers(
                address=REGISTER_START, count=NUM_REGISTERS
            )
            if reg_result.isError():
                current_registers = [0] * NUM_REGISTERS
            else:
                current_registers = list(reg_result.registers)

            # --- Detect coil changes ---
            if prev_coils is not None:
                for i in range(NUM_COILS):
                    if current_coils[i] != prev_coils[i]:
                        name = COIL_NAMES.get(i, "coil_%d" % i)
                        new_val = current_coils[i]
                        edge = "RISING" if new_val else "FALLING"

                        # Classify event type
                        if i == 4:  # RunCommand
                            evt_type = "RUN_START" if new_val else "RUN_STOP"
                        elif i in (2, 3):  # Sensors
                            evt_type = "SENSOR_TRANSITION"
                        elif i in (0, 1):  # Conveyor/Emitter outputs
                            evt_type = "OUTPUT_CHANGE"
                        elif 7 <= i <= 14:  # Physical inputs
                            evt_type = "INPUT_CHANGE"
                        elif 15 <= i <= 17:  # Physical outputs
                            evt_type = "OUTPUT_CHANGE"
                        else:
                            evt_type = "COIL_CHANGE"

                        log_event(evt_type, {
                            "coil": i,
                            "name": name,
                            "edge": edge,
                            "old": prev_coils[i],
                            "new": new_val,
                        })

            # --- Detect register changes ---
            if prev_registers is not None:
                for i in range(NUM_REGISTERS):
                    addr = REGISTER_START + i
                    if current_registers[i] != prev_registers[i]:
                        name = REGISTER_NAMES.get(addr, "reg_%d" % addr)
                        log_event("REGISTER_CHANGE", {
                            "address": addr,
                            "name": name,
                            "old": prev_registers[i],
                            "new": current_registers[i],
                        })

            # --- Log initial state on first read ---
            if prev_coils is None:
                coil_state = {}
                for i, v in enumerate(current_coils):
                    coil_state[COIL_NAMES.get(i, "coil_%d" % i)] = v
                reg_state = {}
                for i, v in enumerate(current_registers):
                    key = REGISTER_NAMES.get(REGISTER_START + i, "reg_%d" % (REGISTER_START + i))
                    reg_state[key] = v
                log_event("INITIAL_STATE", {
                    "coils": coil_state,
                    "registers": reg_state,
                })

            prev_coils = current_coils
            prev_registers = current_registers

        except Exception as e:
            log_event("POLL_ERROR", {"error": str(e)})
            try:
                client.close()
                time.sleep(1)
                client.connect()
            except Exception:
                pass

        time.sleep(POLL_INTERVAL)

except KeyboardInterrupt:
    log_event("MONITOR_STOP", {
        "total_events": event_count,
        "uptime_s": round((datetime.now() - start_time).total_seconds(), 1),
    })
    print("Monitor stopped. %d events logged to %s" % (event_count, log_path))
finally:
    client.close()
