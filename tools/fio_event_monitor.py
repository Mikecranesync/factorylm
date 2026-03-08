"""Factory I/O + PLC Event Monitor via Web API.

Polls Factory I/O's web API for tag values and logs every change
to a timestamped JSONL file for audit.
"""
import json
import time
import datetime
import urllib.request
import os
import sys

API_BASE = "http://localhost:7410"
LOG_DIR = r"C:\Users\hharp\Desktop\factorylm-monorepo\logs"
os.makedirs(LOG_DIR, exist_ok=True)

ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = os.path.join(LOG_DIR, f"fio_events_{ts}.jsonl")
POLL_INTERVAL = 0.25  # 250ms

def get_tags():
    """Fetch all tags from Factory I/O web API."""
    req = urllib.request.Request(f"{API_BASE}/api/tags")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode())

def log_event(event_type, data):
    """Write a JSONL event to the log file."""
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "event": event_type,
        **data
    }
    line = json.dumps(entry)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")
    print(line, flush=True)

def main():
    print(f"Factory I/O Event Monitor starting...")
    print(f"API: {API_BASE}")
    print(f"Log: {LOG_FILE}")
    print(f"Poll interval: {POLL_INTERVAL}s")
    
    # Initial state
    try:
        tags = get_tags()
    except Exception as e:
        print(f"ERROR connecting to API: {e}")
        sys.exit(1)
    
    # Build state map: name -> {value, isForced, openCircuit, shortCircuit}
    prev_state = {}
    for t in tags:
        key = f"{t['name']}|{t['kind']}"
        prev_state[key] = {
            "value": t["value"],
            "isForced": t["isForced"],
            "openCircuit": t["openCircuit"],
            "shortCircuit": t["shortCircuit"]
        }
    
    # Log initial state
    log_event("INITIAL_STATE", {
        "tags": {t["name"]: {
            "kind": t["kind"],
            "address": t["address"],
            "type": t["type"],
            "value": t["value"],
            "isForced": t["isForced"]
        } for t in tags}
    })
    
    print(f"Monitoring {len(tags)} tags... (Ctrl+C to stop)")
    
    errors = 0
    while True:
        try:
            time.sleep(POLL_INTERVAL)
            tags = get_tags()
            errors = 0  # Reset error counter on success
            
            for t in tags:
                key = f"{t['name']}|{t['kind']}"
                curr = {
                    "value": t["value"],
                    "isForced": t["isForced"],
                    "openCircuit": t["openCircuit"],
                    "shortCircuit": t["shortCircuit"]
                }
                
                if key not in prev_state:
                    # New tag appeared
                    log_event("TAG_ADDED", {
                        "name": t["name"],
                        "kind": t["kind"],
                        "address": t["address"],
                        "value": t["value"]
                    })
                    prev_state[key] = curr
                    continue
                
                prev = prev_state[key]
                
                # Check value change
                if curr["value"] != prev["value"]:
                    event_type = "SENSOR_CHANGE" if t["kind"] == "Input" else "COIL_CHANGE"
                    if t["name"].startswith("FACTORY I/O"):
                        if "Running" in t["name"]:
                            event_type = "SIM_START" if curr["value"] else "SIM_STOP"
                        elif "Paused" in t["name"]:
                            event_type = "SIM_PAUSE" if curr["value"] else "SIM_RESUME"
                        elif "Reset" in t["name"] and t["kind"] == "Input":
                            event_type = "SIM_RESET"
                        else:
                            event_type = "SYSTEM_CHANGE"
                    
                    log_event(event_type, {
                        "name": t["name"],
                        "kind": t["kind"],
                        "address": t["address"],
                        "old_value": prev["value"],
                        "new_value": curr["value"]
                    })
                
                # Check forced state change
                if curr["isForced"] != prev["isForced"]:
                    log_event("FORCE_CHANGE", {
                        "name": t["name"],
                        "kind": t["kind"],
                        "isForced": curr["isForced"],
                        "forcedValue": t.get("forcedValue")
                    })
                
                # Check fault changes
                if curr["openCircuit"] != prev["openCircuit"]:
                    log_event("FAULT_OPEN_CIRCUIT", {
                        "name": t["name"],
                        "kind": t["kind"],
                        "openCircuit": curr["openCircuit"]
                    })
                
                if curr["shortCircuit"] != prev["shortCircuit"]:
                    log_event("FAULT_SHORT_CIRCUIT", {
                        "name": t["name"],
                        "kind": t["kind"],
                        "shortCircuit": curr["shortCircuit"]
                    })
                
                prev_state[key] = curr
        
        except KeyboardInterrupt:
            log_event("MONITOR_STOP", {"reason": "user_interrupt"})
            print("\nMonitor stopped.")
            break
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"Error (attempt {errors}): {e}", flush=True)
            if errors >= 10:
                log_event("MONITOR_STOP", {"reason": "too_many_errors", "last_error": str(e)})
                print(f"Too many errors, stopping.")
                break
            time.sleep(1)

if __name__ == "__main__":
    main()
