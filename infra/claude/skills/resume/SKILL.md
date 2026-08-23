---
name: resume
description: Safely resume from a handoff doc or continue a workstream without duplicating work a parallel session already landed. Use when a session starts from a handoff pointer, "continue where we left off", or resuming any multi-session program. Reconciles handoff claims against actual repo state BEFORE any work starts.
---

# /resume — Reconcile Before You Work

Handoffs go stale and parallel sessions land work. A session once rebuilt two already-merged PRs and burned most of its budget before the user interrupted. Never start from the handoff's word — start from the repo's.

## Step 1: Read the handoff

Read the handoff doc (argument, or most recent in the usual handoff location). Extract every claim into a checklist: PR numbers, branches, SHAs, "open"/"merged"/"blocked" states, next actions.

## Step 2: Fetch reality

```bash
git fetch --all --prune
git log --oneline origin/main -30
gh pr list --state all --limit 30 --json number,title,state,mergedAt,headRefName
gh pr list --state all --search "updated:>=$(date -v-2d +%Y-%m-%d)" --json number,title,state
```

Also check for other live sessions/worktrees that might be mid-flight:

```bash
git worktree list
```

## Step 3: Diff claims vs reality

For each handoff claim, mark: **confirmed** / **already done elsewhere** / **stale** / **contradicted**. Anything already merged or closed comes OFF the work list. Anything contradicted gets re-verified from the artifact (PR body, CI run, diff), not from the handoff prose.

## Step 4: Preflight the environment

Long runs die on avoidable stalls. Check before starting, not mid-flight:

```bash
gh auth status
docker info >/dev/null 2>&1 || echo "Colima/Docker down"
```

Plus any services the work needs (Qdrant :8000, PLC API :8001, etc. — see project CLAUDE.md).

## Step 5: Report, then work

Output a short table — item, source claim, verified state, action — then execute ONLY the surviving items. Do not Edit/Write anything before Step 5.
