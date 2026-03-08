"""Unit tests for Feature 003 — Gist Comment Dispatch integration.

Validates that note-type gist comments are routed through dispatch()
(intent classify -> skill -> response) while command-type comments
bypass dispatch and use notify directly.

All mocked — no VPS, GitHub API, or Telegram required.
"""

from __future__ import annotations

import asyncio
import logging
import unittest
from dataclasses import dataclass
from unittest.mock import AsyncMock

from openclaw.gist_dispatch import process_gist_notification
from openclaw.messages.models import InboundMessage
from openclaw.types import Channel


# ── Test-only response stub ──────────────────────────────────────────────────

@dataclass
class Response:
    text: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(coro):
    """Run an async coroutine in a new event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


COMMAND_NOTIF = {
    "wo_id": "WO-2026-0217-001",
    "gist_id": "abc123",
    "type": "command",
    "field": "status",
    "value": "completed",
    "user": "Mikecranesync",
    "comment_id": 42,
}

NOTE_NOTIF = {
    "wo_id": "WO-2026-0217-001",
    "gist_id": "abc123",
    "type": "note",
    "body": "draw me a wiring diagram for this motor",
    "user": "Mikecranesync",
    "comment_id": 43,
}

OWNER_ID = "8445149012"


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestCommandCommentNotifiesOnly(unittest.TestCase):
    """Test 1: Command-type bypasses dispatch, uses notify."""

    def test_command_comment_notifies_only(self):
        dispatch = AsyncMock(return_value=Response(text="should not be called"))
        notify = AsyncMock()

        _run(process_gist_notification(COMMAND_NOTIF, dispatch, notify, OWNER_ID))

        dispatch.assert_not_called()
        notify.assert_called_once()
        msg = notify.call_args[0][0]
        assert "updated: status -> completed" in msg
        assert "Mikecranesync" in msg


class TestNoteCommentDispatches(unittest.TestCase):
    """Test 2: Note-type builds InboundMessage, calls dispatch."""

    def test_note_comment_dispatches(self):
        dispatch = AsyncMock(return_value=Response(text="Check bearing alignment"))
        notify = AsyncMock()

        _run(process_gist_notification(NOTE_NOTIF, dispatch, notify, OWNER_ID))

        dispatch.assert_called_once()
        msg = dispatch.call_args[0][0]
        assert isinstance(msg, InboundMessage)
        assert msg.channel == Channel.TELEGRAM
        assert msg.user_id == OWNER_ID
        assert msg.user_name == "Mikecranesync"
        assert msg.metadata["source"] == "gist_comment"
        assert msg.metadata["gist_id"] == "abc123"


class TestDispatchResponseSentViaNotify(unittest.TestCase):
    """Test 3: dispatch response.text forwarded through notify."""

    def test_dispatch_response_sent_via_notify(self):
        dispatch = AsyncMock(return_value=Response(text="Check bearing alignment"))
        notify = AsyncMock()

        _run(process_gist_notification(NOTE_NOTIF, dispatch, notify, OWNER_ID))

        notify.assert_called_once()
        msg = notify.call_args[0][0]
        assert "Re: WO-2026-0217-001" in msg
        assert "Check bearing alignment" in msg


class TestDispatchFailureLogsWarning(unittest.TestCase):
    """Test 4: If dispatch raises, warning logged, no crash."""

    def test_dispatch_failure_logs_warning(self):
        dispatch = AsyncMock(side_effect=RuntimeError("LLM provider down"))
        notify = AsyncMock()

        with self.assertLogs("openclaw.gist_dispatch", level="WARNING") as cm:
            _run(process_gist_notification(NOTE_NOTIF, dispatch, notify, OWNER_ID))

        # Should not crash — notify called with fallback
        notify.assert_called_once()
        fallback_msg = notify.call_args[0][0]
        assert "Comment on WO-2026-0217-001" in fallback_msg
        assert "Mikecranesync" in fallback_msg
        # Warning was logged
        assert any("Dispatch failed" in line for line in cm.output)


class TestNoDispatchFallsBack(unittest.TestCase):
    """Test 5: dispatch=None -> note-type sends formatted notification."""

    def test_no_dispatch_falls_back(self):
        notify = AsyncMock()

        _run(process_gist_notification(NOTE_NOTIF, None, notify, OWNER_ID))

        notify.assert_called_once()
        msg = notify.call_args[0][0]
        assert "Comment on WO-2026-0217-001 by Mikecranesync" in msg
        assert "draw me a wiring diagram" in msg


class TestInboundMessageHasWoContext(unittest.TestCase):
    """Test 6: text starts with [WO WO-YYYY-MMDD-NNN]."""

    def test_inbound_message_has_wo_context(self):
        captured_msg = {}

        async def _capture_dispatch(msg):
            captured_msg["msg"] = msg
            return Response(text="ok")

        notify = AsyncMock()

        _run(process_gist_notification(NOTE_NOTIF, _capture_dispatch, notify, OWNER_ID))

        msg = captured_msg["msg"]
        assert msg.text.startswith("[WO WO-2026-0217-001]")
        assert "draw me a wiring diagram for this motor" in msg.text
        assert msg.id == "gist-43"
        assert msg.metadata["wo_id"] == "WO-2026-0217-001"


if __name__ == "__main__":
    unittest.main()
