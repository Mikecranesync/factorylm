"""
FactoryLM Cosmos Cookoff - Startup Script
==========================================
Starts all components for the demo:
1. Docker/Postgres (if available)
2. Factory I/O Bridge
3. Cosmos/Llama analysis

Usage:
    python start_cookoff.py              # Full stack
    python start_cookoff.py --live-only  # Just live test (no Docker)
    python start_cookoff.py --check      # Check status only
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

# Configuration
PLC_HOST = os.getenv("PLC_HOST", "100.72.2.99")
REPO_ROOT = Path(__file__).parent
DOCKER_COMPOSE = REPO_ROOT / "infra" / "local" / "docker-compose.yml"


def run_cmd(cmd, check=False, timeout=30):
    """Run a command and return (success, output)."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)


def check_docker():
    """Check if Docker is running."""
    ok, out = run_cmd("docker ps", timeout=10)
    return ok


def check_plc():
    """Check if PLC API is reachable."""
    import httpx
    try:
        resp = httpx.get(f"http://{PLC_HOST}:8000/api/health", timeout=5)
        return resp.status_code == 200
    except:
        return False


def check_postgres():
    """Check if Postgres container is running."""
    ok, out = run_cmd("docker ps --filter name=factorylm-postgres -q", timeout=10)
    return ok and out.strip() != ""


def start_docker():
    """Start Docker Compose stack."""
    print("[>] Starting Docker/Postgres...")
    ok, out = run_cmd(f"docker-compose -f {DOCKER_COMPOSE} up -d", timeout=60)
    if ok:
        print("[OK] Docker stack started")
    else:
        print(f"[!] Docker failed: {out[:200]}")
    return ok


def start_bridge():
    """Start the Factory I/O bridge in background."""
    print(f"[>] Starting bridge to {PLC_HOST}...")
    bridge_script = REPO_ROOT / "sim" / "factoryio_bridge.py"

    # Start in background
    if sys.platform == "win32":
        subprocess.Popen(
            ["python", str(bridge_script), "--plc-host", PLC_HOST, "--interval", "1000"],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            cwd=str(REPO_ROOT),
        )
    else:
        subprocess.Popen(
            ["python", str(bridge_script), "--plc-host", PLC_HOST, "--interval", "1000"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            cwd=str(REPO_ROOT),
        )
    print("[OK] Bridge started in new window")
    return True


def run_live_test():
    """Run the live test directly."""
    print("\n" + "=" * 60)
    print("Running live Factory I/O -> Cosmos/Llama test...")
    print("=" * 60 + "\n")

    live_test = REPO_ROOT / "cosmos" / "live_test.py"
    subprocess.run([sys.executable, str(live_test)], cwd=str(REPO_ROOT))


def show_status():
    """Show current status of all components."""
    print("\n" + "=" * 60)
    print("COSMOS COOKOFF STATUS")
    print("=" * 60)

    # Docker
    docker_ok = check_docker()
    print(f"  Docker:     {'[OK] Running' if docker_ok else '[X] Not running'}")

    # Postgres
    if docker_ok:
        pg_ok = check_postgres()
        print(f"  Postgres:   {'[OK] Running' if pg_ok else '[X] Not running'}")
    else:
        print("  Postgres:   [?] Unknown (Docker not running)")

    # PLC
    plc_ok = check_plc()
    print(f"  PLC API:    {'[OK] ' + PLC_HOST + ':8000' if plc_ok else '[X] Not reachable'}")

    # API Key
    api_key = os.environ.get("NVIDIA_COSMOS_API_KEY")
    if api_key:
        print(f"  API Key:    [OK] {api_key[:20]}...")
    else:
        print("  API Key:    [!] Not set (will use stub)")

    print("=" * 60 + "\n")

    return docker_ok, plc_ok


def main():
    parser = argparse.ArgumentParser(description="FactoryLM Cosmos Cookoff Startup")
    parser.add_argument("--live-only", action="store_true", help="Skip Docker, run live test only")
    parser.add_argument("--check", action="store_true", help="Check status only")
    parser.add_argument("--no-bridge", action="store_true", help="Don't start bridge")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("FACTORYLM COSMOS COOKOFF")
    print("=" * 60)

    # Status check only
    if args.check:
        show_status()
        return

    # Check PLC first
    print(f"\n[>] Checking PLC API at {PLC_HOST}:8000...")
    if check_plc():
        print("[OK] PLC API reachable")
    else:
        print("[!] PLC API not reachable - Factory I/O may not be running")
        print("    Make sure Factory I/O is running on the PLC laptop")

    # Live only mode
    if args.live_only:
        print("\n[>] Live-only mode (skipping Docker)")
        run_live_test()
        return

    # Full stack mode
    print("\n[>] Starting full stack...")

    # Docker
    if check_docker():
        print("[OK] Docker already running")
        if not check_postgres():
            start_docker()
    else:
        print("[!] Docker not running - skipping Postgres")
        print("    Run 'docker-compose -f infra/local/docker-compose.yml up -d' manually")

    # Bridge
    if not args.no_bridge:
        start_bridge()
        time.sleep(2)

    # Show status
    show_status()

    # Run live test
    print("\nPress Enter to run live test, or Ctrl+C to exit...")
    try:
        input()
        run_live_test()
    except KeyboardInterrupt:
        print("\nExiting.")


if __name__ == "__main__":
    main()
