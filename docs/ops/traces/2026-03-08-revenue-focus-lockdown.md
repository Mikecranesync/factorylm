# Ops Trace: Revenue Focus Lockdown

**Date:** 2026-03-08
**Author:** Claude (CTO agent)
**Type:** governance

## What Changed

1. **CLAUDE.md** — Added "Active Focus Window (Revenue Priority)" section
   - Defines IN SCOPE paths (14 directories) for V1 bot work
   - Defines OUT OF SCOPE paths (12+ directories) that require human approval
   - Hard stop rule: if outside scope, ask Mike

2. **7 GitHub PRs tagged as post-V1**
   - #132 (KB auto-ingest) — post-V1
   - #131 (workflow graph) — post-V1
   - #127 (MCP factory tools) — post-V1
   - #125 (README video) — post-V1
   - #124 (crash-safe recording) — post-V1
   - #122 (Open Brain fallback) — post-V1.1
   - #106 (Discord health check) — post-V1

3. **GitHub labels created**
   - `revenue-v1` (green) — In the V1 money path
   - `post-v1` (red) — Deferred until after revenue bot ships

4. **PR #135 merged** (by Mike) — Mission Control Phase 2-3 + Telegram bot on CHARLIE

## Why

The repo had 8 open PRs spanning every corner of a 43-directory monorepo. Every Claude session was touching everything. Only one PR (#135) was in the path to "Telegram bot that answers from KB with citations." This lockdown draws a hard boundary so every session and PR is either shipping the bot or explicitly deferred.

## Architecture Decision

**Focus rule:** Until the Telegram bot can (1) answer from KB with citations and (2) be paid for by a stranger — nothing outside the money path gets touched.

## Risks

- Low: Deferred PRs may drift further from main over time
- Mitigation: PRs stay open, not closed. Can be rebased when V1 ships.

## Rollback

- `git revert` the CLAUDE.md commit
- `gh label delete post-v1 && gh label delete revenue-v1`
- Remove this trace
