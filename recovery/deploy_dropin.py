#!/usr/bin/env python3
"""
deploy_dropin.py — Drop-in replacer for CCW project files.

Backs up the entire CCW project, then copies:
  - Micro820_Complete_Program.st -> Prog2.stf
  - MbSrvConf_v2.xml -> MbSrvConf.xml

After running this, open CCW, add variables, set IP, rebuild, download.
"""

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

# --- Paths ---
RECOVERY_DIR = Path(__file__).parent
CCW_PROJECT = Path(r"C:\Users\hharp\Documents\CCW\Cosmos_Demo_v1.0")
PROG2_TARGET = CCW_PROJECT / "Controller" / "Controller" / "Micro820" / "Micro820" / "Prog2.stf"
MBSRV_TARGET = CCW_PROJECT / "Controller" / "Controller" / "MbSrvConf.xml"

SRC_PROGRAM = RECOVERY_DIR / "Micro820_Complete_Program.st"
SRC_MODBUS = RECOVERY_DIR / "MbSrvConf_v2.xml"


def _ignore_tmp(directory, files):
    """Skip .tmp and lock files that CCW may hold open."""
    return [f for f in files if f.endswith(('.tmp', '.lock', '.ldb'))]


def main():
    print("=" * 60)
    print("  Micro820 v2.0 Drop-In Deploy")
    print("=" * 60)

    # Verify source files exist
    for src in [SRC_PROGRAM, SRC_MODBUS]:
        if not src.exists():
            print(f"ERROR: Source file not found: {src}")
            sys.exit(1)

    # Verify CCW project exists
    if not CCW_PROJECT.exists():
        print(f"ERROR: CCW project not found at: {CCW_PROJECT}")
        print("  Is CCW installed and the project created?")
        sys.exit(1)

    # Step 1: Backup (skip locked temp files)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = RECOVERY_DIR / f"CCW_BACKUP_{timestamp}"
    print(f"\n[1/3] Backing up CCW project to:")
    print(f"      {backup_dir}")
    shutil.copytree(CCW_PROJECT, backup_dir, ignore=_ignore_tmp)
    print("      DONE")

    # Step 2: Copy program
    print(f"\n[2/3] Copying program -> Prog2.stf")
    print(f"      {SRC_PROGRAM.name} -> {PROG2_TARGET}")
    os.makedirs(PROG2_TARGET.parent, exist_ok=True)
    shutil.copy2(SRC_PROGRAM, PROG2_TARGET)
    print("      DONE")

    # Step 3: Copy Modbus config
    print(f"\n[3/3] Copying Modbus config -> MbSrvConf.xml")
    print(f"      {SRC_MODBUS.name} -> {MBSRV_TARGET}")
    os.makedirs(MBSRV_TARGET.parent, exist_ok=True)
    shutil.copy2(SRC_MODBUS, MBSRV_TARGET)
    print("      DONE")

    # Summary
    print("\n" + "=" * 60)
    print("  ALL FILES DEPLOYED")
    print("=" * 60)
    print()
    print("  Next steps in CCW:")
    print("  1. Open project: Cosmos_Demo_v1.0")
    print("  2. Add 16 new variables (see CCW_NEW_VARIABLES.txt)")
    print("  3. Set static IP: 192.168.1.100 / 255.255.255.0")
    print("  4. Rebuild (Ctrl+Shift+B)")
    print("  5. Download to PLC")
    print("  6. Switch to RUN mode")
    print()
    print(f"  Backup saved at: {backup_dir}")
    print()


if __name__ == "__main__":
    main()
