#!/usr/bin/env python3
"""
verify_green.py — Verify that a PR's CI checks are truly green.

Exit 0 only if:
  1. Newest check-run set reports against PR's current head SHA
  2. All required checks concluded with 'success' (fail on skipped/neutral/cancelled)
  3. If PR diff adds test functions, each test appears in CI logs
  4. Logs contain no ModuleNotFoundError or command not found errors
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def compare_sha(actual: str, expected: str) -> bool:
    """Return True if SHAs match (same commit)."""
    return actual.strip() == expected.strip()


def classify_conclusion(conclusion: str) -> Tuple[bool, str]:
    """
    Classify a check conclusion.
    Returns (is_success, reason).
    Only 'success' is acceptable; others fail with a reason.
    """
    conclusion = conclusion.strip().lower()
    if conclusion == "success":
        return True, "success"
    elif conclusion == "skipped":
        return False, "check was skipped"
    elif conclusion == "neutral":
        return False, "check was neutral"
    elif conclusion == "cancelled":
        return False, "check was cancelled"
    else:
        return False, f"unexpected conclusion: {conclusion}"


def extract_new_tests(diff_text: str) -> List[str]:
    """
    Extract new test function names from a PR diff.
    Regex: lines starting with '+' followed by 'def test_'.
    Returns list of test function names (without 'def ' prefix).
    """
    tests = []
    for line in diff_text.split("\n"):
        # Match: +<optional-whitespace>def test_<name>
        match = re.match(r"^\+\s*def\s+(test_\w+)", line)
        if match:
            tests.append(match.group(1))
    return tests


def scan_logs_for_errors(log_text: str) -> List[str]:
    """
    Scan logs for known error patterns.
    Returns list of error messages found (empty if clean).
    """
    errors = []
    # Colon required: a real traceback is always "ModuleNotFoundError: ...";
    # bare mentions occur legitimately (e.g. commit messages echoed into logs).
    if "ModuleNotFoundError:" in log_text:
        errors.append("ModuleNotFoundError found in logs")
    if "command not found" in log_text:
        errors.append("command not found error in logs")
    return errors


def run_cmd(cmd: List[str]) -> str:
    """
    Run a shell command and return stdout.
    Raises subprocess.CalledProcessError on non-zero exit.
    """
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, cmd, output=result.stdout, stderr=result.stderr
        )
    return result.stdout


def get_pr_head_sha(pr_number: int, repo: Optional[str] = None) -> str:
    """Get the current head SHA of a PR via 'gh pr view --json headRefOid'."""
    cmd = ["gh", "pr", "view", str(pr_number), "--json", "headRefOid"]
    if repo:
        cmd.extend(["-R", repo])
    output = run_cmd(cmd)
    data = json.loads(output)
    return data.get("headRefOid", "")


def get_pr_diff(pr_number: int, repo: Optional[str] = None) -> str:
    """Get the PR diff via 'gh pr diff'."""
    cmd = ["gh", "pr", "diff", str(pr_number)]
    if repo:
        cmd.extend(["-R", repo])
    return run_cmd(cmd)


def get_repo_slug(repo: Optional[str] = None) -> str:
    """Resolve owner/name, defaulting to the current directory's repo."""
    if repo:
        return repo
    output = run_cmd(
        ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"]
    )
    return output.strip()


def get_check_runs_for_sha(sha: str, repo: Optional[str] = None) -> List[Dict]:
    """
    Get check-runs reported against EXACTLY this commit SHA via the REST API.
    Inherently SHA-pinned: a green badge from a previous head cannot appear here.
    Returns list of {name, status, conclusion, completed_at}.
    """
    slug = get_repo_slug(repo)
    output = run_cmd(
        ["gh", "api", "repos/%s/commits/%s/check-runs" % (slug, sha), "--paginate"]
    )
    check_runs: List[Dict] = []
    # --paginate concatenates JSON objects; parse each document
    decoder = json.JSONDecoder()
    idx = 0
    text = output.strip()
    while idx < len(text):
        obj, end = decoder.raw_decode(text, idx)
        check_runs.extend(obj.get("check_runs", []))
        idx = end
        while idx < len(text) and text[idx] in " \n\r\t":
            idx += 1
    return check_runs


def get_run_ids_for_sha(sha: str, repo: Optional[str] = None) -> List[str]:
    """Get workflow-run IDs whose headSha is exactly this SHA."""
    cmd = [
        "gh",
        "run",
        "list",
        "--commit",
        sha,
        "--json",
        "databaseId,status,headSha",
        "--limit",
        "50",
    ]
    if repo:
        cmd.extend(["-R", repo])
    runs = json.loads(run_cmd(cmd))
    return [
        str(r["databaseId"])
        for r in runs
        if r.get("headSha") == sha and r.get("status") == "completed"
    ]


def get_run_logs(run_id: str, repo: Optional[str] = None) -> str:
    """Get logs from a specific workflow run via 'gh run view --log'."""
    cmd = ["gh", "run", "view", run_id, "--log"]
    if repo:
        cmd.extend(["-R", repo])
    return run_cmd(cmd)


