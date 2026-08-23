# Claude Global Rules (insights-derived, cluster-wide)

Canonical copy — installed into each node's `~/.claude/CLAUDE.md` via an
`@import` line by `infra/claude/install.sh`. Provenance and tracking:
`docs/insights/README.md`.

## Verification Discipline — "green" and "done" are machine-checked claims

- Never report a PR or CI run as green without confirming the check-run SHA
  equals the PR's **current** head: `gh pr view <n> --json headRefOid` must match
  the SHA on the green run. A badge from the previous head is not green.
- A green run is not proof new tests executed. Grep the CI log for the new test
  names (or diff junit test counts vs base) before declaring done. Also grep run
  logs for `ModuleNotFoundError` / `command not found` / suspiciously-fast suite
  steps — workflows have silently no-opped for weeks.
- Prefer `scripts/verify_green.py <pr>` (this repo) — it checks all of the above
  mechanically and emits a JSON verdict.
- For any user-facing feature: hit the real staging endpoint end-to-end and
  capture observable output BEFORE and AFTER. Identical output = failure to
  prove, not success — trace the request path until you find where it diverges.
- Before saying "done", emit a **hazard ledger**: every hazard/TODO/"probably
  fine" noticed but not fixed, each dispositioned as `fixed | filed as issue #N |
  explicitly accepted because <reason>`. Silent omission is an overclaim.

## Resume-from-Handoff Reconciliation

Handoff docs go stale and parallel sessions land work (a session once rebuilt
two already-merged PRs). Before acting on ANY handoff or resuming any
workstream: `git fetch --all`, `git log --oneline origin/main -30`, and
`gh pr list --state all --limit 30 --json number,title,state,mergedAt`. Diff the
handoff's claims against reality, report what's already merged/closed, and only
then propose the remaining work list. The `/resume` skill encodes this — use it.
For parallel sessions, claim work items first: `scripts/agent_claim.py claim <item>`.

## Diagnose Once, Then Act

Timebox diagnosis: at most ~15 tool calls to a written one-paragraph root-cause
statement citing the specific evidence lines, then implement the fix. Reopen the
diagnosis only if the fix fails, and say explicitly what new evidence changed
your mind. One decisive fix beats repeated analysis passes.

## Local Gates Before Push

Before any `git push` in a Python repo: `ruff format --check . && ruff check . &&
pytest -q` — the FULL suite, not just the new test file (new tests have passed in
isolation and failed under full-suite module pollution). A PostToolUse hook
auto-formats each edited .py and reports unfixable lint errors — but it can't run
the test suite; that's on you.

## Shared-File Conflict Policy

Never edit `VERSION`, `CHANGELOG.md`, or `wiki/hot.md` directly in a feature
branch. Use per-run dated fragment files (`changelog.d/<date>-<slug>.md`); a
release job assembles them. A PreToolUse hook (`shared-file-guard.sh`) turns
direct edits at a repo root into an explicit permission prompt; set
`CLAUDE_ALLOW_SHARED_FILE_EDITS=1` where direct edits are legitimately fine.
A rebase conflict on one of these files means the policy was violated — fix the
source, don't hand-resolve.

## Output Length & Long Autonomous Runs

Long artifacts (reports, plans, audit writeups) go to a file via Write/Edit with
a short pointer + 2-3 line summary in chat — never one giant chat response
(~12 sessions died mid-response on the output-token ceiling). Long autonomous
runs checkpoint progress to `.planning/STATE.md` (or equivalent) every phase.

## Subagent Worktree Isolation

Before dispatching any subagent that will Edit/Write files — especially several
in parallel — give it its own git worktree (Agent tool `isolation: "worktree"`
or `git worktree add`) or explicitly confirm the shared checkout has no
uncommitted work it could clobber. Never assume isolation — verify it.

## Verify Subagent Output

Subagents fabricate symbols. After ANY agent returns code, before committing:
confirm every referenced symbol, import, signature, DB column, and state value
exists (codegraph or grep). Reject and regenerate code referencing symbols you
cannot ground.

## Permission Gates

Don't silently loop, retry, or route around a permission/classifier block. If
the action is within a standing authorization, do it. If the gate is right to
flag it, ask the user once — exactly what's blocked and why — and act on the
answer. Fix the looping, keep the guardrail.
