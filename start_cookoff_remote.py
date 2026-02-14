"""
FactoryLM Cosmos Cookoff - Remote Startup (PLC Laptop)
======================================================
Runs demo on PLC laptop (100.72.2.99) via SSH from travel laptop.

Usage:
    python start_cookoff_remote.py              # Full demo on PLC laptop
    python start_cookoff_remote.py --check      # Check PLC laptop status
    python start_cookoff_remote.py --live       # Run live test on PLC laptop
"""

import argparse
import subprocess
import sys
import os

PLC_HOST = os.getenv("PLC_HOST", "100.72.2.99")
NVIDIA_API_KEY = os.getenv("NVIDIA_COSMOS_API_KEY", "")


def ssh_cmd(cmd, interactive=False):
    """Run command on PLC laptop via SSH."""
    ssh_command = ["ssh", PLC_HOST, cmd]
    if interactive:
        return subprocess.run(ssh_command)
    else:
        result = subprocess.run(ssh_command, capture_output=True, text=True, timeout=30)
        return result.returncode == 0, result.stdout + result.stderr


def check_plc_status():
    """Check status of PLC laptop."""
    print(f"\n{'='*60}")
    print(f"PLC LAPTOP STATUS ({PLC_HOST})")
    print('='*60)

    # Check Factory I/O
    ok, out = ssh_cmd('powershell -Command "Get-Process | Where-Object {$_.Name -like \'*Factory*\'} | Select-Object Name, Id"')
    if ok and "Factory" in out:
        print("[OK] Factory I/O: Running")
    else:
        print("[X] Factory I/O: Not running")

    # Check PLC API
    ok, out = ssh_cmd('powershell -Command "Invoke-RestMethod -Uri http://localhost:8000/api/health"')
    if ok and "healthy" in out.lower():
        print("[OK] PLC API: Running on :8000")
    else:
        print("[X] PLC API: Not running")

    # Check Modbus connection
    ok, out = ssh_cmd('powershell -Command "netstat -an | Select-String \':502\'"')
    if ok and "ESTABLISHED" in out:
        print("[OK] Modbus: Connected to Factory I/O")
    else:
        print("[?] Modbus: No established connection")

    # Check if repo exists
    ok, out = ssh_cmd('powershell -Command "Test-Path C:\\Users\\hharp\\Desktop\\factorylm-monorepo\\cosmos"')
    if ok and "True" in out:
        print("[OK] Repo: Found at C:\\Users\\hharp\\Desktop\\factorylm-monorepo")
    else:
        print("[X] Repo: cosmos folder not found")

    print('='*60 + "\n")


def update_repo():
    """Pull latest code on PLC laptop."""
    print("[>] Updating repo on PLC laptop...")
    ok, out = ssh_cmd('powershell -Command "Set-Location C:\\Users\\hharp\\Desktop\\factorylm-monorepo; & \'C:\\Users\\hharp\\AppData\\Local\\GitHubDesktop\\app-3.5.4\\resources\\app\\git\\cmd\\git.exe\' pull --ff-only"')
    if ok:
        print("[OK] Repo updated")
    else:
        print(f"[!] Git pull failed: {out[:200]}")


def run_live_test_remote():
    """Run live test on PLC laptop."""
    print(f"\n{'='*60}")
    print("Running live test on PLC laptop...")
    print('='*60 + "\n")

    # Set API key and run test
    key_part = f"$env:NVIDIA_COSMOS_API_KEY = '{NVIDIA_API_KEY}'; " if NVIDIA_API_KEY else ""
    cmd = f'''powershell -Command "{key_part}Set-Location C:\\Users\\hharp\\Desktop\\factorylm-monorepo; python cosmos/live_test.py"'''
    ssh_cmd(cmd, interactive=True)


def start_bridge_remote():
    """Start bridge on PLC laptop (connects to local Factory I/O)."""
    print("[>] Starting bridge on PLC laptop...")
    cmd = '''powershell -Command "
        Start-Process python -ArgumentList 'sim/factoryio_bridge.py','--plc-host','127.0.0.1','--interval','1000' -WorkingDirectory 'C:\\Users\\hharp\\Desktop\\factorylm-monorepo'
    "'''
    ok, out = ssh_cmd(cmd)
    if ok:
        print("[OK] Bridge started on PLC laptop")
    else:
        print(f"[!] Failed to start bridge: {out[:200]}")


def main():
    parser = argparse.ArgumentParser(description="Remote startup for PLC laptop")
    parser.add_argument("--check", action="store_true", help="Check PLC laptop status")
    parser.add_argument("--live", action="store_true", help="Run live test on PLC laptop")
    parser.add_argument("--update", action="store_true", help="Update repo on PLC laptop")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"FACTORYLM COSMOS COOKOFF - REMOTE ({PLC_HOST})")
    print('='*60)

    if args.check:
        check_plc_status()
        return

    if args.update:
        update_repo()
        return

    if args.live:
        run_live_test_remote()
        return

    # Default: check status then run live test
    check_plc_status()

    print("Press Enter to run live test on PLC laptop, or Ctrl+C to exit...")
    try:
        input()
        run_live_test_remote()
    except KeyboardInterrupt:
        print("\nExiting.")


if __name__ == "__main__":
    main()
