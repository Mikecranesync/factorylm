# Insights 2026-07-06 — Output Limits, Worktree Isolation, Permission Gates

Report file no longer on disk; findings reconstructed from the rules it produced
(dated 2026-07-06 in CHARLIE's `~/.claude/CLAUDE.md`).

## Findings

1. **~12 sessions over 28 days died as unrecoverable API errors** from exceeding
   the output-token ceiling mid-response — the single biggest source of lost work.
2. **Two incidents of a dispatched subagent mutating the shared checkout** instead
   of an isolated one, nearly destroying uncommitted work.
3. **Permission-gate looping**: a session repeatedly deferred an already-authorized
   prod action until the user had to demand it; another silently routed around a
   blocked tool instead of surfacing the block.

## Implementations

| Fix | Artifact | Status |
|---|---|---|
| Long artifacts → Write to file + short pointer reply; checkpoint long runs to `.planning/STATE.md` | `infra/claude/CLAUDE-GLOBAL-RULES.md` § Output Length | ✅ |
| Subagents that Edit/Write get a worktree, or the shared checkout is verified clean first | § Subagent Worktree Isolation | ✅ |
| Blocked action → act if within standing authorization, else ask once and act on the answer; never loop or evade | § Permission Gates | ✅ |
