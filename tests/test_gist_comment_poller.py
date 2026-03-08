"""Unit tests for openclaw.gist_poller — gist comment polling & command parsing.

All tests mock subprocess/filesystem — no VPS or GitHub required.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: stub out the VPS-only subpackages that gist_poller lazily imports
# so tests can run from the monorepo without the full openclaw installation.
# ---------------------------------------------------------------------------
# gist_poller does a lazy `from openclaw.skills.builtin.gist_work_order import ...`
# inside poll_all_gists(), so we only need these stubs to exist in sys.modules.
_mock_update = MagicMock(return_value={"gist_id": "abc", "gist_url": "https://gist.github.com/abc"})

for _mod_name in (
    "openclaw.skills",
    "openclaw.skills.builtin",
    "openclaw.skills.builtin.gist_work_order",
):
    if _mod_name not in sys.modules:
        _m = types.ModuleType(_mod_name)
        if _mod_name.endswith("gist_work_order"):
            _m.update_work_order_gist = _mock_update
        sys.modules[_mod_name] = _m

from openclaw.gist_poller import (
    fetch_gist_comments,
    list_work_order_gists,
    parse_comment_command,
    poll_all_gists,
    _load_seen,
    _save_seen,
    SEEN_FILE,
)


# ── parse_comment_command ────────────────────────────────────────────────

class TestParseCommentCommand:
    def test_parse_status_command(self):
        result = parse_comment_command("status: completed")
        assert result == {"type": "command", "field": "status", "value": "completed"}

    def test_parse_priority_command(self):
        result = parse_comment_command("priority: critical")
        assert result == {"type": "command", "field": "priority", "value": "critical"}

    def test_parse_assign_command(self):
        result = parse_comment_command("assign: John")
        assert result == {"type": "command", "field": "assign", "value": "John"}

    def test_parse_category_command(self):
        result = parse_comment_command("category: Electrical")
        assert result == {"type": "command", "field": "category", "value": "Electrical"}

    def test_parse_freetext_note(self):
        result = parse_comment_command("Just a regular comment about the motor")
        assert result["type"] == "note"
        assert "regular comment" in result["raw"]

    def test_parse_case_insensitive(self):
        result = parse_comment_command("STATUS: In Progress")
        assert result == {"type": "command", "field": "status", "value": "In Progress"}

    def test_parse_multiline_first_match(self):
        body = "Some preamble text\nstatus: completed\npriority: high"
        result = parse_comment_command(body)
        assert result["type"] == "command"
        assert result["field"] == "status"
        assert result["value"] == "completed"


# ── list_work_order_gists ────────────────────────────────────────────────

class TestListWorkOrderGists:
    @patch("openclaw.gist_poller.subprocess.run")
    def test_list_work_order_gists_filters(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "abc123\t[Jarvis Work Order] WO-2026-0217-001 — Motor\t1 file\tpublic\n"
                "def456\tRandom notes gist\t2 files\tsecret\n"
                "ghi789\t[Jarvis Work Order] WO-2026-0217-002 — Pump\t3 files\tpublic\n"
            ),
        )
        gists = list_work_order_gists()
        assert len(gists) == 2
        assert gists[0]["id"] == "abc123"
        assert "[Jarvis Work Order]" in gists[0]["description"]
        assert gists[1]["id"] == "ghi789"


# ── fetch_gist_comments ─────────────────────────────────────────────────

class TestFetchGistComments:
    @patch("openclaw.gist_poller.subprocess.run")
    def test_fetch_gist_comments_parses_json(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {
                    "id": 100,
                    "body": "status: completed",
                    "user": {"login": "Mikecranesync"},
                    "created_at": "2026-02-17T12:00:00Z",
                },
                {
                    "id": 101,
                    "body": "Looks good",
                    "user": {"login": "otheruser"},
                    "created_at": "2026-02-17T12:05:00Z",
                },
            ]),
        )
        comments = fetch_gist_comments("abc123")
        assert len(comments) == 2
        assert comments[0]["id"] == 100
        assert comments[0]["user"] == "Mikecranesync"
        assert comments[1]["body"] == "Looks good"


# ── poll_all_gists ───────────────────────────────────────────────────────

class TestPollAllGists:
    @patch("openclaw.gist_poller._save_seen")
    @patch("openclaw.gist_poller._load_seen")
    @patch("openclaw.gist_poller.fetch_gist_comments")
    @patch("openclaw.gist_poller.list_work_order_gists")
    def test_poll_new_comments_detected(
        self, mock_list, mock_fetch, mock_load, mock_save
    ):
        mock_list.return_value = [
            {"id": "abc123", "description": "[Jarvis Work Order] WO-2026-0217-001 — Motor"},
        ]
        mock_fetch.return_value = [
            {"id": 100, "body": "status: completed", "user": "Mike", "created_at": ""},
        ]
        mock_load.return_value = {}  # First run — no seen state

        notifications = poll_all_gists()
        assert len(notifications) == 1
        assert notifications[0]["type"] == "command"
        assert notifications[0]["field"] == "status"
        assert notifications[0]["value"] == "completed"
        assert notifications[0]["wo_id"] == "WO-2026-0217-001"
        mock_save.assert_called_once()

    @patch("openclaw.gist_poller._save_seen")
    @patch("openclaw.gist_poller._load_seen")
    @patch("openclaw.gist_poller.fetch_gist_comments")
    @patch("openclaw.gist_poller.list_work_order_gists")
    def test_poll_no_new_comments(
        self, mock_list, mock_fetch, mock_load, mock_save
    ):
        mock_list.return_value = [
            {"id": "abc123", "description": "[Jarvis Work Order] WO-2026-0217-001 — Motor"},
        ]
        mock_fetch.return_value = [
            {"id": 100, "body": "status: completed", "user": "Mike", "created_at": ""},
        ]
        # Already seen comment 100
        mock_load.return_value = {
            "abc123": {"last_seen_comment_id": 100, "wo_description": "..."},
        }

        notifications = poll_all_gists()
        assert len(notifications) == 0


# ── seen file corruption ────────────────────────────────────────────────

class TestSeenFileFallback:
    def test_seen_file_corrupt_fallback(self, tmp_path):
        """Corrupt JSON should not crash — returns empty dict."""
        corrupt_file = tmp_path / "seen_comments.json"
        corrupt_file.write_text("{invalid json!!", encoding="utf-8")

        with patch("openclaw.gist_poller.SEEN_FILE", corrupt_file):
            result = _load_seen()
        assert result == {}
