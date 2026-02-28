# Dispatch Integration Developer Agent

**Mode:** Jarvis-DevOps-Me (see `docs/jarvis-devops-mode.md`)

You modify 3 VPS files to route note-type gist comments through the dispatch pipeline instead of sending dumb notification strings.

## Your Role

You make the smallest set of changes to wire gist comments into the existing dispatch system. Note-type comments become `InboundMessage` objects, get intent-classified, run through skills, and the response goes back to Mike via Telegram.

## Files to Modify (VPS: /opt/openclaw/)

### 1. openclaw/monitor.py — CapabilityMonitor

**Changes to `__init__`:**
```python
class CapabilityMonitor:
    def __init__(
        self,
        sm: StateMachine,
        notify: Callable,
        poll_interval: float = 300.0,
        dispatch: Callable | None = None,   # NEW
        owner_id: str = "",                  # NEW
    ):
        self._sm = sm
        self._notify = notify
        self._poll_interval = poll_interval
        self._dispatch = dispatch            # NEW
        self._owner_id = owner_id            # NEW
```

**Changes to gist poll block (inside the monitor loop):**

When `poll_all_gists()` returns notifications, handle each by type:

```python
for notif in notifications:
    wo_id = notif["wo_id"]
    gist_id = notif["gist_id"]
    user = notif["user"]
    comment_id = notif["comment_id"]

    if notif["type"] == "command":
        # Command-type: unchanged — update already applied by gist_poller
        await self._notify(
            f"WO {wo_id} updated: {notif['field']} -> {notif['value']} (by {user})"
        )

    elif notif["type"] == "note":
        body = notif["body"]

        if self._dispatch is not None:
            try:
                from openclaw.models import InboundMessage, Channel
                msg = InboundMessage(
                    id=f"gist-{comment_id}",
                    channel=Channel.TELEGRAM,
                    user_id=self._owner_id,
                    user_name=user,
                    text=f"[WO {wo_id}] {body}",
                    metadata={
                        "source": "gist_comment",
                        "gist_id": gist_id,
                        "wo_id": wo_id,
                    },
                )
                response = await self._dispatch(msg)
                await self._notify(f"Re: {wo_id}\n{response.text}")
            except Exception:
                logger.warning(
                    "Dispatch failed for gist comment %s on %s",
                    comment_id, wo_id, exc_info=True,
                )
                # Fall through to basic notification
                await self._notify(
                    f"Comment on {wo_id} by {user}:\n{body[:200]}"
                )
        else:
            # No dispatch wired — basic notification
            await self._notify(
                f"Comment on {wo_id} by {user}:\n{body[:200]}"
            )
```

### 2. openclaw/app.py — startup()

Pass `dispatch` and `owner_id` to `CapabilityMonitor`:

```python
monitor = CapabilityMonitor(
    sm=state_machine,
    notify=notify_telegram,
    poll_interval=300.0,
    dispatch=dispatch,                              # NEW
    owner_id=str(config.telegram_allowed_users[0]), # NEW
)
```

The `dispatch` function already exists in `app.py` — it's the main message handler that classifies intent and runs skills. We just pass a reference to it.

### 3. openclaw/gist_poller.py — body cap

Change the note-type body truncation from 200 to 500 characters so dispatch gets enough text to classify intent:

```python
# Before (line ~192):
notif["body"] = comment["body"][:200]

# After:
notif["body"] = comment["body"][:500]
```

## Key Principles

- **Minimal changes**: only touch what's needed for dispatch routing
- **Backward compatible**: if dispatch=None, behavior is identical to v1.5-rc2
- **Command-type unchanged**: `status: completed` etc. still update gist metadata directly
- **Note-type dispatched**: free-text comments go through intent classify -> skill -> response
- **Error resilient**: if dispatch raises, log warning and fall back to basic notification

## Tests to Write

After implementation, create `tests/test_gist_dispatch.py` with 6 tests:

| # | Test | What it validates |
|---|------|-------------------|
| 1 | `test_command_comment_notifies_only` | Command-type bypasses dispatch, calls notify with field->value |
| 2 | `test_note_comment_dispatches` | Note-type builds InboundMessage, calls dispatch |
| 3 | `test_dispatch_response_sent_via_notify` | dispatch response.text forwarded through notify |
| 4 | `test_dispatch_failure_logs_warning` | If dispatch raises, warning logged, no crash |
| 5 | `test_no_dispatch_falls_back` | dispatch=None -> note-type sends formatted notification |
| 6 | `test_inbound_message_has_wo_context` | text starts with `[WO WO-YYYY-MMDD-NNN]` |

### InboundMessage Construction Pattern

```python
InboundMessage(
    id=f"gist-{comment_id}",
    channel=Channel.TELEGRAM,
    user_id=owner_id,
    user_name=user,
    text=f"[WO {wo_id}] {body}",
    metadata={"source": "gist_comment", "gist_id": gist_id, "wo_id": wo_id},
)
```

The `[WO {wo_id}]` prefix gives the skill system work order context without changing the dispatch interface.

## Example

**Input:**
```
Modify monitor.py, app.py, and gist_poller.py for dispatch integration.
```

**Output:**
```
FILES_MODIFIED: 3
MONITOR_CHANGES: dispatch param, owner_id param, InboundMessage construction, dispatch call
APP_CHANGES: pass dispatch + owner_id to CapabilityMonitor
POLLER_CHANGES: body cap 200 -> 500
RESULT: pass
STATUS: done
```
