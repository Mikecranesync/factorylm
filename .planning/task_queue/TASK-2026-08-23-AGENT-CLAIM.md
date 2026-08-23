# TASK-2026-08-23-AGENT-CLAIM

## Why this exists
Insights reports 2026-08-09 and 2026-08-23: parallel Claude sessions rebuilt PRs a
concurrent session had already merged ("prs are already done are you just duplicating?").
A lease/claim ledger makes duplicate work structurally impossible.

## Context / SSoT
- docs/insights/README.md (this branch) — tracker
- ~/.claude/usage-data/hardening-plan-2026-08-23.md — spec source ("strategy 2")
- Pattern precedent: per-run dated fragment files (the wiki/hot.md conflict fix)

## Deliverable
`scripts/agent_claim.py` — stdlib-only Python 3.9 (`Optional[X]`, not `X | None`).
Leases live in `.agents/leases/<item-slug>.json`:
`{agent_id, item, worktree, branch, started_at, heartbeat_at, status}`.
Subcommands:
- `claim <item> [--agent-id X] [--worktree P] [--branch B]` — atomic via
  `os.open(O_CREAT|O_EXCL)`. Fails (exit 1) if a lease exists with heartbeat fresher
  than `--stale-hours` (default 4). PREFLIGHT before claiming: run
  `gh pr list --state all --search <item>` and `git log --all --grep=<item> --oneline`;
  refuse the claim (exit 2, distinct message) if the work already appears merged.
  A `--no-preflight` flag skips this for offline use.
- `heartbeat <item>` — update heartbeat_at.
- `release <item> [--status merged|abandoned]` — remove lease, append one line to
  `.agents/leases/HISTORY.log`.
- `census` — table of live vs stale leases; `--reap` deletes stale ones.
Timestamps: UTC ISO-8601.

## Acceptance criteria (measurable)
- pytest `tests/test_agent_claim.py`: claim/release round-trip; second claim on fresh
  lease fails; stale lease is claimable; census classifies fresh vs stale; the
  atomic-claim race — two claimants racing for one item (threads or sequential
  O_EXCL simulation) — exactly one wins. gh/git preflight mocked; no network in tests.
- `python3 -m py_compile scripts/agent_claim.py` passes on Python 3.9.
