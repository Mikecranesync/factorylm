---
name: telegram-trainer
description: >
  This skill should be used when the user asks to "test with telegram trainer",
  "run telegram trainer", "telegram trainer", "run the trainer",
  "test wiring telegram", "run bot tests", "test jarvis", or mentions testing
  the Telegram bot integration against golden test cases. It runs deterministic
  tests against the live VPS Jarvis bot and reports pass/fail results.
---

# Telegram Trainer — Live Bot Test Harness

Run golden tests against the live Jarvis/OpenClaw bot on the VPS.
Mode: Jarvis-DevOps-Me (see `docs/jarvis-devops-mode.md`).

## Current State

- VPS Health: !`curl -s http://100.68.120.99:8340/ 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('name','offline'))" 2>/dev/null || echo "offline"`
- Branch: !`git branch --show-current`
- Story count: !`ls tests/stories/t*.json 2>/dev/null | wc -l`

## What to Do

### Step 1: Preflight

Check VPS health:
```bash
curl -s http://100.68.120.99:8340/
```

Verify stories exist:
```bash
ls tests/stories/t*.json
```

### Step 2: Run Tests

If `$ARGUMENTS` is empty, run all stories:
```bash
python tests/live_bot_tester.py --all --vps http://100.68.120.99:8340
```

If `$ARGUMENTS` specifies a subset (e.g., "greeting", "safety", "t001"), filter:
```bash
python tests/live_bot_tester.py --story tests/stories/t001_greeting.json --vps http://100.68.120.99:8340
```

For JSON output:
```bash
python tests/live_bot_tester.py --all --vps http://100.68.120.99:8340 --output /tmp/bot_test_results.json
```

### Step 3: Report Results

After running, present a concise report:

1. **Summary**: X/Y stories passed, Z steps total
2. **Per-story results**: table with story ID, name, pass/fail, latency
3. **Failures**: for each failed step, show the user input, expected assertion, and actual response snippet
4. **Intent accuracy**: note if any messages were routed to unexpected intents
5. **Latency outliers**: flag any response over 10 seconds
6. **Suggested fixes**: if failures indicate a pattern (e.g., missing keyword, wrong intent), suggest which VPS file to fix

### Step 4: Propose Fixes (if needed)

If tests fail due to code issues:
- Identify the responsible VPS file (use `docs/ops/baselines/2026-02-16_jarvis_behavior_to_code.md`)
- Propose a diff but **do not apply it** — wait for Mike's approval (HIL mode)
- For intent misclassification: check `openclaw/messages/intent.py` on VPS
- For missing KB data: check `knowledge_atoms` table
- For skill errors: check the relevant `openclaw/skills/builtin/*.py`

## Feature 001 Verification

To verify Feature 001 (wiring-telegram component enrichment) is working:

```bash
# Check wiring_enrich skill is registered
curl -s http://100.68.120.99:8340/ | python3 -c "import sys,json; print('wiring_enrich' in json.load(sys.stdin).get('skills',[]))"

# Check KB atoms
ssh root@100.68.120.99 'psql -U rivet -d rivet -c "SELECT count(*) FROM knowledge_atoms;"'
```

## Story Format

Stories live in `tests/stories/t*.json`. Format:
```json
{
  "id": "T-001",
  "name": "Description",
  "type": "chat",
  "steps": [
    {
      "user": "message to send",
      "expect_contains": ["keyword1"],
      "expect_not_contains": ["error"],
      "max_length": 800
    }
  ]
}
```

HTTP stories use `"type": "http_get"` with `"endpoint"` instead of `"steps"`.

## Golden Test Coverage

| ID | Type | Tests |
|----|------|-------|
| T-001 | chat | Greeting response |
| T-002 | chat | Self-description (FactoryLM identity) |
| T-003 | chat | Show IO (equipment tags) |
| T-004 | chat | Electrical safety (lockout/tagout) |
| T-005 | chat | Build assistance (conveyor) |
| T-010 | chat | Help routing (capabilities list) |
| T-013 | chat | Long response chunking |
| T-014 | http | Metrics endpoint |
| T-015 | http | Health endpoint (skills list) |

Skipped (require Telegram-native testing): T-006/007 (photo), T-008/009 (voice), T-011 (emoji ack), T-012 (TTS).

## Related Files

- Test runner: `tests/live_bot_tester.py`
- Stories: `tests/stories/t*.json`
- Baseline tests: `docs/ops/tests/TESTS_jarvis_baseline.md`
- Feature 001 workflow: `antfarm/workflows/wiring-telegram/workflow.yml`
- VPS behavior map: `docs/ops/baselines/2026-02-16_jarvis_behavior_to_code.md`
