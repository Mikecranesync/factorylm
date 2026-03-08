#!/usr/bin/env python3
"""
FactoryLM Vision — Comprehensive Test Session Script
=====================================================
Runs a full test matrix against the Cosmos R2 diagnosis pipeline.

Usage:
    # Full test suite
    python cookoff/test_session.py

    # Skip vLLM (useful for infrastructure checks only)
    python cookoff/test_session.py --skip-vllm

    # Skip PLC connectivity test
    python cookoff/test_session.py --skip-plc

    # Run only 2 scenarios (normal + jam) for a faster pass
    python cookoff/test_session.py --quick

    # Combine flags
    python cookoff/test_session.py --quick --skip-plc

Importable API:
    from cookoff.test_session import (
        check_prerequisites,
        check_vllm_endpoint,
        run_screenshot_test,
        run_scenario_tests,
        run_live_plc_test,
        run_qa_test,
    )
"""

import argparse
import importlib
import io
import os
import sys
import time
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Repo-root path manipulation — same pattern as diagnosis_engine.py.
# Must happen before importing siblings so their relative imports resolve.
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Import siblings.  diagnosis_engine wraps sys.stdout/stderr with utf-8
# TextIOWrappers at its module level — this covers the Windows console encoding
# fix for the whole process, so we do not re-wrap here.
from cookoff import capture_fio          # noqa: E402
from cookoff import diagnosis_engine     # noqa: E402

CLIPS_DIR = REPO_ROOT / "cookoff" / "clips"
VLLM_MODELS_URL = "http://localhost:8000/v1/models"
VLLM_CHAT_URL = "http://localhost:8000/v1/chat/completions"
PLC_HOST = "192.168.1.100"
PLC_PORT = 502
EXPECTED_MODEL = "nvidia/Cosmos-Reason2-8B"

ALL_SCENARIOS = ["normal", "jam", "estop", "idle", "overheat"]
QUICK_SCENARIOS = ["normal", "jam"]

# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

class TestResult:
    """Holds the outcome of a single test."""

    def __init__(self, name: str):
        self.name = name
        self.status: str = "SKIP"   # PASS | FAIL | SKIP
        self.detail: str = ""
        self.elapsed_s: Optional[float] = None
        self.tokens: Optional[int] = None

    def passed(self, detail: str = "", elapsed_s: float = None, tokens: int = None):
        self.status = "PASS"
        self.detail = detail
        self.elapsed_s = elapsed_s
        self.tokens = tokens

    def failed(self, detail: str = ""):
        self.status = "FAIL"
        self.detail = detail

    def skipped(self, reason: str = ""):
        self.status = "SKIP"
        self.detail = reason

    def label(self) -> str:
        """Human-readable label for the summary table row."""
        timing = ""
        if self.elapsed_s is not None and self.tokens is not None:
            timing = f" ({self.elapsed_s:.1f}s, {self.tokens} tokens)"
        elif self.elapsed_s is not None:
            timing = f" ({self.elapsed_s:.1f}s)"
        detail = f" — {self.detail}" if self.detail and self.status != "PASS" else timing
        return f"{self.status}{detail}"


# ---------------------------------------------------------------------------
# Individual test functions
# ---------------------------------------------------------------------------

