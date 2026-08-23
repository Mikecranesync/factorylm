# Insights 2026-08-23 — Hardening Pass

Source: `report-2026-08-23-072714.html` (CHARLIE `~/.claude/usage-data/`).
31 sessions analyzed, 2026-07-15 → 2026-08-19. 214 commits, 1,101h, 5,625 Bash calls.
Same top frictions as 2026-08-09 (premature green, duplicated parallel work,
environment stalls) — this pass turned the habits into enforcement.

## Implemented (live on CHARLIE 2026-08-23; distributed via `infra/claude/`)

| Item | Artifact | What it kills |
|---|---|---|
| Orphaned pyright/LSP reaper (SessionStart hook) | `infra/claude/hooks/reap-orphaned-lsp.sh` | CPU-thrash rediscovery (3 sessions). Kills only launchd-orphaned, TTY-less, >30-min LSP workers; logs to `~/.claude/reaped.log`; ctkd report-only. |
| Shared-file guard (PreToolUse hook) | `infra/claude/hooks/shared-file-guard.sh` | VERSION/CHANGELOG/hot.md conflict tax. Direct repo-root edits become a one-click permission prompt. Bypass: `CLAUDE_ALLOW_SHARED_FILE_EDITS=1`. |
| Ruff at edit time + unfixable-error feedback | `infra/claude/hooks/ruff-on-edit.sh` | Avoidable red-CI reruns; unfixable lint errors surface to the model immediately. |
| Verification Discipline rules | `infra/claude/CLAUDE-GLOBAL-RULES.md` | Stale-SHA green badges, phantom test runs, silent hazard omission — the #1 friction. |
| `/resume` skill | `infra/claude/skills/resume/SKILL.md` | Duplicated PRs from stale handoffs; auth/service preflight before work. |
| `/ship` hardened | `infra/claude/skills/ship.md` | SHA-pinned CI gate, tests-executed grep, hazard ledger, staging before/after behavioral diff. |
| `verify_green.py` | `scripts/verify_green.py` | Unfakeable green: SHA match, no skipped checks, new tests present in logs, no silent no-ops. JSON verdict artifact. |
| `agent_claim.py` claim ledger | `scripts/agent_claim.py` + `.agents/leases/` | Parallel-session duplicate work. Atomic O_EXCL claim with merged-work preflight, heartbeat, stale reaping. |

## Adoption notes

- `verify_green.py` is generic (`gh`-based, `--repo` flag). For the MIRA repo,
  wire it as a required step in the merge-pr/ship flow there; optionally add a
  Stop hook blocking session end on an unverified "ready to merge" claim.
- `agent_claim.py`: run `census` at session start, `claim` before implementation
  work. The claim preflight (refuses items already merged) is the direct fix for
  the duplicated-PRs incident.

## Machine-checked handoff format (convention)

Handoffs are a table, not prose: `item | PR# | branch | head SHA | CI state |
blocking hazard | next action`, plus a "verify before resuming" code block with
the exact gh/git commands re-checking every row. `/resume` consumes this mechanically.

## Overnight close-the-loop phase template (prompt discipline until automated)

1. **Baseline**: 8–10 live staging probes captured before any code. Staging already
   broken → STOP (never build on a dead layer).
2. **TDD**: failing tests first; full suite, not just the new file.
3. **Verify**: `verify_green.py` — SHA-pinned, no skips, tests provably ran.
4. **Behavioral diff**: deploy staging, settle, re-run probes. Identical output = failure.
5. **Promote or revert**: prod only on intended diff, rollback checkpoint,
   tag == VERSION == deployed; else auto-revert + file issue with evidence.
6. **Handoff**: table format, before/after probe outputs, explicit uninvestigated-hazard list.

## Confirmed-working patterns (do not change)

Handoff-driven continuity, class-level fixes over instance patches, refusing
unverified "done" — now encoded as hooks/skills/scripts rather than habits.
