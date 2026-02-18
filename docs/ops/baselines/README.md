# Baselines

## What is a Baseline?

A baseline captures the **known-good behavioral state** of a service at a point in time. Unlike config snapshots (which capture settings), baselines capture:

- **Expected input/output behavior** — test cases with qualitative pass criteria
- **Code-to-behavior mapping** — which Python file produces which observable behavior
- **Personality/style characteristics** — for AI services like Jarvis
- **Performance expectations** — response time, error rate, provider routing

A baseline answers: "If we had to rebuild this service from scratch, what should it do?"

## When to Create a Baseline

- After a major feature milestone is verified working
- Before a risky refactor or migration
- After restoring a service from a broken state
- When establishing a "known-good" for regression testing

## File Naming

- `YYYY-MM-DD_service_baseline.md` — The behavioral snapshot
- `YYYY-MM-DD_service_behavior_to_code.md` — Behavior-to-code mapping

Each baseline links to:
- `../tests/TESTS_service_baseline.md` — Golden test cases
- `../workflows/check-service-baseline.md` — Repeatable verification workflow
- `../config-snapshots/YYYY-MM-DD_service.yaml` — Config at baseline time

## How Baselines Are Used

1. **Regression detection**: Run test cases after any change — if a test fails, the change broke something
2. **Resurrection**: If a service dies, baseline + test cases = rebuild spec
3. **Handoff**: New developers can understand expected behavior without reading all the code
4. **Drift detection**: Compare current behavior against baseline periodically
5. **Digital twin**: The JARVIS-IS-DEAD repo freezes baselines as a resurrection kit

## Relationship to Other Artifacts

| Artifact | Captures | Baseline Adds |
|----------|----------|---------------|
| Config Snapshot | Settings and env vars | Expected behavior those settings produce |
| Trace | What changed and why | What the "before" state should look like |
| Workflow | How to do a procedure | What the result should look like |
| Tests | How to verify | The actual pass/fail criteria |

## Current Baselines

| Date | Service | Tag | Status |
|------|---------|-----|--------|
| 2026-02-16 | openclaw (Jarvis) | v0.9.0-jarvis-baseline | active |
