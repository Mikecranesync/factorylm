---
name: ship
description: Merge-and-deploy run-book. Use when merging a PR and deploying to VPS. Encodes the full checklist: CI gate → merge → deploy → verify → Linear update. Trigger on "ship PR", "merge and deploy", "deploy this", "ship it".
---

# /ship — Merge & Deploy Run-book

## Step 1: CI Gate (SHA-pinned — a badge is not proof)

```bash
gh pr view <PR_NUMBER> --json headRefOid,mergeable,statusCheckRollup
```

- **Pin the SHA**: the green check runs must report against `headRefOid` (the PR's *current* head). A green run for a previous head is NOT green — push/wait and re-check.
- All required checks `success` — `skipped`/`neutral` on a required check counts as a failure; investigate why it skipped.
- **If this PR adds tests**: confirm they actually executed — grep the CI run log for the new test names (`gh run view <run-id> --log | grep <test_name>`). Also grep for `ModuleNotFoundError` and `command not found`; workflows have silently no-opped on missing deps.
- If checks are failing: compare against main head (`gh run list --branch main --limit 3`).
  - **Pre-existing on main** (unrelated to this PR) → confirm with user, then proceed.
  - **New failure** → STOP. Do not merge. Fix or escalate.

## Step 1.5: Hazard Ledger

Before merging, list every hazard/TODO/"probably fine" noticed during the work but not fixed. Each gets a disposition: `fixed | filed as issue #N | explicitly accepted because <reason>`. A non-empty list with no dispositions = do not merge; report it instead.

## Step 2: Dependency Order

Check if this PR depends on another unmerged PR (look at description, imports, migration files). Merge dependencies first.

## Step 3: Merge

```bash
gh pr merge <PR_NUMBER> --squash --auto
```

Or if auto-merge is blocked:
```bash
gh pr merge <PR_NUMBER> --squash
```

## Step 4: Deploy to VPS

```bash
doppler run --project factorylm --config prd -- docker compose pull <service>
doppler run --project factorylm --config prd -- docker compose up -d <service>
```

Or full stack:
```bash
doppler run --project factorylm --config prd -- docker compose up -d
```

## Step 5: Verify

Run smoke tests against affected routes:
```bash
bash install/smoke_test.sh
```

Or targeted Playwright:
```bash
npx playwright test --grep "<feature>"
```

Report: status codes, screenshots to `docs/promo-screenshots/` (both 1440x900 and 412x915), any errors in `docker compose logs -f <service> --tail=50`.

**Behavioral diff for feature PRs**: capture the observable output of the affected endpoint BEFORE deploying and AFTER. If they are identical, that is a FAILURE, not a pass — a feature once shipped into a dead staging layer and "worked" while changing nothing. Trace the request path until you find where it diverges from expectation.

**STOP if smoke fails** — rollback: `docker compose up -d --scale <service>=0` then re-deploy prior image.

## Step 6: Update Linear

Find the linked Linear ticket and move to **Done**:
- Add PR link as attachment
- Note deploy timestamp and verification result

## Checkpoints (STOP and ask if)

- New red CI check (not pre-existing)
- Smoke test failure post-deploy
- Migration detected but not verified applied
- PR touches `SAFETY`, `PLC`, or `CRITICAL` tagged code
