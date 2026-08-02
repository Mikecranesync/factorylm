# `factorylm.machine-snapshot.v1` — shared contract fixture

The compatibility boundary between **FactoryLM** (producer) and **MIRA** (consumer)
for read-only PLC machine snapshots. PRD: `docs/prd/2026-08-01-mira-factorylm-machine-evidence-handoff.md`.

Both repositories test against the **exact same** payload in this directory. Neither side
may change a fixture without the other's tests being re-run against it — that is what keeps
the two projects wire-compatible.

## Files

- `snapshot_v1_valid.json` — a well-formed running-machine snapshot (the golden payload).
- `snapshot_v1_invalid_missing_tenant.json`
- `snapshot_v1_invalid_missing_timestamp.json`
- `snapshot_v1_invalid_schema_version.json`
- `snapshot_v1_invalid_malformed_tags.json`

## Rules (see PRD § "Contract rules")

- Required: `schema_version`, `snapshot_id`, `captured_at`, `tenant_id`, `tags`.
- `schema_version` MUST be `factorylm.machine-snapshot.v1`.
- `tag_path` MUST be a canonical FactoryLM tag name (e.g. `conv_simple.vfd_speed_hz`).
- `quality ∈ {good, bad, stale, uncertain}`; an unknown value downgrades toward *less*
  confidence, never `good`.
- `proposed_uns_path` is **provenance only** — it never creates or mutates a KG/UNS record.
- **Observation only.** No command / write / actuator / control field is permitted.

## Consumer (MIRA)

`materialized_evidence.context_contract.overlay_from_factorylm_snapshot(snapshot)` →
`(LiveStateOverlay | None, violations)`. It reuses `live_overlay_from_machine_packet` — it does
**not** re-implement `LiveTag`, freshness mapping, or rendering. `augment_with_live(ctx, snapshot)`
in `mira-bots/shared/technician_context.py` folds the overlay into `TechnicianContext.live`
(one context, one manifest — the `augment_with_*` shape from #3041).
