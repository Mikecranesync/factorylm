#!/usr/bin/env python3
"""
FactoryLM Smoke Test — End-to-End Cosmos Cookoff Pipeline
==========================================================
Starts the Matrix API on port 8100 with a temp database, pushes tags
(normal + faulted), runs CosmosClient.analyze_incident(), posts the
resulting insight, and verifies the full round-trip.

Run: python scripts/smoke_test.py
"""

import dataclasses
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure repo root is importable
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import httpx  # noqa: E402
from cosmos.client import CosmosClient  # noqa: E402

MATRIX_PORT = 8100
MATRIX_URL = f"http://127.0.0.1:{MATRIX_PORT}"
DB_PATH = REPO_ROOT / "smoke_test_temp.db"

NORMAL_TAGS = {
    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    "node_id": "smoke-test-node",
    "motor_running": True,
    "motor_speed": 60,
    "motor_current": 3.2,
    "temperature": 42.5,
    "pressure": 85,
    "conveyor_running": True,
    "conveyor_speed": 50,
    "sensor_1": False,
    "sensor_2": False,
    "fault_alarm": False,
    "e_stop": False,
    "error_code": 0,
    "error_message": "",
}

FAULT_TAGS = {
    **NORMAL_TAGS,
    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    "fault_alarm": True,
    "error_code": 3,
    "error_message": "Conveyor jam",
    "conveyor_speed": 0,
    "motor_current": 8.7,
}


