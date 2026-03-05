"""
FactoryLM Service Orchestrator
================================
Starts Matrix (8002), plc-modbus (8001), and plc_reader together.
Auto-detects PLC IP, monitors health, and shuts down cleanly.

Usage:
    python start_services.py           # Start all services
    python start_services.py --stop    # Kill running services via PID file
"""

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.resolve()
PID_DIR = REPO_ROOT / ".factorylm"
LOG_DIR = PID_DIR / "logs"
PID_FILE = PID_DIR / "services.pid"

PLC_MODBUS_DIR = REPO_ROOT / "services" / "plc-modbus"
CORE_DIR = Path(os.getenv("FACTORYLM_CORE", str(Path.home() / "Desktop" / "factorylm-core")))
PLC_READER = CORE_DIR / "plc_reader.py"

# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------
PLC_CANDIDATES = [
    ("192.168.1.100", "Direct Ethernet"),
    ("100.72.2.99", "Tailnet"),
]
MODBUS_PORT = 502

MATRIX_PORT = 8002
PLC_MODBUS_PORT = 8001

HEALTH_TIMEOUT = 10  # seconds to wait for each service to become healthy
MONITOR_INTERVAL = 15  # seconds between health-monitor ticks

# ---------------------------------------------------------------------------
# Globals for signal handler
# ---------------------------------------------------------------------------
children: dict[str, subprocess.Popen] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def detect_plc_ip() -> str:
    """Try each candidate PLC IP with a quick TCP connect on port 502."""
    for ip, label in PLC_CANDIDATES:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.5)
            s.connect((ip, MODBUS_PORT))
            s.close()
            log(f"PLC detected at {ip} ({label})")
            return ip
        except (OSError, socket.timeout):
            log(f"  {ip} ({label}) — not reachable")
    print("\nERROR: Cannot reach PLC on any known address.")
    print("  Tried: " + ", ".join(f"{ip}" for ip, _ in PLC_CANDIDATES))
    print("  Is the PLC powered on and connected?")
    sys.exit(1)


def wait_for_health(url: str, label: str, timeout: int = HEALTH_TIMEOUT) -> bool:
    """Poll a health URL until it returns 200 or timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = urlopen(url, timeout=2)
            if resp.status == 200:
                log(f"{label} healthy")
                return True
        except (URLError, OSError):
            pass
        time.sleep(0.5)
    log(f"WARNING: {label} did not become healthy within {timeout}s")
    return False


def http_post_json(url: str, data: dict) -> dict | None:
    """Simple JSON POST using stdlib."""
    body = json.dumps(data).encode()
    req = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        resp = urlopen(req, timeout=5)
        return json.loads(resp.read())
    except Exception as e:
        log(f"POST {url} failed: {e}")
        return None


def start_process(name: str, cmd: list[str], cwd: Path | None = None) -> subprocess.Popen:
    """Launch a subprocess with stdout/stderr redirected to log files."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stdout_f = open(LOG_DIR / f"{name}.log", "a")
    stderr_f = open(LOG_DIR / f"{name}.err.log", "a")
    ts = datetime.now().isoformat()
    stdout_f.write(f"\n--- started {ts} ---\n")
    stdout_f.flush()

    env = os.environ.copy()
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=stdout_f,
        stderr=stderr_f,
        env=env,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )
    log(f"Started {name} (PID {proc.pid})")
    return proc


def write_pid_file() -> None:
    PID_DIR.mkdir(parents=True, exist_ok=True)
    pids = {name: proc.pid for name, proc in children.items()}
    PID_FILE.write_text(json.dumps(pids, indent=2))
    log(f"PID file written: {PID_FILE}")


def kill_from_pid_file() -> None:
    """Read PID file and kill all listed processes."""
    if not PID_FILE.exists():
        print("No PID file found. Are the services running?")
        sys.exit(1)

    pids = json.loads(PID_FILE.read_text())
    for name, pid in pids.items():
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
            else:
                os.kill(pid, signal.SIGTERM)
            print(f"Killed {name} (PID {pid})")
        except (OSError, ProcessLookupError):
            print(f"{name} (PID {pid}) — already stopped")

    PID_FILE.unlink(missing_ok=True)
    print("All services stopped.")


def shutdown_children() -> None:
    """Gracefully terminate all child processes."""
    log("Shutting down services...")
    for name, proc in children.items():
        if proc.poll() is None:
            try:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/PID", str(proc.pid)], capture_output=True)
                else:
                    proc.terminate()
                log(f"  Sent SIGTERM to {name} (PID {proc.pid})")
            except OSError:
                pass

    # Wait up to 5s for graceful exit, then force-kill
    deadline = time.time() + 5
    for name, proc in children.items():
        remaining = max(0, deadline - time.time())
        try:
            proc.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            log(f"  Force-killing {name}")
            proc.kill()

    PID_FILE.unlink(missing_ok=True)
    log("All services stopped.")


