# TRC-2026-02-16-004: Cosmos R2 Cookoff Refocus & Sprint Plan

| Field | Value |
|-------|-------|
| **ID** | TRC-2026-02-16-004 |
| **Date** | 2026-02-16 |
| **Author** | Claude (Travel Laptop) |
| **Duration** | 1h |
| **Type** | investigation |
| **Services** | matrix-api, cosmos-agent, cosmos-watcher, factoryio-bridge, fault-diagnosis |
| **Devices** | travel-laptop |
| **Trigger** | Cosmos Cookoff deadline 10 days out — need to refocus from Jarvis ops work |

---

## Context

Mike spent the weekend restoring Jarvis (OpenClaw) and building ops infrastructure (baselines, workflows, traces, registry). That work is now frozen at v0.9.0-jarvis-baseline. With 10 days until the NVIDIA Cosmos Cookoff deadline (Feb 26 @ 5:00 PM PT), it's time to shift all attention to the competition submission.

The Cosmos Cookoff pipeline code already exists:
- `cosmos/client.py` (491 lines) — API client with real + stub modes
- `cosmos/agent.py` (207 lines) — incident watcher + analyzer
- `cosmos/watcher.py` (118 lines) — Matrix API poller
- `services/matrix/app.py` (775 lines) — full REST API with SQLite backend + web HMI
- `sim/factoryio_bridge.py` (308 lines) — Modbus bridge with simulator fallback
- `diagnosis/conveyor_faults.py` — 11 rule-based fault codes

But the pipeline has never been run end-to-end, no API key is set, no demo video exists, and the README isn't judge-ready.

## What Happened

1. **Assessed current state** — Inventoried all competition code, identified what works (stub mode, individual components) vs what doesn't (no API key, no end-to-end test, no video, no judge-ready README)
2. **Performed gap analysis** — Mapped competition requirements against current capabilities. Critical gaps: API key, end-to-end validation, demo video, README, public repo
3. **Identified critical path** — Minimum viable demo: get API key → run stub demo → swap to real API → record video → write README → create public repo
4. **Created 10-day sprint plan** — Daily tasks from Feb 16 (pipeline validation) to Feb 25 (final check + submit)
5. **Evaluated Jarvis integration options** — Recommended wiring `diagnose` skill to Matrix API for "ask your factory" demo (highest impact, lowest effort)
6. **Created WF-008** — Demo prep workflow with daily checklist at `docs/ops/workflows/cosmos-r2-demo-prep.md`
7. **Began Day 1 pipeline validation** — Starting Docker, Matrix API, bridge, watcher, fault injection

## Changes Made

| File/Config | Before | After | Why |
|-------------|--------|-------|-----|
| `docs/ops/workflows/cosmos-r2-demo-prep.md` | Did not exist | WF-008: 10-day sprint workflow | Track daily progress toward submission |
| `docs/ops/traces/2026-02-16_cosmos-refocus.md` | Did not exist | This trace | Document the refocus decision and plan |

## Outcome

- Clear 10-day sprint plan created and documented
- WF-008 workflow tracks daily tasks from pipeline validation to submission
- Day 1 pipeline validation in progress
- All team devices can reference the workflow for their role

### Risk Register

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| API key not arriving | Medium | Llama 70B fallback already in `cosmos/client.py` |
| Real Cosmos responses differ from stubs | Medium | Test on Day 4, tune prompts Day 4-5 |
| Docker/Postgres issues on WSL | Low | SQLite is default backend, skip Postgres |
| Factory I/O licensing | Low | Built-in simulator works without it |

## Queryable Tags

- **competition**: cosmos-cookoff-r2
- **deadline**: 2026-02-26T17:00:00-08:00
- **services**: matrix-api, cosmos-agent, cosmos-watcher, factoryio-bridge
- **ports**: 8000, 502
- **models**: nvidia/cosmos-reason2-8b, meta/llama-3.1-70b-instruct
- **config-keys**: NVIDIA_COSMOS_API_KEY
- **fault-codes**: E001-T002 (11 rule-based codes), error_code 0-5 (PLC)

## Related

- **Workflows**: [WF-008](../workflows/cosmos-r2-demo-prep.md)
- **Config Snapshots**: [2026-02-16_cosmos-agent.yaml](../config-snapshots/2026-02-16_cosmos-agent.yaml)
- **Docs**: `docs/cosmos_cookoff_demo_runbook.md`, `docs/cosmos_cookoff_plan.md`, `docs/cosmos_architecture.md`
- **Prior Traces**: [TRC-2026-02-16-001](./2026-02-16_jarvis-soul-restore.md) (Jarvis restore — now frozen)
