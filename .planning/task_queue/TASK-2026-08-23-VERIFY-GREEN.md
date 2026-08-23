# TASK-2026-08-23-VERIFY-GREEN

## Why this exists
Three usage-insights reports (2026-07-06, 2026-08-09, 2026-08-23) identify premature
"green and done" claims as the #1 friction: green CI badges read against a stale SHA,
required checks that silently skipped, new tests that never executed, workflows that
no-opped on missing deps. This task makes "green" a machine-checked verdict.

## Context / SSoT
- docs/insights/README.md (this branch) — tracker
- ~/.claude/usage-data/hardening-plan-2026-08-23.md — spec source ("strategy 1")
- /ship skill Step 1 — the manual checklist this script automates

## Deliverable
`scripts/verify_green.py <pr-number> [--repo owner/name]` — stdlib-only Python 3.9
(`Optional[X]`, not `X | None`), shells out to `gh` CLI. Exit 0 only if ALL hold:
1. Newest completed check-run set reports against the PR's CURRENT head
   (`gh pr view --json headRefOid` == the SHA the runs report for).
2. Every required/reported check concluded `success` — `skipped`/`neutral`/`cancelled`
   on any check is enumerated and FAILS the verdict.
3. If the PR diff adds test functions (parse `gh pr diff` for `^+\s*def test_`),
   each new test name must appear in the CI run logs (`gh run view --log`).
4. Run logs contain none of: `ModuleNotFoundError`, `command not found`.
Writes JSON verdict `{pr, sha, checks:[{name,conclusion}], tests_added, tests_found_in_log, verdict}`
to stdout and to `.verify_green/<pr>-<sha>.json`. Non-zero exit + reason on any failure.

## Acceptance criteria (measurable)
- `python3 scripts/verify_green.py --self-test` runs offline unit checks of the pure
  functions (SHA compare, conclusion classification, new-test extraction from a diff
  string, log scanning) and prints PASS; exit 0.
- pytest file `tests/test_verify_green.py` covers: stale-SHA fail, skipped-check fail,
  missing-test-in-log fail, ModuleNotFoundError fail, all-good pass — mocking gh calls.
- `python3 -m py_compile scripts/verify_green.py` passes on Python 3.9.
- No network/gh calls in tests.
