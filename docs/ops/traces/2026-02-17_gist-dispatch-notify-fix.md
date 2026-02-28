# TRC-2026-02-17-006: Fix Gist Dispatch Notifications + Diagram-to-Gist

| Field | Value |
|-------|-------|
| **ID** | TRC-2026-02-17-006 |
| **Date** | 2026-02-17 |
| **Author** | Claude Code |
| **Duration** | 10m |
| **Type** | fix / feature-build |
| **Services** | openclaw |
| **Devices** | vps |
| **Trigger** | Live test showed gist dispatch runs but Telegram notifications silently dropped due to empty `telegram_allowed_users` config |

---

## Context

Feature 003 (CMMS Gist Work Order dispatch) was deployed and working — intent classification, LLM skill routing, and diagram rendering all fired correctly. But the live test revealed `_send_notification` silently drops all messages when `telegram_allowed_users: []` in Doppler/config. The dispatch executed but Mike never received the response on Telegram.

Additionally, Mike wanted dispatch responses written back into the gist body as a `dispatch-response.md` file, and start/finish Telegram notifications around dispatch processing.

## What Happened

1. Read current `app.py` and `monitor.py` from VPS to understand existing code
2. Modified `app.py`: added `_owner_chat_id` variable seeded from config but dynamically captured from first Telegram message via `_tracking_dispatch` wrapper — eliminates dependency on `telegram_allowed_users` being non-empty
3. Modified `monitor.py`: added start/done Telegram notifications around dispatch, added `_update_gist_with_response` method that writes `dispatch-response.md` file back into the WO gist via `gh api`
4. Verified diffs, deployed both files via SCP, restarted openclaw
5. Clean startup confirmed — OpenClaw v1.5.0-rc2 running with all skills and capabilities

## Changes Made

| File/Config | Before | After | Why |
|-------------|--------|-------|-----|
| `openclaw/app.py` | `_send_notification` required `config.telegram_allowed_users` non-empty | Uses `_owner_chat_id` captured dynamically from first Telegram message | Fix silent notification drop when config list is empty |
| `openclaw/app.py` | `dispatch` passed directly to monitor | `_tracking_dispatch` wrapper captures owner_id then delegates | Enables dynamic owner capture without config change |
| `openclaw/monitor.py` | No start/done notifications around dispatch | Sends "Processing..." before and "Re: WO-..." after dispatch | User visibility into gist comment processing |
| `openclaw/monitor.py` | No gist write-back | `_update_gist_with_response` adds `dispatch-response.md` to gist | Diagram/response visible in gist, not just Telegram |

## Outcome

- OpenClaw restarts cleanly, Telegram adapter and monitor running
- First Telegram message from Mike will capture `_owner_chat_id` for all future notifications
- Gist comment dispatch will send start/done Telegram messages and write response back to gist
- No config/Doppler changes needed

## Queryable Tags

- **root-cause**: `telegram_allowed_users` empty in Doppler, `_send_notification` guard silently dropped all notifications
- **config-keys**: TELEGRAM_ALLOWED_USERS
- **ports**: 8340
- **dependencies**: gh CLI

## Related

- **Prior Traces**: [TRC feature-003-state-machine](./feature-003-state-machine.md)
- **Prior Traces**: [TRC gist-project-skills](./2026-02-17_gist-project-skills.md)
