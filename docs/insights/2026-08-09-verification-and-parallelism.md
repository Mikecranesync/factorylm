# Insights 2026-08-09 — Verification, Parallel Sessions, Environment Traps

Source: `report-2026-08-09-062029.html` (CHARLIE `~/.claude/usage-data/`).
30 sessions analyzed, 2026-07-08 → 2026-08-04. 169 commits, 705h wall-clock,
4,643 Bash calls.

## Top friction

1. **Premature "done" / false-green** (14 buggy-code events): PR #3023 declared
   "green and done" with uninvestigated hazards; its own fix shipped three real
   bool/NaN/inf defects; new tests trusted without confirming they executed;
   ruff-format CI failures never run locally.
2. **Parallel sessions colliding**: PRs 4 and 5 rebuilt after a concurrent session
   had already merged them; VERSION/CHANGELOG rebase conflicts across 4+ sessions;
   a #3051 smoke failure caused by a concurrent #3067 prod deploy.
3. **Environment traps on unattended runs**: seven orphaned pyright workers pinning
   CPU; Colima down; gh auth expired twice; missing tesseract tainting a benchmark
   lane; a Stop hook that deadlocked by text-matching its own goal snippet.

## Recommendations → implementations

| Recommendation | Artifact | Status |
|---|---|---|
| Definition of Done: named CI checks, tests-provably-ran, local lint, explicit hazards | `/ship` skill + `CLAUDE-GLOBAL-RULES.md` § Verification Discipline + `scripts/verify_green.py` | ✅ |
| Parallel-session check before implementing | `/resume` skill + § Resume Reconciliation | ✅ |
| Shared-file conflict policy (dated fragments) | § Shared-File Policy + `infra/claude/hooks/shared-file-guard.sh` | ✅ |
| Stop re-diagnosing | § Diagnose Once, Then Act | ✅ |
| Deploy verification end-to-end (dead-staging-layer check) | `/ship` behavioral-diff step | ✅ |
| PostToolUse ruff hook | `infra/claude/hooks/ruff-on-edit.sh` | ✅ |
| SessionStart environment preflight | `/resume` Step 4 + `infra/claude/hooks/reap-orphaned-lsp.sh` | ✅ |
| Claim ledger for parallel agents | `scripts/agent_claim.py` | ✅ |
| Evidence-gated merge (test-ID assertion in CI logs) | `scripts/verify_green.py` | ✅ |
| Mutation testing scoped to diff | — | ⬜ deferred (heavy; revisit if false-green recurs) |
| Overnight self-healing backlog operator | phase template in 2026-08-23 entry | 🟡 prompt discipline |
