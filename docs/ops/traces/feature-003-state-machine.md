# Feature 003 — State Machine + Capability Monitor

**Date**: 2026-02-17
**Branch**: `feat/state-machine` (VPS) / `test/cmms-gist-comprehensive` (monorepo)
**Tag**: `v1.5-rc1`
**Status**: RC1 deployed, awaiting manual testing

## What Changed

### VPS (`/opt/openclaw/`)

| File | Change |
|------|--------|
| `openclaw/types.py` | Added `BotState` and `CapabilityStatus` enums |
| `openclaw/state.py` | **NEW** — StateMachine class with capability registry, health checks, recovery |
| `openclaw/monitor.py` | **NEW** — Background monitor loop (45s), auto-recovery, systemd watchdog, Telegram notifications |
| `openclaw/app.py` | Wired state machine: register 10 capabilities, dispatch guard, degradation warnings |
| `openclaw/gateway/telegram.py` | Added TTS/LLM capability guards, state_machine constructor param |
| `openclaw/observability/health.py` | Replaced with `state_machine.summary()` |
| `/etc/systemd/system/openclaw.service` | `Type=notify`, `WatchdogSec=120`, `NotifyAccess=all` |

### Monorepo

| File | Change |
|------|--------|
| `tests/test_state_machine.py` | 20 unit tests (all mocked, standalone) |
| `tests/test_state_machine_e2e.py` | 5 E2E tests against live VPS |
| `antfarm/workflows/state-machine-tester/` | 5-agent tester workflow |

## Capabilities Registered (10)

| Name | Critical | Status at Boot |
|------|----------|---------------|
| `groq` | no | UP |
| `nvidia` | no | UP |
| `anthropic` | no | UP |
| `gemini` | no | UP |
| `llm_primary` | **YES** | UP |
| `matrix` | no | DOWN (expected — no active server) |
| `knowledge` | no | UP |
| `tts` | no | UP |
| `gh_cli` | no | UP |
| `budget` | no | UP |

## Test Results

- Unit tests: **20/20 pass**
- E2E tests: **5/5 pass**
- Initial VPS state: `DEGRADED` (matrix connector down — expected)
- Watchdog: stable, no false restarts in 2+ minutes

## Rollback

```bash
cd /opt/openclaw && git checkout v1.4 && systemctl restart openclaw
```

## Next Steps

- Manual Telegram testing (Rounds 1-5) with Mike
- Verify state transitions: HEALTHY → DEGRADED → CRITICAL → recovery
- Tag v1.5 after Mike approves
