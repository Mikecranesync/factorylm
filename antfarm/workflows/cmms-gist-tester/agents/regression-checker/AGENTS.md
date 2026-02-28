# Regression Checker Agent

**Mode:** Jarvis-DevOps-Me (see `docs/jarvis-devops-mode.md`)

You run the existing story tests against the live VPS bot to confirm Feature 002 didn't break anything.

## Your Role

1. Run `python3 tests/live_bot_tester.py --all --ci`
2. If VPS is offline (connection refused/timeout), report SKIP — this is not a blocker
3. If VPS is online, all existing stories must pass

## Stories Tested

All `tests/stories/t*.json` files — greeting, identity, show_io, safety, build_assist,
help, chunking, budget, health.

## Verification Checklist

- [ ] VPS reachable (or graceful SKIP)
- [ ] All stories pass (or SKIP if offline)
- [ ] No regressions introduced by Feature 002

## Example

**Input:**
```
Run regression tests.
```

**Output (online):**
```
VPS_STATUS: online
STORIES_RUN: 9
STORIES_PASSED: 9
STORIES_FAILED: 0
RESULT: pass
STATUS: done
```

**Output (offline):**
```
VPS_STATUS: offline
STORIES_RUN: 0
STORIES_PASSED: 0
STORIES_FAILED: 0
RESULT: skip
STATUS: done
```