def check_prerequisites() -> TestResult:
    """
    Verify that all required Python packages are importable and that at least
    one screenshot exists in cookoff/clips/.
    """
    result = TestResult("Prerequisites")
    required = ["pymodbus", "requests", "yaml", "mss"]
    missing = []

    for pkg in required:
        try:
            importlib.import_module(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        result.failed(f"Missing packages: {', '.join(missing)}")
        print(f"  [FAIL] Missing packages: {', '.join(missing)}")
        print(f"         Install with: pip install {' '.join(missing)}")
        return result

    print(f"  [OK ] All packages importable: {', '.join(required)}")

    # Check for at least one existing screenshot in clips/
    clips = list(CLIPS_DIR.glob("*.png")) + list(CLIPS_DIR.glob("*.jpg"))
    if clips:
        print(f"  [OK ] Found {len(clips)} file(s) in {CLIPS_DIR}")
        result.passed()
    else:
        # Not fatal — screenshot test will create one
        print(f"  [WARN] No screenshots found in {CLIPS_DIR} (will capture one during tests)")
        result.passed("no pre-existing screenshots, will capture")

    return result


def check_vllm_endpoint() -> TestResult:
    """
    GET /v1/models and confirm Cosmos-Reason2-8B is loaded.
    """
    result = TestResult("vLLM endpoint")
    try:
        import requests
        resp = requests.get(VLLM_MODELS_URL, timeout=10)
    except Exception as exc:
        result.failed(f"Cannot reach {VLLM_MODELS_URL}: {exc}")
        print(f"  [FAIL] {result.detail}")
        print()
        print("  ---- Vast.ai spin-up instructions ----")
        print("  1. Go to https://vast.ai and rent an A100/A6000 instance")
        print("  2. SSH in and run:")
        print("       pip install vllm")
        print("       python -m vllm.entrypoints.openai.api_server \\")
        print(f"         --model {EXPECTED_MODEL} \\")
        print("         --trust-remote-code \\")
        print("         --port 8000")
        print("  3. Forward port 8000 to this machine:")
        print("       ssh -L 8000:localhost:8000 user@<vast-ip>")
        print("  ---------------------------------------")
        return result

    if resp.status_code != 200:
        result.failed(f"HTTP {resp.status_code} from {VLLM_MODELS_URL}")
        print(f"  [FAIL] {result.detail}")
        return result

    data = resp.json()
    model_ids = [m.get("id", "") for m in data.get("data", [])]
    if any(EXPECTED_MODEL in mid for mid in model_ids):
        print(f"  [OK ] {EXPECTED_MODEL} is loaded ({', '.join(model_ids)})")
        result.passed()
    else:
        result.failed(f"Model not found. Loaded: {model_ids}")
        print(f"  [FAIL] {result.detail}")

    return result


def run_screenshot_test() -> tuple[TestResult, Optional[Path]]:
    """
    Capture a single screenshot via capture_fio.capture_screenshot().
    Returns (TestResult, path_to_screenshot_or_None).
    """
    result = TestResult("Screenshot")
    screenshot_path: Optional[Path] = None

    try:
        screenshot_path = capture_fio.capture_screenshot(label="test_session")
        if not screenshot_path.exists():
            result.failed(f"File not created: {screenshot_path}")
            print(f"  [FAIL] {result.detail}")
            return result, None

        size = screenshot_path.stat().st_size
        if size == 0:
            result.failed(f"File is empty: {screenshot_path}")
            print(f"  [FAIL] {result.detail}")
            return result, None

        print(f"  [OK ] {screenshot_path.name} ({size:,} bytes)")
        result.passed()
    except Exception as exc:
        result.failed(str(exc))
        print(f"  [FAIL] {exc}")

    return result, screenshot_path


def run_scenario_tests(
    screenshot_path: Path,
    scenarios: list[str],
    vllm_url: str = VLLM_CHAT_URL,
) -> list[TestResult]:
    """
    Run diagnosis_engine.diagnose() for each simulated scenario.

    Returns a list of TestResult, one per scenario.
    """
    results: list[TestResult] = []

    for scenario in scenarios:
        r = TestResult(f"Scenario {scenario}")
        print(f"  Running scenario: {scenario} ...", end=" ", flush=True)

        plc_tags = diagnosis_engine.SIMULATED_SCENARIOS[scenario]

        try:
            response = diagnosis_engine.diagnose(
                media_path=str(screenshot_path),
                plc_tags=plc_tags,
                vllm_url=vllm_url,
            )
        except Exception as exc:
            r.failed(str(exc))
            print(f"FAIL ({exc})")
            results.append(r)
            continue

        if "error" in response:
            r.failed(response["error"][:120])
            print(f"FAIL ({r.detail})")
        elif "diagnosis" not in response:
            r.failed("response missing 'diagnosis' key")
            print(f"FAIL ({r.detail})")
        else:
            elapsed = response.get("elapsed_s")
            tokens = response.get("usage", {}).get("completion_tokens")
            r.passed(elapsed_s=elapsed, tokens=tokens)
            timing_str = ""
            if elapsed is not None:
                timing_str += f"{elapsed:.1f}s"
            if tokens is not None:
                timing_str += f", {tokens} tokens"
            print(f"PASS ({timing_str})")

        results.append(r)

    return results


def run_live_plc_test(
    screenshot_path: Path,
    vllm_url: str = VLLM_CHAT_URL,
) -> TestResult:
    """
    Attempt to connect to the real Micro 820 PLC, read registers,
    then run a diagnosis.  Skips gracefully if PLC is unreachable.
    """
    result = TestResult("Live PLC")

    # First probe connectivity with a short timeout
    import socket
    try:
        sock = socket.create_connection((PLC_HOST, PLC_PORT), timeout=3)
        sock.close()
        print(f"  PLC reachable at {PLC_HOST}:{PLC_PORT}")
    except OSError:
        result.skipped(f"PLC offline at {PLC_HOST}:{PLC_PORT}")
        print(f"  [SKIP] {result.detail}")
        return result

    # PLC is reachable — try a real read
    try:
        plc_tags = diagnosis_engine.read_live_plc(host=PLC_HOST, port=PLC_PORT)
    except Exception as exc:
        result.failed(f"read_live_plc raised: {exc}")
        print(f"  [FAIL] {result.detail}")
        return result

    if plc_tags is None:
        result.failed("read_live_plc returned None (connection failed internally)")
        print(f"  [FAIL] {result.detail}")
        return result

    print(f"  Read {len(plc_tags)} tags from live PLC. Running diagnosis...")

    try:
        response = diagnosis_engine.diagnose(
            media_path=str(screenshot_path),
            plc_tags=plc_tags,
            vllm_url=vllm_url,
        )
    except Exception as exc:
        result.failed(f"diagnose raised: {exc}")
        print(f"  [FAIL] {result.detail}")
        return result

    if "error" in response:
        result.failed(response["error"][:120])
        print(f"  [FAIL] {result.detail}")
    elif "diagnosis" not in response:
        result.failed("response missing 'diagnosis' key")
        print(f"  [FAIL] {result.detail}")
    else:
        elapsed = response.get("elapsed_s")
        tokens = response.get("usage", {}).get("completion_tokens")
        result.passed(elapsed_s=elapsed, tokens=tokens)
        timing_str = f"{elapsed:.1f}s" if elapsed else "?"
        print(f"  [OK ] Live PLC diagnosis complete ({timing_str})")

    return result


def run_qa_test(
    screenshot_path: Path,
    vllm_url: str = VLLM_CHAT_URL,
) -> TestResult:
    """
    Ask a natural-language question and verify a response is returned.
    """
    result = TestResult("Q&A mode")
    question = "What equipment do you see and is the conveyor running?"
    print(f"  Question: \"{question}\"")

    # Use the 'normal' scenario PLC data as context for the Q&A test
    plc_tags = diagnosis_engine.SIMULATED_SCENARIOS["normal"]

    try:
        response = diagnosis_engine.diagnose(
            media_path=str(screenshot_path),
            plc_tags=plc_tags,
            question=question,
            vllm_url=vllm_url,
        )
    except Exception as exc:
        result.failed(str(exc))
        print(f"  [FAIL] {exc}")
        return result

    if "error" in response:
        result.failed(response["error"][:120])
        print(f"  [FAIL] {result.detail}")
    elif "diagnosis" not in response:
        result.failed("response missing 'diagnosis' key")
        print(f"  [FAIL] {result.detail}")
    else:
        elapsed = response.get("elapsed_s")
        tokens = response.get("usage", {}).get("completion_tokens")
        result.passed(elapsed_s=elapsed, tokens=tokens)
        timing_str = ""
        if elapsed is not None:
            timing_str += f"{elapsed:.1f}s"
        if tokens is not None:
            timing_str += f", {tokens} tokens"
        snippet = response["diagnosis"][:120].replace("\n", " ")
        print(f"  [OK ] Answer received ({timing_str}): {snippet}...")

    return result


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def print_summary(all_results: list[TestResult]) -> tuple[int, int, int]:
    """
    Print the final results table.  Returns (passed, failed, skipped).
    """
    print()
    print("FactoryLM Vision -- Test Results")
    print("=" * 48)

    passed = failed = skipped = 0
    for r in all_results:
        col_width = 22
        name_col = f"{r.name}:".ljust(col_width)
        print(f"  {name_col} {r.label()}")
        if r.status == "PASS":
            passed += 1
        elif r.status == "FAIL":
            failed += 1
        else:
            skipped += 1

    total = passed + failed + skipped
    print("=" * 48)
    print(f"  Total: {passed}/{total} passed", end="")
    if skipped:
        print(f", {skipped} skipped", end="")
    if failed:
        print(f", {failed} FAILED", end="")
    print()
    return passed, failed, skipped


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_test_session(
    skip_vllm: bool = False,
    skip_plc: bool = False,
    quick: bool = False,
    vllm_url: str = VLLM_CHAT_URL,
) -> int:
    """
    Execute the full test matrix.

    Parameters
    ----------
    skip_vllm : bool
        If True, skip the vLLM endpoint check and all inference tests.
    skip_plc : bool
        If True, skip the live PLC connectivity test.
    quick : bool
        If True, run only the 'normal' and 'jam' scenarios instead of all 5.
    vllm_url : str
        Override the vLLM chat completions URL.

    Returns
    -------
    int
        Exit code: 0 if all non-skipped tests passed, 1 otherwise.
    """
    scenarios = QUICK_SCENARIOS if quick else ALL_SCENARIOS
    all_results: list[TestResult] = []
    screenshot_path: Optional[Path] = None

    # ------------------------------------------------------------------
    # 1. Prerequisites
    # ------------------------------------------------------------------
    print("\n[1/6] Checking prerequisites...")
    prereq_result = check_prerequisites()
    all_results.append(prereq_result)

    if prereq_result.status == "FAIL":
        # No point running further tests without required packages
        print("\nAborting: fix prerequisites first.")
        print_summary(all_results)
        return 1

    # ------------------------------------------------------------------
    # 2. vLLM endpoint
    # ------------------------------------------------------------------
    print("\n[2/6] Checking vLLM endpoint...")
    vllm_result = TestResult("vLLM endpoint")
    if skip_vllm:
        vllm_result.skipped("--skip-vllm flag")
        print(f"  [SKIP] {vllm_result.detail}")
    else:
        vllm_result = check_vllm_endpoint()
    all_results.append(vllm_result)

    # ------------------------------------------------------------------
    # 3. Screenshot capture
    # ------------------------------------------------------------------
    print("\n[3/6] Screenshot test...")
    screenshot_result, screenshot_path = run_screenshot_test()
    all_results.append(screenshot_result)

    # If screenshot failed and no existing clip is available, bail on
    # inference tests because they all need an image.
    if screenshot_path is None or not screenshot_path.exists():
        existing = sorted(CLIPS_DIR.glob("*.png"))
        if existing:
            screenshot_path = existing[-1]
            print(f"  Using most recent clip instead: {screenshot_path.name}")
        else:
            print("\nAborting inference tests: no screenshot available.")
            # Mark remaining tests as skipped
            for name in [f"Scenario {s}" for s in scenarios] + ["Live PLC", "Q&A mode"]:
                r = TestResult(name)
                r.skipped("no screenshot")
                all_results.append(r)
            print_summary(all_results)
            return 1

    # ------------------------------------------------------------------
    # 4. Scenario diagnosis tests
    # ------------------------------------------------------------------
    print(f"\n[4/6] Running {len(scenarios)} scenario diagnosis tests...")
    if skip_vllm or vllm_result.status == "FAIL":
        for scenario in scenarios:
            r = TestResult(f"Scenario {scenario}")
            reason = "--skip-vllm" if skip_vllm else "vLLM unavailable"
            r.skipped(reason)
            print(f"  [SKIP] Scenario {scenario}: {reason}")
            all_results.append(r)
    else:
        scenario_results = run_scenario_tests(
            screenshot_path=screenshot_path,
            scenarios=scenarios,
            vllm_url=vllm_url,
        )
        all_results.extend(scenario_results)

    # ------------------------------------------------------------------
    # 5. Live PLC test
    # ------------------------------------------------------------------
    print("\n[5/6] Live PLC test...")
    if skip_plc:
        plc_result = TestResult("Live PLC")
        plc_result.skipped("--skip-plc flag")
        print(f"  [SKIP] {plc_result.detail}")
        all_results.append(plc_result)
    elif skip_vllm or vllm_result.status == "FAIL":
        plc_result = TestResult("Live PLC")
        plc_result.skipped("vLLM unavailable — skipping inference step")
        print(f"  [SKIP] {plc_result.detail}")
        all_results.append(plc_result)
    else:
        plc_result = run_live_plc_test(
            screenshot_path=screenshot_path,
            vllm_url=vllm_url,
        )
        all_results.append(plc_result)

    # ------------------------------------------------------------------
    # 6. Q&A test
    # ------------------------------------------------------------------
    print("\n[6/6] Q&A mode test...")
    if skip_vllm or vllm_result.status == "FAIL":
        qa_result = TestResult("Q&A mode")
        reason = "--skip-vllm" if skip_vllm else "vLLM unavailable"
        qa_result.skipped(reason)
        print(f"  [SKIP] {qa_result.detail}")
        all_results.append(qa_result)
    else:
        qa_result = run_qa_test(
            screenshot_path=screenshot_path,
            vllm_url=vllm_url,
        )
        all_results.append(qa_result)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    passed, failed, skipped = print_summary(all_results)
    return 0 if failed == 0 else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="FactoryLM Vision — Comprehensive Test Session",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--skip-vllm",
        action="store_true",
        help="Skip the vLLM endpoint check and all inference tests",
    )
    parser.add_argument(
        "--skip-plc",
        action="store_true",
        help="Skip the live PLC connectivity test",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run only normal + jam scenarios (faster pass)",
    )
    parser.add_argument(
        "--vllm-url",
        default=VLLM_CHAT_URL,
        help=f"Override the vLLM chat completions URL (default: {VLLM_CHAT_URL})",
    )
    args = parser.parse_args()

    print("FactoryLM Vision — Test Session")
    print(f"  Repo root : {REPO_ROOT}")
    print(f"  Clips dir : {CLIPS_DIR}")
    print(f"  vLLM URL  : {args.vllm_url}")
    print(f"  PLC host  : {PLC_HOST}:{PLC_PORT}")
    print(f"  Mode      : {'quick (2 scenarios)' if args.quick else 'full (5 scenarios)'}")
    if args.skip_vllm:
        print("  --skip-vllm: inference tests will be skipped")
    if args.skip_plc:
        print("  --skip-plc: live PLC test will be skipped")

    exit_code = run_test_session(
        skip_vllm=args.skip_vllm,
        skip_plc=args.skip_plc,
        quick=args.quick,
        vllm_url=args.vllm_url,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
