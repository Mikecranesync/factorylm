# infra/claude — Cluster-wide Claude Code Hardening

Canonical, version-controlled home of the Claude improvements derived from
usage-insights reports. Tracking and provenance: [`docs/insights/`](../../docs/insights/README.md).

## Contents

| Path | What |
|---|---|
| `CLAUDE-GLOBAL-RULES.md` | Insights-derived working rules, imported into each node's `~/.claude/CLAUDE.md` |
| `hooks/reap-orphaned-lsp.sh` | SessionStart: reap orphaned pyright/LSP workers (logs to `~/.claude/reaped.log`) |
| `hooks/shared-file-guard.sh` | PreToolUse: VERSION/CHANGELOG/hot.md edits become a permission prompt |
| `hooks/ruff-on-edit.sh` | PostToolUse: auto-format .py edits, feed unfixable lint errors back to the model |
| `skills/resume/SKILL.md` | `/resume` — reconcile handoff vs repo state + env preflight before any work |
| `skills/ship.md` | `/ship` — SHA-pinned CI gate, hazard ledger, behavioral diff, merge & deploy |
| `install.sh` | Idempotent installer for all of the above |

Related repo tooling (installed nowhere — invoked by path):
- `scripts/verify_green.py <pr>` — machine-checked green verdict (SHA-pinned, no
  skipped checks, new tests provably executed, no silent no-ops)
- `scripts/agent_claim.py` — atomic work-claim ledger for parallel sessions

## Install / update on any node

```bash
git -C ~/factorylm pull
bash ~/factorylm/infra/claude/install.sh
```

Idempotent. New sessions pick everything up automatically; already-running
sessions need `/hooks` opened once (or a restart) to load new hook registrations.

## Editing policy

Edit the copies HERE, ship via PR, then re-run `install.sh` on each node —
never hand-edit `~/.claude/hooks/` copies, they get overwritten on the next install.