def verify_green(pr_number: int, repo: Optional[str] = None) -> Dict:
    """
    Main verification logic.
    Returns dict: {pr, sha, checks, tests_added, tests_found_in_log, verdict, errors}
    """
    verdict = {
        "pr": pr_number,
        "sha": "",
        "checks": [],
        "tests_added": [],
        "tests_found_in_log": [],
        "errors": [],
    }

    try:
        # Get current head SHA
        head_sha = get_pr_head_sha(pr_number, repo)
        verdict["sha"] = head_sha
        if not head_sha:
            verdict["errors"].append("Could not resolve PR head SHA")
            return verdict

        # Check 1 (SHA pinning): fetch check-runs for EXACTLY the current head.
        # A green badge from a previous head simply cannot appear in this list;
        # an empty list means CI never reported against the current head.
        checks = get_check_runs_for_sha(head_sha, repo)
        if not checks:
            verdict["errors"].append(
                f"No check-runs reported against current head {head_sha[:8]} "
                "— any green badge you saw belongs to a previous head"
            )
            return verdict

        # Check 2: every check-run must be completed AND concluded success
        check_list = []
        for check in checks:
            name = check.get("name", "unknown")
            status = check.get("status", "")
            conclusion = check.get("conclusion") or ""
            check_list.append({"name": name, "conclusion": conclusion})
            if status != "completed":
                verdict["errors"].append(
                    f"Check '{name}': still '{status}', not completed"
                )
                continue
            is_success, reason = classify_conclusion(conclusion)
            if not is_success:
                verdict["errors"].append(f"Check '{name}': {reason}")

        verdict["checks"] = check_list

        # Get diff and extract new tests
        diff_text = get_pr_diff(pr_number, repo)
        new_tests = extract_new_tests(diff_text)
        verdict["tests_added"] = new_tests

        # Check 3+4: fetch logs of all completed runs for this SHA; new tests
        # must appear, and no silent no-op markers may appear.
        try:
            run_ids = get_run_ids_for_sha(head_sha, repo)
            logs = "\n".join(get_run_logs(rid, repo) for rid in run_ids)
            if not logs:
                verdict["errors"].append(
                    f"No workflow-run logs found for head {head_sha[:8]}"
                )
            log_errors = scan_logs_for_errors(logs)
            verdict["errors"].extend(log_errors)

            found_in_log = []
            for test in new_tests:
                if test in logs:
                    found_in_log.append(test)
                else:
                    verdict["errors"].append(f"Test '{test}' not found in CI logs")
            verdict["tests_found_in_log"] = found_in_log
        except subprocess.CalledProcessError as e:
            verdict["errors"].append(f"Could not fetch logs: {e}")

    except subprocess.CalledProcessError as e:
        verdict["errors"].append(f"Command failed: {e}")
    except json.JSONDecodeError as e:
        verdict["errors"].append(f"JSON parse error: {e}")
    except Exception as e:
        verdict["errors"].append(f"Unexpected error: {e}")

    return verdict


def save_verdict(verdict: Dict, output_dir: str = ".verify_green") -> None:
    """Save verdict JSON to file."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    pr = verdict.get("pr", "unknown")
    sha = verdict.get("sha", "unknown")[:8]
    filename = Path(output_dir) / f"{pr}-{sha}.json"
    with open(filename, "w") as f:
        json.dump(verdict, f, indent=2)


def run_self_test() -> bool:
    """
    Run offline unit checks on pure functions.
    Returns True if all pass.
    """
    tests_passed = 0
    tests_failed = 0

    # Test: compare_sha
    if compare_sha("abc123", "abc123"):
        tests_passed += 1
    else:
        print("FAIL: compare_sha identical")
        tests_failed += 1

    if not compare_sha("abc123", "def456"):
        tests_passed += 1
    else:
        print("FAIL: compare_sha different")
        tests_failed += 1

    # Test: classify_conclusion
    is_ok, _ = classify_conclusion("success")
    if is_ok:
        tests_passed += 1
    else:
        print("FAIL: classify_conclusion success")
        tests_failed += 1

    is_ok, _ = classify_conclusion("skipped")
    if not is_ok:
        tests_passed += 1
    else:
        print("FAIL: classify_conclusion skipped")
        tests_failed += 1

    # Test: extract_new_tests
    diff = "line1\n+  def test_foo():\n+    pass\nline2\n+def test_bar():"
    tests = extract_new_tests(diff)
    if tests == ["test_foo", "test_bar"]:
        tests_passed += 1
    else:
        print(f"FAIL: extract_new_tests got {tests}")
        tests_failed += 1

    # Test: scan_logs_for_errors
    log_clean = "All tests passed"
    errors = scan_logs_for_errors(log_clean)
    if not errors:
        tests_passed += 1
    else:
        print("FAIL: scan_logs_for_errors clean log")
        tests_failed += 1

    log_error = "ModuleNotFoundError: no module named foo"
    errors = scan_logs_for_errors(log_error)
    if errors and "ModuleNotFoundError" in errors[0]:
        tests_passed += 1
    else:
        print("FAIL: scan_logs_for_errors ModuleNotFoundError")
        tests_failed += 1

    return tests_failed == 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: verify_green.py <pr-number> [--repo owner/name] [--self-test]")
        sys.exit(1)

    if sys.argv[1] == "--self-test":
        if run_self_test():
            print("PASS")
            sys.exit(0)
        else:
            print("FAIL")
            sys.exit(1)

    try:
        pr_num = int(sys.argv[1])
    except ValueError:
        print(f"Invalid PR number: {sys.argv[1]}")
        sys.exit(1)

    repo = None
    if "--repo" in sys.argv:
        idx = sys.argv.index("--repo")
        if idx + 1 < len(sys.argv):
            repo = sys.argv[idx + 1]

    verdict = verify_green(pr_num, repo)
    save_verdict(verdict)

    if verdict.get("errors"):
        print(json.dumps(verdict, indent=2))
        sys.exit(1)
    else:
        print(json.dumps(verdict, indent=2))
        sys.exit(0)
