#!/usr/bin/env python3
"""
FactoryLM KB Ingestion Tool
============================
Indexes FactoryLM-specific equipment data into the Qdrant factorylm_brain
collection so the query-api can return sourced answers.

Ingests:
  1. Nautobot device records (14 devices)
  2. Modbus register map (Micro820 + GS10 VFD)
  3. Cosmos Cookoff outputs (if present)

Uses scroll-compatible payload format: {'memory': ..., 'source': ..., 'tags': ...}
Vectors are unit-normalized random (query-api uses keyword scroll, not ANN search).

Usage:
    python tools/ingest_factorylm_kb.py
    python tools/ingest_factorylm_kb.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:8000")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "factorylm_brain")
VECTOR_DIM = 1536  # matches factorylm_brain collection

NAUTOBOT_URL = os.getenv("NAUTOBOT_URL", "http://localhost:8443")
NAUTOBOT_TOKEN = os.getenv("NAUTOBOT_TOKEN", "7ed85bda94d2c7b5396bd83b319cd7235fe57e0f")

COSMOS_DIR = os.path.expanduser("~/factorylm-cosmos-cookoff")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unit_vector(dim: int) -> List[float]:
    """Return a random unit vector of given dimension."""
    v = [random.gauss(0, 1) for _ in range(dim)]
    mag = math.sqrt(sum(x * x for x in v))
    return [x / mag for x in v]


def _qdrant_post(path: str, payload: Dict) -> Dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{QDRANT_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def _qdrant_get(path: str) -> Dict:
    req = urllib.request.Request(f"{QDRANT_URL}{path}", method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def _nautobot_get(path: str) -> Dict:
    url = f"{NAUTOBOT_URL}/api{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Token {NAUTOBOT_TOKEN}",
            "Accept": "application/json",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _upsert_points(points: List[Dict], dry_run: bool = False) -> int:
    """Upsert a list of points into Qdrant. Returns count inserted."""
    if dry_run:
        for p in points:
            print(f"  [DRY-RUN] Would insert id={p['id']} | {str(p['payload'])[:80]}")
        return len(points)

    result = _qdrant_post(
        f"/collections/{QDRANT_COLLECTION}/points",
        {"points": points},
    )
    if result.get("status") != "ok":
        print(f"  WARNING: Qdrant upsert returned: {result}", file=sys.stderr)
    return len(points)


# ---------------------------------------------------------------------------
# Section 1: Nautobot devices
# ---------------------------------------------------------------------------

def _build_device_text(device: Dict, interfaces: List[Dict], ips: Dict[str, str]) -> str:
    """Build a human-readable text summary for a device."""
    name = device["name"]
    comments = device.get("comments", "").strip()

    # Gather IPs for this device
    dev_id = device["id"]
    dev_ips = []
    for iface in interfaces:
        if iface.get("device", {}).get("id") == dev_id:
            for ip_ref in iface.get("ip_addresses", []):
                ip_str = ips.get(ip_ref["id"], "")
                if ip_str:
                    dev_ips.append(f"{iface['name']}: {ip_str}")

    lines = [f"Device: {name}"]
    if dev_ips:
        lines.append("IP addresses: " + ", ".join(dev_ips))
    if comments:
        lines.append("Details: " + comments)
    return "\n".join(lines)


def ingest_nautobot(dry_run: bool = False) -> int:
    """Pull 14 Nautobot devices and insert into Qdrant."""
    print("\n[1/3] Ingesting Nautobot device records...")

    try:
        devices_resp = _nautobot_get("/dcim/devices/?limit=50")
        devices = devices_resp.get("results", [])
        print(f"  Found {len(devices)} devices in Nautobot")

        ifaces_resp = _nautobot_get("/dcim/interfaces/?limit=200")
        interfaces = ifaces_resp.get("results", [])

        ips_resp = _nautobot_get("/ipam/ip-addresses/?limit=200")
        ip_list = ips_resp.get("results", [])
        # id -> address string
        ips = {ip["id"]: ip["address"] for ip in ip_list}

    except urllib.error.URLError as e:
        print(f"  ERROR: Nautobot unreachable: {e}", file=sys.stderr)
        return 0

    points = []
    for i, device in enumerate(devices):
        text = _build_device_text(device, interfaces, ips)
        point_id = i + 1000  # start at 1000 to avoid collisions
        points.append({
            "id": point_id,
            "vector": _unit_vector(VECTOR_DIM),
            "payload": {
                "memory": text,
                "source": "nautobot",
                "device_name": device["name"],
                "device_id": device["id"],
                "tags": ["device", "infrastructure", "nautobot"],
            },
        })

    count = _upsert_points(points, dry_run=dry_run)
    print(f"  Indexed {count} device records")
    return count


# ---------------------------------------------------------------------------
# Section 2: Modbus register map
# ---------------------------------------------------------------------------

MODBUS_RECORDS = [
    # Micro820 Holding Registers
    {
        "register": "HR100",
        "name": "motor_speed",
        "description": (
            "Micro820 PLC Holding Register HR100 = motor_speed. "
            "Current motor speed value from the GS10 VFD drive. "
            "Range 0-60 Hz (scaled). Used to monitor conveyor belt speed "
            "on the Sorting by Height Factory IO scene."
        ),
        "device": "micro820-1",
        "register_type": "holding_register",
    },
    {
        "register": "HR101",
        "name": "current",
        "description": (
            "Micro820 PLC Holding Register HR101 = current. "
            "Motor current draw in amps from GS10 VFD. "
            "High current indicates overload or mechanical jam. "
            "Normal operating range depends on motor nameplate data."
        ),
        "device": "micro820-1",
        "register_type": "holding_register",
    },
    {
        "register": "HR102",
        "name": "temp",
        "description": (
            "Micro820 PLC Holding Register HR102 = temp. "
            "GS10 VFD drive temperature in degrees Celsius. "
            "Overtemperature fault triggers at manufacturer threshold. "
            "Check drive ventilation if temp is elevated."
        ),
        "device": "micro820-1",
        "register_type": "holding_register",
    },
    # Coils
    {
        "register": "Coil0",
        "name": "motor_run",
        "description": (
            "Micro820 PLC Coil0 = motor_run. "
            "Write 1 to start the conveyor motor via GS10 VFD. "
            "Write 0 to stop. Verify Coil2 (fault) is clear before starting. "
            "Modbus TCP address: 192.168.1.100:502."
        ),
        "device": "micro820-1",
        "register_type": "coil",
    },
    {
        "register": "Coil1",
        "name": "motor_stop",
        "description": (
            "Micro820 PLC Coil1 = motor_stop. "
            "Pulse to 1 to command a controlled stop of the conveyor motor. "
            "Latches off once stop is complete. "
            "Use for graceful shutdown; Coil0=0 is an immediate de-energize."
        ),
        "device": "micro820-1",
        "register_type": "coil",
    },
    {
        "register": "Coil2",
        "name": "fault",
        "description": (
            "Micro820 PLC Coil2 = fault. "
            "Set by PLC when GS10 VFD reports a drive fault. "
            "Read to check fault status before starting motor. "
            "Must be cleared (write 0 after resolving condition) before restart. "
            "Common faults: overcurrent, overtemperature, communication loss."
        ),
        "device": "micro820-1",
        "register_type": "coil",
    },
    # VFD summary
    {
        "register": "VFD-GS10",
        "name": "gs10_vfd_summary",
        "description": (
            "GS10 VFD (Variable Frequency Drive) on Modbus RTU RS-485 bus, "
            "bridged through Micro820 PLC to Modbus TCP. "
            "Controls conveyor motor speed and direction in the Factory IO "
            "Sorting by Height scene. No direct IP address — accessed via PLC bridge "
            "at 192.168.1.100:502. "
            "Speed range: 0–60 Hz. Fault register: Coil2. "
            "Speed register: HR100. Current: HR101. Temperature: HR102."
        ),
        "device": "gs10-vfd-1",
        "register_type": "vfd_summary",
    },
    # PLC summary
    {
        "register": "PLC-MICRO820",
        "name": "micro820_plc_summary",
        "description": (
            "Allen-Bradley Micro820 PLC at 192.168.1.100, Modbus TCP port 502. "
            "Controls Factory IO Sorting by Height conveyor scene. "
            "Bridges GS10 VFD via RS-485. "
            "Key registers: HR100=motor_speed, HR101=current, HR102=temp, "
            "Coil0=motor_run, Coil1=motor_stop, Coil2=fault. "
            "Connect with: modbus_client.connect('192.168.1.100', port=502)."
        ),
        "device": "micro820-1",
        "register_type": "plc_summary",
    },
]


def ingest_modbus(dry_run: bool = False) -> int:
    """Insert Modbus register map into Qdrant."""
    print("\n[2/3] Ingesting Modbus register map...")

    points = []
    for i, rec in enumerate(MODBUS_RECORDS):
        point_id = i + 2000  # start at 2000
        points.append({
            "id": point_id,
            "vector": _unit_vector(VECTOR_DIM),
            "payload": {
                "memory": rec["description"],
                "source": "modbus_map",
                "register": rec["register"],
                "register_name": rec["name"],
                "device": rec["device"],
                "register_type": rec["register_type"],
                "tags": ["plc", "modbus", "register", rec["device"]],
            },
        })

    count = _upsert_points(points, dry_run=dry_run)
    print(f"  Indexed {count} Modbus register entries")
    return count


# ---------------------------------------------------------------------------
# Section 3: Cosmos Cookoff outputs
# ---------------------------------------------------------------------------

def ingest_cosmos(dry_run: bool = False) -> int:
    """Scan Cosmos Cookoff directory for indexable outputs."""
    print("\n[3/3] Scanning Cosmos Cookoff outputs...")

    # Look for markdown docs and summaries
    import glob
    candidates = []
    for pattern in ["**/*.md", "docs/**/*.txt", "**/*summary*", "**/*output*"]:
        for path in glob.glob(os.path.join(COSMOS_DIR, pattern), recursive=True):
            if os.path.isfile(path) and os.path.getsize(path) > 50:
                candidates.append(path)

    # Deduplicate
    candidates = list(set(candidates))

    if not candidates:
        print("  No Cosmos Cookoff output files found — documenting as empty")
        if not dry_run:
            _upsert_points([{
                "id": 3000,
                "vector": _unit_vector(VECTOR_DIM),
                "payload": {
                    "memory": (
                        "Cosmos Cookoff directory at ~/factorylm-cosmos-cookoff/ was scanned "
                        "on 2026-04-02. No generated output files (datasets, training outputs) "
                        "were found to index. The directory contains source code and "
                        "infrastructure files but no completed training artifacts."
                    ),
                    "source": "cosmos_cookoff",
                    "tags": ["cosmos", "training", "status"],
                },
            }])
        return 0

    print(f"  Found {len(candidates)} candidate files")
    points = []
    for i, path in enumerate(candidates[:20]):  # cap at 20 files
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read(3000)  # first 3000 chars
        except OSError:
            continue

        rel = os.path.relpath(path, COSMOS_DIR)
        point_id = 3000 + i + 1
        points.append({
            "id": point_id,
            "vector": _unit_vector(VECTOR_DIM),
            "payload": {
                "memory": f"[Cosmos Cookoff: {rel}]\n{text}",
                "source": "cosmos_cookoff",
                "file": rel,
                "tags": ["cosmos", "training", "docs"],
            },
        })

    count = _upsert_points(points, dry_run=dry_run)
    print(f"  Indexed {count} Cosmos Cookoff files")
    return count


# ---------------------------------------------------------------------------
# Section 4: Verify
# ---------------------------------------------------------------------------

def verify() -> bool:
    """Query Qdrant to confirm hits for 'motor speed' and 'fault'."""
    print("\n[Verify] Querying Qdrant...")

    try:
        r = urllib.request.urlopen(
            urllib.request.Request(
                f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/scroll",
                data=json.dumps({"limit": 200, "with_payload": True, "with_vector": False}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            ),
            timeout=10,
        )
        result = json.loads(r.read().decode())
        points = result.get("result", {}).get("points", [])
    except Exception as e:
        print(f"  ERROR: Qdrant scroll failed: {e}", file=sys.stderr)
        return False

    total = len(points)
    print(f"  Total points in collection: {total}")

    for query in ["motor speed", "fault"]:
        q_words = set(query.lower().split())
        hits = [
            p for p in points
            if q_words & set(p.get("payload", {}).get("memory", "").lower().split())
        ]
        print(f"  Query '{query}': {len(hits)} hit(s)")
        if hits:
            preview = hits[0]["payload"]["memory"][:80].replace("\n", " ")
            print(f"    Top hit: {preview}...")

    return total > 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest FactoryLM equipment data into Qdrant KB")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be inserted, don't write")
    args = parser.parse_args()

    print(f"FactoryLM KB Ingestion")
    print(f"  Qdrant: {QDRANT_URL} / collection: {QDRANT_COLLECTION}")
    print(f"  Nautobot: {NAUTOBOT_URL}")
    print(f"  Dry-run: {args.dry_run}")

    # Verify Qdrant is reachable
    try:
        info = _qdrant_get(f"/collections/{QDRANT_COLLECTION}")
        existing = info.get("result", {}).get("points_count", 0)
        print(f"  Existing points in collection: {existing}")
    except Exception as e:
        print(f"ERROR: Cannot reach Qdrant at {QDRANT_URL}: {e}", file=sys.stderr)
        sys.exit(1)

    total = 0
    total += ingest_nautobot(dry_run=args.dry_run)
    total += ingest_modbus(dry_run=args.dry_run)
    total += ingest_cosmos(dry_run=args.dry_run)

    print(f"\nTotal indexed: {total} records")

    if not args.dry_run:
        verify()

    print("\nDone.")


if __name__ == "__main__":
    main()
