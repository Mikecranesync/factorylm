#!/usr/bin/env python3
"""E2E Gist CRUD lifecycle test for Feature 002 — CMMS Gist Work Order.

Creates a test work order Gist, verifies its contents, updates it,
verifies the update, then cleans up. Follows live_bot_tester.py patterns.

Usage:
    python3 tests/test_gist_work_order_e2e.py          # interactive
    python3 tests/test_gist_work_order_e2e.py --ci      # exit code 0/1
    python3 tests/test_gist_work_order_e2e.py --keep     # don't delete test Gist
    python3 tests/test_gist_work_order_e2e.py --output results.json
"""

import argparse
import csv
import io
import json
import subprocess
import sys
import os
from datetime import datetime

# Ensure repo root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cmms.gist_work_order import (
    create_work_order_gist,
    update_work_order_gist,
)

TEST_METADATA = {
    "work_order_id": f"WO-TEST-{datetime.now().strftime('%H%M%S')}",
    "title": "[E2E TEST] Motor Bearing Check — Automated Test",
    "description": "Automated E2E test. Safe to delete.",
    "status": "open",
    "priority": "medium",
    "asset_name": "Test Asset",
    "asset_id": "TEST-001",
    "location": "Test Bay",
    "site": "CI Environment",
    "assigned_to": "Automated Tester",
    "work_type": "Preventive",
    "category": "Electrical",
    "channel": "CI",
    "reported_by": "E2E Script",
    "estimated_hours": "1",
    "failure_code": "TEST-000",
}

TEST_ATTACHMENTS = [
    {"type": "log", "description": "Test log file", "url": "https://example.com/test.log"},
]

REQUIRED_MD_SECTIONS = ["## Summary", "## Details", "## Attachments"]
EXPECTED_FILE_COUNT = 3
EXPECTED_CSV_COLS = 25