def pid_alive(proc: subprocess.Popen) -> bool:
    return proc.poll() is None


# ---------------------------------------------------------------------------
# Main startup
# ---------------------------------------------------------------------------

def start_all() -> None:
    global children

    print("=" * 56)
    print("  FactoryLM Service Orchestrator")
    print("=" * 56)
    print()

    # 0. Pre-checks
    if not PLC_READER.exists():
        print(f"ERROR: plc_reader.py not found at {PLC_READER}")
        print("  Set FACTORYLM_CORE env var to the factorylm-core directory.")
        sys.exit(1)

    # 1. Detect PLC IP
    log("Detecting PLC IP...")
    plc_ip = detect_plc_ip()
    print()

    # 2. Start Matrix on port 8002
    log("Starting Matrix on port 8002...")
    matrix_proc = start_process(
        "matrix",
        [sys.executable, "-m", "uvicorn", "services.matrix.app:app",
         "--host", "0.0.0.0", "--port", str(MATRIX_PORT)],
        cwd=REPO_ROOT,
    )
    children["matrix"] = matrix_proc

    # 3. Wait for Matrix health
    wait_for_health(f"http://localhost:{MATRIX_PORT}/api/health", "Matrix")

    # 4. Start plc-modbus on port 8001
    log("Starting plc-modbus on port 8001...")
    plc_modbus_proc = start_process(
        "plc_modbus",
        [sys.executable, "-m", "uvicorn", "backend.main:app",
         "--host", "0.0.0.0", "--port", str(PLC_MODBUS_PORT)],
        cwd=PLC_MODBUS_DIR,
    )
    children["plc_modbus"] = plc_modbus_proc

    # 5. Wait for plc-modbus health
    wait_for_health(f"http://localhost:{PLC_MODBUS_PORT}/api/health", "plc-modbus")

    # 6. Auto-connect plc-modbus to PLC
    log(f"Connecting plc-modbus to PLC at {plc_ip}...")
    result = http_post_json(
        f"http://localhost:{PLC_MODBUS_PORT}/api/plc/connect",
        {"ip": plc_ip, "port": MODBUS_PORT},
    )
    if result:
        log(f"PLC connect result: {result}")
    print()

    # 7. Start plc_reader
    log("Starting plc_reader...")
    reader_proc = start_process(
        "plc_reader",
        [sys.executable, str(PLC_READER),
         "--host", plc_ip,
         "--matrix", f"http://localhost:{MATRIX_PORT}"],
        cwd=CORE_DIR,
    )
    children["plc_reader"] = reader_proc

    # 8. Write PID file
    write_pid_file()

    # 9. Print status summary
    print()
    print("=" * 56)
    log("All services started!")
    print(f"  PLC IP:       {plc_ip}")
    print(f"  Matrix:       http://localhost:{MATRIX_PORT}/")
    print(f"  plc-modbus:   http://localhost:{PLC_MODBUS_PORT}/api/docs")
    print(f"  plc_reader:   running (logs: {LOG_DIR / 'plc_reader.log'})")
    print(f"  PID file:     {PID_FILE}")
    print("=" * 56)
    print()
    print("Press Ctrl+C to stop all services.")
    print()

    # 10. Health monitor loop
    try:
        while True:
            time.sleep(MONITOR_INTERVAL)
            statuses = []
            for name, proc in children.items():
                alive = pid_alive(proc)
                statuses.append(f"{name}:{'OK' if alive else 'DEAD'}")

                # Auto-restart plc_reader if it dies
                if not alive and name == "plc_reader":
                    log("plc_reader died — restarting...")
                    new_proc = start_process(
                        "plc_reader",
                        [sys.executable, str(PLC_READER),
                         "--host", plc_ip,
                         "--matrix", f"http://localhost:{MATRIX_PORT}"],
                        cwd=CORE_DIR,
                    )
                    children["plc_reader"] = new_proc
                    write_pid_file()

            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] {' | '.join(statuses)}")

    except KeyboardInterrupt:
        print()
        shutdown_children()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="FactoryLM Service Orchestrator")
    parser.add_argument("--stop", action="store_true", help="Stop running services via PID file")
    args = parser.parse_args()

    if args.stop:
        kill_from_pid_file()
    else:
        # Register signal handler for clean shutdown
        if sys.platform != "win32":
            signal.signal(signal.SIGTERM, lambda *_: shutdown_children())
        start_all()


if __name__ == "__main__":
    main()
