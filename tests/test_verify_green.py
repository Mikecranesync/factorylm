"""
Tests for verify_green.py — pure functions and mocked subprocess calls.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch


# Import the module
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from verify_green import (
    classify_conclusion,
    compare_sha,
    extract_new_tests,
    get_check_runs_for_sha,
    get_run_ids_for_sha,
    scan_logs_for_errors,
    verify_green,
)


class TestCompareSha:
    """Test SHA comparison."""

    def test_identical_shas(self):
        assert compare_sha("abc123", "abc123")

    def test_different_shas(self):
        assert not compare_sha("abc123", "def456")

    def test_shas_with_whitespace(self):
        assert compare_sha("abc123\n", "abc123")


class TestClassifyConclusion:
    """Test check conclusion classification."""

    def test_success(self):
        is_ok, reason = classify_conclusion("success")
        assert is_ok
        assert reason == "success"

    def test_skipped(self):
        is_ok, reason = classify_conclusion("skipped")
        assert not is_ok
        assert "skipped" in reason

    def test_neutral(self):
        is_ok, reason = classify_conclusion("neutral")
        assert not is_ok
        assert "neutral" in reason

    def test_cancelled(self):
        is_ok, reason = classify_conclusion("cancelled")
        assert not is_ok
        assert "cancelled" in reason

    def test_unknown(self):
        is_ok, reason = classify_conclusion("unknown")
        assert not is_ok


class TestExtractNewTests:
    """Test new test function extraction from diff."""

    def test_no_tests(self):
        diff = "line1\nline2\n"
        tests = extract_new_tests(diff)
        assert tests == []

    def test_single_test(self):
        diff = "+def test_foo():\n+    pass\n"
        tests = extract_new_tests(diff)
        assert "test_foo" in tests

    def test_multiple_tests(self):
        diff = "+def test_foo():\n+    pass\n+def test_bar():\n+    pass\n"
        tests = extract_new_tests(diff)
        assert "test_foo" in tests
        assert "test_bar" in tests

    def test_indented_tests(self):
        diff = "+  def test_baz():\n+    pass\n"
        tests = extract_new_tests(diff)
        assert "test_baz" in tests

    def test_non_test_functions_ignored(self):
        diff = "+def helper():\n+    pass\n"
        tests = extract_new_tests(diff)
        assert tests == []


class TestScanLogsForErrors:
    """Test error scanning in logs."""

    def test_clean_logs(self):
        logs = "All tests passed\nBuild successful\n"
        errors = scan_logs_for_errors(logs)
        assert errors == []

    def test_module_not_found(self):
        logs = "ModuleNotFoundError: no module named foo\n"
        errors = scan_logs_for_errors(logs)
        assert any("ModuleNotFoundError" in e for e in errors)

    def test_command_not_found(self):
        logs = "command not found: pytest\n"
        errors = scan_logs_for_errors(logs)
        assert any("command not found" in e for e in errors)

    def test_multiple_errors(self):
        logs = "ModuleNotFoundError: xyz\ncommand not found: foo\n"
        errors = scan_logs_for_errors(logs)
        assert len(errors) >= 2

    def test_bare_mention_without_colon_is_not_an_error(self):
        # Regression: PR #214's own commit message, echoed into the brain-ingest
        # log, contains the bare string and must not trip the scanner.
        logs = "docs: fails on ModuleNotFoundError/command-not-found no-ops\n"
        errors = scan_logs_for_errors(logs)
        assert not any("ModuleNotFoundError" in e for e in errors)


class TestGetCheckRunsForSha:
    """Test SHA-pinned check-run fetching, incl. --paginate concatenated JSON."""

    @patch("verify_green.run_cmd")
    def test_single_page(self, mock_cmd):
        def side_effect(cmd):
            if "nameWithOwner" in " ".join(cmd):
                return "owner/repo"
            return json.dumps(
                {"check_runs": [{"name": "build", "conclusion": "success"}]}
            )

        mock_cmd.side_effect = side_effect
        runs = get_check_runs_for_sha("abc123")
        assert len(runs) == 1
        assert runs[0]["name"] == "build"

    @patch("verify_green.run_cmd")
    def test_paginated_concatenated_json(self, mock_cmd):
        page1 = json.dumps({"check_runs": [{"name": "a"}]})
        page2 = json.dumps({"check_runs": [{"name": "b"}]})

        def side_effect(cmd):
            if "nameWithOwner" in " ".join(cmd):
                return "owner/repo"
            return page1 + "\n" + page2

        mock_cmd.side_effect = side_effect
        runs = get_check_runs_for_sha("abc123")
        assert [r["name"] for r in runs] == ["a", "b"]


class TestGetRunIdsForSha:
    """Test workflow-run id filtering by SHA and completion."""

    @patch("verify_green.run_cmd")
    def test_filters_wrong_sha_and_incomplete(self, mock_cmd):
        mock_cmd.return_value = json.dumps(
            [
                {"databaseId": 1, "status": "completed", "headSha": "sha_want"},
                {"databaseId": 2, "status": "completed", "headSha": "sha_other"},
                {"databaseId": 3, "status": "in_progress", "headSha": "sha_want"},
            ]
        )
        ids = get_run_ids_for_sha("sha_want")
        assert ids == ["1"]


class TestVerifyGreenIntegration:
    """Integration tests with run_cmd mocked to the REAL gh command shapes:
    gh pr view --json headRefOid / gh repo view --json nameWithOwner /
    gh api repos/<slug>/commits/<sha>/check-runs / gh pr diff /
    gh run list --commit / gh run view <id> --log
    """

    @staticmethod
    def make_side_effect(
        head_sha="sha_123",
        check_runs=None,
        diff="",
        run_ids=None,
        logs="All tests passed\n",
    ):
        check_runs = (
            check_runs
            if check_runs is not None
            else [{"name": "build", "status": "completed", "conclusion": "success"}]
        )
        run_ids = run_ids if run_ids is not None else [1]

        def side_effect(cmd):
            joined = " ".join(str(c) for c in cmd)
            if "headRefOid" in joined:
                return json.dumps({"headRefOid": head_sha})
            if "nameWithOwner" in joined:
                return "owner/repo"
            if "check-runs" in joined:
                return json.dumps({"check_runs": check_runs})
            if "diff" in joined:
                return diff
            if "run list" in joined or ("--commit" in joined):
                return json.dumps(
                    [
                        {"databaseId": rid, "status": "completed", "headSha": head_sha}
                        for rid in run_ids
                    ]
                )
            if "--log" in joined:
                return logs
            return ""

        return side_effect

    @patch("verify_green.run_cmd")
    def test_stale_sha_fails(self, mock_cmd):
        """No check-runs against the current head = the green badge was stale."""
        mock_cmd.side_effect = self.make_side_effect(check_runs=[])
        verdict = verify_green(123)
        assert verdict["errors"]
        assert any("previous head" in str(e) for e in verdict["errors"])

    @patch("verify_green.run_cmd")
    def test_skipped_check_fails(self, mock_cmd):
        mock_cmd.side_effect = self.make_side_effect(
            check_runs=[
                {"name": "build", "status": "completed", "conclusion": "skipped"}
            ]
        )
        verdict = verify_green(123)
        assert any("skipped" in str(e).lower() for e in verdict["errors"])

    @patch("verify_green.run_cmd")
    def test_in_progress_check_fails(self, mock_cmd):
        mock_cmd.side_effect = self.make_side_effect(
            check_runs=[{"name": "build", "status": "in_progress", "conclusion": None}]
        )
        verdict = verify_green(123)
        assert any("not completed" in str(e) for e in verdict["errors"])

    @patch("verify_green.run_cmd")
    def test_missing_test_in_log_fails(self, mock_cmd):
        mock_cmd.side_effect = self.make_side_effect(
            diff="+def test_new_feature():\n+    pass\n",
            logs="test_existing_feature PASSED\n",
        )
        verdict = verify_green(123)
        assert any("not found in" in str(e).lower() for e in verdict["errors"])

    @patch("verify_green.run_cmd")
    def test_module_error_in_logs_fails(self, mock_cmd):
        mock_cmd.side_effect = self.make_side_effect(
            logs="ModuleNotFoundError: no module named foo\n"
        )
        verdict = verify_green(123)
        assert any("ModuleNotFoundError" in str(e) for e in verdict["errors"])

    @patch("verify_green.run_cmd")
    def test_all_good_passes(self, mock_cmd):
        mock_cmd.side_effect = self.make_side_effect(
            diff="+def test_new_feature():\n+    pass\n",
            logs="test_new_feature PASSED\nAll tests passed\n",
        )
        verdict = verify_green(123)
        assert not verdict["errors"]
        assert verdict["tests_found_in_log"] == ["test_new_feature"]