def run_gh(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a gh CLI command and return result."""
    result = subprocess.run(
        ["gh"] + args, capture_output=True, text=True
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {result.stderr}")
    return result


def preflight() -> dict:
    """Check gh auth status."""
    print("  [preflight] Checking gh auth status...")
    result = run_gh(["auth", "status"], check=False)
    if result.returncode != 0:
        return {"passed": False, "error": "gh auth failed — not logged in"}
    print("  [preflight] PASS — gh authenticated")
    return {"passed": True}


def step_create() -> dict:
    """Create a test work order Gist."""
    print("  [create] Creating test Gist...")
    result = create_work_order_gist(TEST_METADATA.copy(), TEST_ATTACHMENTS)
    gist_id = result["gist_id"]
    gist_url = result["gist_url"]
    print(f"  [create] PASS — {gist_url}")
    return {"passed": True, "gist_id": gist_id, "gist_url": gist_url}


def step_verify(gist_id: str) -> dict:
    """Verify the Gist has correct files and content."""
    print(f"  [verify] Checking Gist {gist_id}...")
    failures = []

    # Get Gist file list
    result = run_gh(["gist", "view", gist_id, "--files"])
    files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    print(f"  [verify] Files: {files}")

    if len(files) != EXPECTED_FILE_COUNT:
        failures.append(f"Expected {EXPECTED_FILE_COUNT} files, got {len(files)}")

    # Check CSV content (--raw for unrendered output)
    csv_result = run_gh(["gist", "view", gist_id, "-f", "work-order.csv", "--raw"])
    csv_text = csv_result.stdout
    reader = csv.reader(io.StringIO(csv_text))
    header = next(reader)
    if len(header) != EXPECTED_CSV_COLS:
        failures.append(f"CSV: expected {EXPECTED_CSV_COLS} columns, got {len(header)}")

    # Check MD content (--raw for unrendered source)
    md_result = run_gh(["gist", "view", gist_id, "-f", "work-order.md", "--raw"])
    md_text = md_result.stdout
    for section in REQUIRED_MD_SECTIONS:
        if section not in md_text:
            failures.append(f"MD missing section: {section}")

    if TEST_METADATA["work_order_id"] not in md_text:
        failures.append("MD missing work_order_id")

    if failures:
        print(f"  [verify] FAIL — {failures}")
        return {"passed": False, "failures": failures}

    print("  [verify] PASS — 3 files, 25 CSV cols, MD sections present")
    return {"passed": True}


def step_update(gist_id: str) -> dict:
    """Update the Gist: change status to completed, add notes."""
    print(f"  [update] Updating Gist {gist_id}...")
    meta = TEST_METADATA.copy()
    meta["status"] = "completed"
    meta["completion_notes"] = "E2E test completed successfully."
    meta["completed_date"] = datetime.now().isoformat()
    meta["completed_by"] = "E2E Script"

    update_work_order_gist(gist_id, meta, TEST_ATTACHMENTS)

    # Verify update took effect (--raw for unrendered source)
    md_result = run_gh(["gist", "view", gist_id, "-f", "work-order.md", "--raw"])
    md_text = md_result.stdout

    failures = []
    if "completed" not in md_text.lower():
        failures.append("Update: 'completed' not found in MD after update")
    if "E2E test completed successfully" not in md_text:
        failures.append("Update: completion_notes not found in MD")

    csv_result = run_gh(["gist", "view", gist_id, "-f", "work-order.csv", "--raw"])
    if "completed" not in csv_result.stdout.lower():
        failures.append("Update: 'completed' not found in CSV after update")

    if failures:
        print(f"  [update] FAIL — {failures}")
        return {"passed": False, "failures": failures}

    print("  [update] PASS — status=completed, notes present")
    return {"passed": True}


def step_delete(gist_id: str) -> dict:
    """Delete the test Gist."""
    print(f"  [delete] Deleting Gist {gist_id}...")
    result = run_gh(["gist", "delete", gist_id], check=False)
    if result.returncode != 0:
        print(f"  [delete] FAIL — {result.stderr}")
        return {"passed": False, "error": result.stderr}

    # Verify deletion
    verify = run_gh(["gist", "view", gist_id], check=False)
    if verify.returncode == 0:
        print("  [delete] FAIL — Gist still exists after delete")
        return {"passed": False, "error": "Gist still accessible"}

    print("  [delete] PASS — Gist deleted")
    return {"passed": True}


def main():
    parser = argparse.ArgumentParser(description="E2E Gist CRUD lifecycle test")
    parser.add_argument("--ci", action="store_true", help="CI mode: exit 0/1")
    parser.add_argument("--keep", action="store_true", help="Don't delete test Gist")
    parser.add_argument("--output", type=str, help="Write JSON results to file")
    args = parser.parse_args()

    print("=" * 60)
    print("Feature 002 — E2E Gist CRUD Lifecycle Test")
    print("=" * 60)

    results = {
        "timestamp": datetime.now().isoformat(),
        "steps": {},
        "overall": "pending",
    }
    gist_id = None

    try:
        # Preflight
        pf = preflight()
        results["steps"]["preflight"] = pf
        if not pf["passed"]:
            results["overall"] = "fail"
            _finish(results, args)
            return

        # Create
        cr = step_create()
        results["steps"]["create"] = cr
        if not cr["passed"]:
            results["overall"] = "fail"
            _finish(results, args)
            return
        gist_id = cr["gist_id"]

        # Verify
        vr = step_verify(gist_id)
        results["steps"]["verify"] = vr

        # Update
        ur = step_update(gist_id)
        results["steps"]["update"] = ur

        # Determine pass/fail before cleanup
        all_passed = all(
            s.get("passed", False)
            for s in [cr, vr, ur]
        )
        results["overall"] = "pass" if all_passed else "fail"

    finally:
        # Cleanup
        if gist_id and not args.keep:
            dr = step_delete(gist_id)
            results["steps"]["delete"] = dr
            if not dr.get("passed"):
                print(f"\n  *** LEAKED GIST: {gist_id} — delete manually! ***")
                results["overall"] = "fail"
        elif gist_id and args.keep:
            print(f"\n  [keep] Gist retained: https://gist.github.com/{gist_id}")
            results["steps"]["delete"] = {"passed": True, "skipped": True}

    _finish(results, args)


def _finish(results: dict, args):
    """Print summary and exit."""
    print("\n" + "=" * 60)
    print("RESULTS:")
    for step_name, step_result in results["steps"].items():
        status = "PASS" if step_result.get("passed") else "FAIL"
        print(f"  {step_name}: {status}")
    print(f"\nOVERALL: {results['overall'].upper()}")
    print("=" * 60)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Results written to {args.output}")

    if args.ci:
        sys.exit(0 if results["overall"] == "pass" else 1)


if __name__ == "__main__":
    main()
