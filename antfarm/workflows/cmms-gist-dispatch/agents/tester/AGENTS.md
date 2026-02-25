# Dispatch Test Runner Agent

**Mode:** Jarvis-DevOps-Me (see `docs/jarvis-devops-mode.md`)

You create and run `tests/test_gist_dispatch.py` with 6 unit tests that validate the gist comment dispatch integration.

## Your Role

You write tests that verify:
1. Command-type comments bypass dispatch and use notify directly
2. Note-type comments build an InboundMessage and call dispatch
3. Dispatch response text gets forwarded through notify
4. Dispatch failures are logged as warnings without crashing
5. When dispatch is None, note-type comments fall back to formatted notification
6. The InboundMessage text field has WO context prefix

## Test File: tests/test_gist_dispatch.py

All tests are mocked — no VPS, no GitHub API, no Telegram. Use `unittest` + `unittest.mock`.

Inline the gist comment dispatch logic (same pattern as `tests/test_state_machine.py` which inlines `StateMachine` and `CapabilityMonitor`).

### Inline Types

```python
from dataclasses import dataclass, field
from enum import Enum

class Channel(str, Enum):
    TELEGRAM = "telegram"

@dataclass
class InboundMessage:
    id: str
    channel: Channel
    user_id: str
    user_name: str
    text: str
    metadata: dict = field(default_factory=dict)

@dataclass
class Response:
    text: str
```

### Inline Dispatch Logic

```python
async def process_gist_notification(notif, dispatch, notify, owner_id):
    """Process a single gist notification — mirrors CapabilityMonitor logic."""
    wo_id = notif["wo_id"]
    gist_id = notif["gist_id"]
    user = notif["user"]
    comment_id = notif["comment_id"]

    if notif["type"] == "command":
        await notify(
            f"WO {wo_id} updated: {notif['field']} -> {notif['value']} (by {user})"
        )
        return

    # note-type
    body = notif["body"]

    if dispatch is not None:
        try:
            msg = InboundMessage(
                id=f"gist-{comment_id}",
                channel=Channel.TELEGRAM,
                user_id=owner_id,
                user_name=user,
                text=f"[WO {wo_id}] {body}",
                metadata={"source": "gist_comment", "gist_id": gist_id, "wo_id": wo_id},
            )
            response = await dispatch(msg)
            await notify(f"Re: {wo_id}\n{response.text}")
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                "Dispatch failed for gist comment %s on %s",
                comment_id, wo_id, exc_info=True,
            )
            await notify(f"Comment on {wo_id} by {user}:\n{body[:200]}")
    else:
        await notify(f"Comment on {wo_id} by {user}:\n{body[:200]}")
```

### The 6 Tests

| # | Test | Setup | Assert |
|---|------|-------|--------|
| 1 | `test_command_comment_notifies_only` | notif type=command, dispatch=AsyncMock | dispatch NOT called, notify called with "updated: field -> value" |
| 2 | `test_note_comment_dispatches` | notif type=note, dispatch=AsyncMock(return_value=Response("...")) | dispatch called with InboundMessage, msg.channel == TELEGRAM |
| 3 | `test_dispatch_response_sent_via_notify` | notif type=note, dispatch returns Response(text="Check bearing alignment") | notify called with "Re: WO-...\nCheck bearing alignment" |
| 4 | `test_dispatch_failure_logs_warning` | notif type=note, dispatch raises RuntimeError | No crash, notify called with fallback "Comment on WO-..." |
| 5 | `test_no_dispatch_falls_back` | notif type=note, dispatch=None | notify called with "Comment on WO-... by user:\nbody" |
| 6 | `test_inbound_message_has_wo_context` | notif type=note with wo_id="WO-2026-0217-001" | captured InboundMessage.text starts with "[WO WO-2026-0217-001]" |

### Test Data Fixtures

```python
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
```

## Running

```bash
python3 -m pytest tests/test_gist_dispatch.py -v
```

All 6 must pass.

## Example

**Input:**
```
Run dispatch integration tests.
```

**Output:**
```
TESTS_RUN: 6
TESTS_PASSED: 6
TESTS_FAILED: 0
RESULT: pass
STATUS: done
```
