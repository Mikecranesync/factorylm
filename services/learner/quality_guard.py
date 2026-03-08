"""Quality Guard -- validate learner experiment quality.

Checks:
1. Tag delta consistency -- same coil toggle should produce same delta
2. Learning quality -- learning text should contain expected keywords
3. Confidence drift -- alert if avg confidence drops below baseline
4. Model cost -- alert if any non-free model was called

Can run as:
- Post-experiment hook (called after each experiment)
- Regression suite (replays golden experiments)
- Langflow custom component (imported into a flow)
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("factorylm.learner.quality_guard")

REPO_ROOT = Path(__file__).parent.parent.parent
DRIFT_LOG = REPO_ROOT / "data" / "learner" / "drift.jsonl"

# Golden experiment baselines for "From A to B" scene
GOLDEN_EXPERIMENTS = {
    "Conveyor": {
        "expected_delta_keys": ["Conveyor"],
        "expected_learning_keywords": ["belt", "motor", "conveyor", "move"],
        "min_confidence": 0.3,
    },
    "Emitter": {
        "expected_delta_keys": ["Emitter"],
        "expected_learning_keywords": ["item", "spawn", "box", "create"],
        "min_confidence": 0.3,
    },
    "SensorStart": {
        "expected_delta_keys": ["SensorStart"],
        "expected_learning_keywords": ["sensor", "entry", "detect"],
        "min_confidence": 0.3,
    },
    "SensorEnd": {
        "expected_delta_keys": ["SensorEnd"],
        "expected_learning_keywords": ["sensor", "exit", "end"],
        "min_confidence": 0.3,
    },
    "RunCommand": {
        "expected_delta_keys": ["RunCommand"],
        "expected_learning_keywords": ["run", "start", "conveyor", "emitter"],
        "min_confidence": 0.3,
    },
}

# Paid providers that should never appear in learner inference
PAID_PROVIDERS = {"anthropic", "sonnet", "haiku", "claude"}

# Golden baselines for sorting-scene fault detection (used by scenario_runner)
GOLDEN_FAULT_SCENARIOS = {
    "E001_estop": {
        "expected_fault_code": "E001",
        "expected_severity": "emergency",
        "max_duration_s": 10.0,
    },
    "C001_conveyor_stopped": {
        "expected_fault_code": "C001",
        "expected_severity": "critical",
        "max_duration_s": 10.0,
    },
    "C002_diverter_conflict": {
        "expected_fault_code": "C002",
        "expected_severity": "critical",
        "max_duration_s": 10.0,
    },
    "J001_high_sensor_jam": {
        "expected_fault_code": "J001",
        "expected_severity": "warning",
        "max_duration_s": 15.0,
    },
    "J001_low_sensor_jam": {
        "expected_fault_code": "J001",
        "expected_severity": "warning",
        "max_duration_s": 15.0,
    },
    "OK_normal": {
        "expected_fault_code": "OK",
        "expected_severity": "info",
        "max_duration_s": 8.0,
    },
    "IDLE_scene_stopped": {
        "expected_fault_code": "IDLE",
        "expected_severity": "info",
        "max_duration_s": 8.0,
    },
    "E001_C001_multi": {
        "expected_fault_code": "E001",
        "expected_severity": "emergency",
        "max_duration_s": 10.0,
    },
}


def check_experiment(result: dict) -> dict:
    """Validate a single experiment result against golden baseline."""
    coil = result.get("coil_name", "")
    golden = GOLDEN_EXPERIMENTS.get(coil)
    if not golden:
        return {"passed": True, "skipped": True, "reason": "no golden baseline", "coil": coil}

    issues = []

    # 1. Tag delta check
    delta_keys = set(result.get("tag_delta", {}).keys())
    for expected in golden["expected_delta_keys"]:
        if expected not in delta_keys:
            issues.append({"type": "missing_delta", "expected": expected})

    # 2. Learning keyword check
    learning = result.get("learning", "").lower()
    if learning:
        missing_kw = 0
        for kw in golden["expected_learning_keywords"]:
            if kw not in learning:
                missing_kw += 1
        # Only flag if ALL keywords are missing (some variation is OK)
        if missing_kw == len(golden["expected_learning_keywords"]):
            issues.append({
                "type": "no_expected_keywords",
                "keywords": golden["expected_learning_keywords"],
                "severity": "warning",
            })

    # 3. Confidence check
    if result.get("confidence", 0) < golden["min_confidence"]:
        issues.append({"type": "low_confidence", "value": result.get("confidence")})

    # 4. Model cost check (privacy gate)
    provider = result.get("provider", "").lower()
    for paid in PAID_PROVIDERS:
        if paid in provider:
            issues.append({"type": "paid_model_used", "provider": provider, "severity": "critical"})
            break

    return {"passed": len(issues) == 0, "issues": issues, "coil": coil}


def run_regression_suite(knowledge_export: dict) -> dict:
    """Run quality checks on all experiments in a knowledge export."""
    results = []
    for exp in knowledge_export.get("experiments", []):
        check = check_experiment(exp)
        results.append(check)

    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"] and not r.get("skipped"))
    skipped = sum(1 for r in results if r.get("skipped"))

    return {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "issues": [r for r in results if not r["passed"] and not r.get("skipped")],
    }


# ---------------------------------------------------------------------------
# Scenario runner quality checks (sorting-scene fault detection)
# ---------------------------------------------------------------------------


def check_scenario_result(result: dict) -> dict:
    """Validate a scenario runner result against golden fault baselines."""
    sid = result.get("scenario_id", "")
    golden = GOLDEN_FAULT_SCENARIOS.get(sid)
    if not golden:
        return {"passed": True, "skipped": True, "reason": "no golden baseline", "scenario_id": sid}

    issues = []

    # 1. Fault code match
    if not result.get("passed"):
        issues.append({
            "type": "fault_code_mismatch",
            "expected": golden["expected_fault_code"],
            "observed": result.get("observed_faults", []),
        })

    # 2. Duration check — slow detection is a quality signal
    duration = result.get("duration_s", 0)
    if duration > golden["max_duration_s"]:
        issues.append({
            "type": "slow_detection",
            "max_allowed_s": golden["max_duration_s"],
            "actual_s": duration,
            "severity": "warning",
        })

    return {"passed": len(issues) == 0, "issues": issues, "scenario_id": sid}


def run_scenario_regression(all_results: list[dict]) -> dict:
    """Run quality checks on all scenario results."""
    checks = []
    for result in all_results:
        check = check_scenario_result(result)
        checks.append(check)

    passed = sum(1 for c in checks if c["passed"])
    failed = sum(1 for c in checks if not c["passed"] and not c.get("skipped"))
    skipped = sum(1 for c in checks if c.get("skipped"))

    return {
        "total": len(checks),
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "issues": [c for c in checks if not c["passed"] and not c.get("skipped")],
    }


# ---------------------------------------------------------------------------
# Drift detection (sigma-based, pattern from analytics/drift_detector.py)
# ---------------------------------------------------------------------------

_confidence_history: list[float] = []
_baseline_mean: Optional[float] = None
_baseline_std: Optional[float] = None


def update_confidence_baseline(confidences: list[float]):
    """Set baseline statistics from a known-good run."""
    global _baseline_mean, _baseline_std
    if not confidences:
        return
    _baseline_mean = sum(confidences) / len(confidences)
    variance = sum((c - _baseline_mean) ** 2 for c in confidences) / len(confidences)
    _baseline_std = max(variance ** 0.5, 0.01)  # Floor to avoid div-by-zero
    logger.info("Drift baseline: mean=%.3f, std=%.3f (n=%d)",
                _baseline_mean, _baseline_std, len(confidences))


def check_drift(confidence: float) -> Optional[dict]:
    """Check if a new confidence value drifts from baseline.

    Returns None if within bounds, or a drift alert dict.
    2-sigma = warning, 3-sigma = critical.
    """
    _confidence_history.append(confidence)

    if _baseline_mean is None or _baseline_std is None:
        return None

    z_score = abs(confidence - _baseline_mean) / _baseline_std

    if z_score < 2.0:
        return None

    severity = "critical" if z_score >= 3.0 else "warning"
    alert = {
        "type": "confidence_drift",
        "severity": severity,
        "z_score": round(z_score, 2),
        "value": confidence,
        "baseline_mean": round(_baseline_mean, 3),
        "baseline_std": round(_baseline_std, 3),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    _log_drift(alert)
    return alert


def _log_drift(alert: dict):
    """Append drift alert to JSONL log."""
    try:
        DRIFT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(DRIFT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(alert, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.error("Drift log write failed: %s", exc)


# ---------------------------------------------------------------------------
# CLI entry point for standalone regression
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m services.learner.quality_guard <knowledge_export.json>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        export = json.load(f)

    result = run_regression_suite(export)
    print(f"\nQuality Guard Results:")
    print(f"  Total: {result['total']}")
    print(f"  Passed: {result['passed']}")
    print(f"  Failed: {result['failed']}")
    print(f"  Skipped: {result['skipped']}")

    if result["issues"]:
        print(f"\nIssues:")
        for issue in result["issues"]:
            print(f"  {issue['coil']}: {issue['issues']}")

    sys.exit(0 if result["failed"] == 0 else 1)
