# Claude Improvement Tracker

Every Claude Code usage-insights report we run gets an entry here, with each
recommendation tracked to a concrete, verifiable implementation. This is the
single place any session (or human) checks what has already been fixed, so the
same lesson is never re-learned and the same tooling is never rebuilt.

**Rule for future sessions:** before implementing anything suggested by an
insights report, check this tracker AND `gh pr list --state all --search <keyword>`.
If it's listed as implemented, verify the artifact still exists and move on.

## Reports

| Report | Period | Entry |
|---|---|---|
| 2026-07-06 | ~28 days to 2026-07-06 | [2026-07-06-output-limits-and-isolation.md](2026-07-06-output-limits-and-isolation.md) |
| 2026-08-09 | 2026-07-08 → 2026-08-04 | [2026-08-09-verification-and-parallelism.md](2026-08-09-verification-and-parallelism.md) |
| 2026-08-23 | 2026-07-15 → 2026-08-19 | [2026-08-23-hardening.md](2026-08-23-hardening.md) |

## Implementation status (consolidated, as of 2026-08-23)

| Recommendation (first appeared) | Status | Artifact |
|---|---|---|
| Long artifacts to file, never one giant chat response (07-06) | ✅ Implemented | `infra/claude/CLAUDE-GLOBAL-RULES.md` § Output Length |
| Subagent worktree isolation (07-06) | ✅ Implemented | § Subagent Worktree Isolation |
| Surface permission blocks once, never loop/evade (07-06) | ✅ Implemented | § Permission Gates |
| Verify subagent output against the code index (07-06 era) | ✅ Implemented | § Verify Subagent Output |
| Reconcile handoff vs repo state before working (08-09, 08-23) | ✅ Implemented | `/resume` skill — `infra/claude/skills/resume/SKILL.md` |
| SHA-pinned green + tests-actually-ran + hazard ledger (08-09, 08-23) | ✅ Implemented | `/ship` skill + `scripts/verify_green.py` |
| Machine-checked "green" verdict script (08-09, 08-23) | ✅ Implemented | `scripts/verify_green.py` (see entry for adoption notes) |
| Ruff format/lint at edit time, not CI time (08-09, 08-23) | ✅ Implemented | `infra/claude/hooks/ruff-on-edit.sh` |
| Shared-file (VERSION/CHANGELOG/hot.md) edit guard (08-09, 08-23) | ✅ Implemented | `infra/claude/hooks/shared-file-guard.sh` |
| Orphaned pyright/LSP reaper at session start (08-23) | ✅ Implemented | `infra/claude/hooks/reap-orphaned-lsp.sh` |
| Stop re-diagnosing / timebox analysis (08-09, 08-23) | ✅ Implemented | § Diagnose Once, Then Act |
| Environment preflight (gh auth, Docker, services) (08-09) | ✅ Implemented | `/resume` skill Step 4 |
| Claim ledger for parallel sessions (08-09, 08-23) | ✅ Implemented | `scripts/agent_claim.py` + `.agents/leases/` |
| Machine-checked handoff table format (08-23) | 🟡 Adopted as convention | `/resume` reconciles any handoff; table format documented in 08-23 entry |
| Overnight close-the-loop (baseline → behavioral diff → promote/revert) (08-09, 08-23) | 🟡 Prompt discipline | Phase template in 08-23 entry; automate once `verify_green.py` is adopted in target-repo CI |
| Mutation testing scoped to diff (08-09) | ⬜ Not built | Deliberate: heavy; revisit if false-green recurs after verify_green adoption |

## Distribution — how every session finds this

- **Any session in this repo**: root `CLAUDE.md` points here.
- **Any session on any cluster node**: `infra/claude/install.sh` installs the
  hooks + skills into `~/.claude/` and links `CLAUDE-GLOBAL-RULES.md` into the
  node's global `~/.claude/CLAUDE.md`. Nodes already pull this repo
  (`git -C ~/factorylm pull`), so `git pull && bash infra/claude/install.sh`
  is the full update path. See `infra/claude/README.md`.
