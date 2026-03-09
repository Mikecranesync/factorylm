# TRC-2026-03-09: CI Watchdog Deploy

| Field | Value |
|-------|-------|
| **Date** | 2026-03-09 |
| **Node** | CHARLIE |
| **Scope** | CI/CD pipeline hardening |
| **Incident** | INC-2026-03-09-001 |

## Context

14 consecutive brain-feed workflow failures on FactoryLM_OS due to
brain-ingest endpoint timeout. No monitoring or alerting existed.

## Changes Made

| File | Action |
|------|--------|
| `.github/workflows/brain-feed.yml` | Rewrite — circuit breaker + DLQ |
| `.github/workflows/ci-watchdog.yml` | Create — 30-min health monitor |
| `.github/scripts/replay-brain-dlq.sh` | Create — DLQ replay utility |
| `docs/ops/incidents/INC-2026-03-09-001.md` | Create — incident report |

## Outcome

- Brain-feed failures no longer block pushes (green checks even when endpoint is down)
- Failed payloads stored as artifacts for 7-day replay window
- Watchdog auto-creates GitHub issues with VPS playbook on failure
- Watchdog auto-closes issues when endpoint recovers

## Tags

`ci-cd` `brain-feed` `watchdog` `circuit-breaker` `dead-letter-queue`
