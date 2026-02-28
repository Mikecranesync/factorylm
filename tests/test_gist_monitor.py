#!/usr/bin/env python3
"""Monitor validation for Feature 002 — CMMS Gist Work Orders.

Read-only script that validates all real [Jarvis Work Order] Gists.
Does NOT create, modify, or delete anything.

Usage:
    python3 tests/test_gist_monitor.py          # interactive
    python3 tests/test_gist_monitor.py --ci      # exit code 0/1
"""

import argparse
import csv
import io
import subprocess
import sys
from datetime import datetime

EXPECTED_CSV_COLS = 25
REQUIRED_MD_SECTIONS = ["## Summary", "## Details", "## Attachments"]


def run_gh(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a gh CLI command and return result."""
    result = subprocess.run(
        ["gh"] + args, capture_output=True, text=True
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {result.stderr}")
    return result


def find_work_order_gists() -> list[dict]:
    """List all [Jarvis Work Order] Gists, excluding WO-TEST ones."""
    result = run_gh(["gist", "list", "--limit", "50"])
    gists = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        if "[Jarvis Work Order]" in line and "WO-TEST" not in line:
            parts = line.split("\t")
            if len(parts) >= 2:
                gists.append({"id": parts[0].strip(), "description": parts[1].strip()})
    return gists


def validate_gist(gist_id: str, description: str) -> dict:
    """Validate a single work order Gist. Returns health report."""
    issues = []

    # Check files
    result = run_gh(["gist", "view", gist_id, "--files"], check=False)
    if result.returncode != 0:
        return {"gist_id": gist_id, "healthy": False, "issues": ["Cannot view Gist"]}

    files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    if len(files) != 3:
        issues.append(f"Expected 3 files, got {len(files)}: {files}")

    # Check CSV (--raw for unrendered output)
    csv_result = run_gh(["gist", "view", gist_id, "-f", "work-order.csv", "--raw"], check=False)
    if csv_result.returncode == 0:
        try:
            reader = csv.reader(io.StringIO(csv_result.stdout))
            header = next(reader)
            if len(header) != EXPECTED_CSV_COLS:
                issues.append(f"CSV: {len(header)} columns (expected {EXPECTED_CSV_COLS})")
        except StopIteration:
            issues.append("CSV: empty file")
    else:
        issues.append("CSV: file not found")

    # Check MD (--raw for unrendered source)
    md_result = run_gh(["gist", "view", gist_id, "-f", "work-order.md", "--raw"], check=False)
    if md_result.returncode == 0:
        for section in REQUIRED_MD_SECTIONS:
            if section not in md_result.stdout:
                issues.append(f"MD missing: {section}")
    else:
        issues.append("MD: file not found")

    return {
        "gist_id": gist_id,
        "description": description,
        "healthy": len(issues) == 0,
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description="Monitor validation for work order Gists")
    parser.add_argument("--ci", action="store_true", help="CI mode: exit 0/1")
    args = parser.parse_args()

    print("=" * 60)
    print("Feature 002 — Work Order Gist Monitor Validation")
    print("=" * 60)

    # Find Gists
    print("\nScanning for [Jarvis Work Order] Gists...")
    gists = find_work_order_gists()
    print(f"Found {len(gists)} work order Gist(s)")

    if not gists:
        print("\nNo work order Gists found. Nothing to validate.")
        print("STATUS: HEALTHY (empty)")
        if args.ci:
            sys.exit(0)
        return

    # Validate each
    results = []
    for g in gists:
        print(f"\n  Validating {g['id']} — {g['description'][:50]}...")
        report = validate_gist(g["id"], g["description"])
        results.append(report)
        status = "HEALTHY" if report["healthy"] else "DEGRADED"
        print(f"    {status}", end="")
        if report["issues"]:
            print(f" — {report['issues']}")
        else:
            print()

    # Summary
    healthy = sum(1 for r in results if r["healthy"])
    degraded = len(results) - healthy

    print("\n" + "=" * 60)
    print(f"TOTAL: {len(results)} Gist(s)")
    print(f"HEALTHY: {healthy}")
    print(f"DEGRADED: {degraded}")
    overall = "HEALTHY" if degraded == 0 else "DEGRADED"
    print(f"STATUS: {overall}")
    print("=" * 60)

    if args.ci:
        sys.exit(0 if overall == "HEALTHY" else 1)


if __name__ == "__main__":
    main()