def print_header(text: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print("=" * 60)


def print_step(num: int, text: str) -> None:
    print(f"\n[STEP {num}] {text}")
    print("-" * 50)


def main() -> int:
    start_time = time.time()
    results: dict[int, tuple[str, bool]] = {}
    proc = None

    print_header("FACTORYLM SMOKE TEST — Cosmos Cookoff Pipeline")
    print(f"  Timestamp : {datetime.now().isoformat()}")
    print(f"  Matrix URL: {MATRIX_URL}")
    print(f"  Temp DB   : {DB_PATH}")

    try:
        # =================================================================
        # STEP 1: Start the Matrix API as a subprocess
        # =================================================================
        print_step(1, "START MATRIX API")

        env = {**os.environ, "MATRIX_DB_PATH": str(DB_PATH)}
        proc = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "services.matrix.app:app",
                "--host", "127.0.0.1",
                "--port", str(MATRIX_PORT),
            ],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        print(f"  PID: {proc.pid}")

        # Poll /api/health until ready (up to 10 s)
        healthy = False
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                r = httpx.get(f"{MATRIX_URL}/api/health", timeout=2)
                if r.status_code == 200:
                    print(f"  Health: {r.json()}")
                    healthy = True
                    break
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            time.sleep(0.5)

        if not healthy:
            print("  [FAIL] Matrix API did not become healthy within 10 s")
            results[1] = ("Start Matrix API", False)
            return _summary(results, start_time)

        results[1] = ("Start Matrix API", True)

        # =================================================================
        # STEP 2: POST normal tag snapshot (no fault)
        # =================================================================
        print_step(2, "POST NORMAL TAG SNAPSHOT")

        r = httpx.post(f"{MATRIX_URL}/api/tags", json=NORMAL_TAGS, timeout=5)
        r.raise_for_status()
        body = r.json()
        print(f"  tag_id     : {body['tag_id']}")
        print(f"  incident_id: {body['incident_id']}  (expected: None)")
        ok = body["incident_id"] is None
        if not ok:
            print("  [FAIL] Incident created for normal tags — unexpected")
        results[2] = ("POST normal tags", ok)

        # =================================================================
        # STEP 3: POST faulted tag snapshot — expect incident creation
        # =================================================================
        print_step(3, "POST FAULTED TAG SNAPSHOT")

        r = httpx.post(f"{MATRIX_URL}/api/tags", json=FAULT_TAGS, timeout=5)
        r.raise_for_status()
        body = r.json()
        fault_tag_id = body["tag_id"]
        incident_id = body["incident_id"]
        print(f"  tag_id     : {fault_tag_id}")
        print(f"  incident_id: {incident_id}")
        ok = incident_id is not None
        if not ok:
            print("  [FAIL] No incident created for faulted tags")
            results[3] = ("POST fault tags — incident created", False)
            return _summary(results, start_time)
        print(f"  [OK] Incident #{incident_id} created for Conveyor jam")
        results[3] = ("POST fault tags — incident created", True)

        # =================================================================
        # STEP 4: Call CosmosClient.analyze_incident() directly
        # =================================================================
        print_step(4, "COSMOS ANALYZE INCIDENT")

        cosmos = CosmosClient()
        ai_start = time.time()
        insight = cosmos.analyze_incident(
            incident_id=str(incident_id),
            node_id=FAULT_TAGS["node_id"],
            tags=FAULT_TAGS,
            context="Smoke test — automated pipeline verification",
        )
        ai_time = time.time() - ai_start

        print(f"  Model      : {insight.cosmos_model}")
        print(f"  Latency    : {ai_time:.2f}s")
        print(f"  Summary    : {insight.summary}")
        print(f"  Root Cause : {insight.root_cause}")
        print(f"  Confidence : {insight.confidence:.0%}")
        print(f"  Checks     : {len(insight.suggested_checks)}")

        ok = bool(insight.summary and insight.root_cause and insight.confidence > 0)
        results[4] = ("Cosmos analyze_incident()", ok)

        # =================================================================
        # STEP 5: POST insight to Matrix API
        # =================================================================
        print_step(5, "POST INSIGHT TO MATRIX API")

        insight_payload = {
            "incident_id": incident_id,
            "summary": insight.summary,
            "root_cause": insight.root_cause,
            "confidence": insight.confidence,
            "reasoning": insight.reasoning,
            "suggested_checks": insight.suggested_checks,
            "video_url": insight.video_url,
            "cosmos_model": insight.cosmos_model,
        }
        r = httpx.post(f"{MATRIX_URL}/api/insights", json=insight_payload, timeout=5)
        r.raise_for_status()
        body = r.json()
        insight_id = body.get("insight_id")
        print(f"  insight_id : {insight_id}")
        ok = insight_id is not None
        results[5] = ("POST insight", ok)

        # =================================================================
        # STEP 6: GET incident and verify cosmos_insight attached
        # =================================================================
        print_step(6, "VERIFY INCIDENT HAS COSMOS INSIGHT")

        r = httpx.get(f"{MATRIX_URL}/api/incidents/{incident_id}", timeout=5)
        r.raise_for_status()
        inc = r.json()
        ci = inc.get("cosmos_insight")
        print(f"  status       : {inc.get('status')}")
        print(f"  has insight  : {ci is not None}")
        if ci:
            print(f"  ci.summary   : {ci.get('summary', '')[:80]}")
            print(f"  ci.confidence: {ci.get('confidence')}")

        ok = ci is not None and ci.get("summary") == insight.summary
        results[6] = ("Incident has cosmos_insight", ok)

    except Exception as exc:
        step = max(results.keys()) + 1 if results else 1
        print(f"\n  [EXCEPTION at step {step}] {exc}")
        results[step] = (f"Exception: {exc}", False)

    finally:
        # =================================================================
        # CLEANUP
        # =================================================================
        print_step(7, "CLEANUP")

        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            print(f"  Matrix API (PID {proc.pid}) terminated")

        if DB_PATH.exists():
            DB_PATH.unlink()
            print(f"  Deleted {DB_PATH.name}")

        # Also clean up WAL/SHM files if they exist
        for suffix in ("-wal", "-shm"):
            p = DB_PATH.with_name(DB_PATH.name + suffix)
            if p.exists():
                p.unlink()

    return _summary(results, start_time)


def _summary(results: dict[int, tuple[str, bool]], start_time: float) -> int:
    total_time = time.time() - start_time
    passed = sum(1 for _, ok in results.values() if ok)
    failed = sum(1 for _, ok in results.values() if not ok)

    print_header("SMOKE TEST SUMMARY")

    for step in sorted(results):
        label, ok = results[step]
        icon = "PASS" if ok else "FAIL"
        print(f"  [{icon}] Step {step}: {label}")

    verdict = "PASS" if failed == 0 else "FAIL"
    print(f"""
  Total Steps : {len(results)}
  Passed      : {passed}
  Failed      : {failed}
  Elapsed     : {total_time:.2f}s

  VERDICT     : {verdict}
""")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
