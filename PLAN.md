# PLAN: MES Core — Week 3 (OEE Calculator Service)

**Branch:** `feat/mes-week3-oee-calculator`
**Issue:** Mikecranesync/MIRA#321
**PRD:** `docs/PRD-MES-CORE.md`
**Date:** 2026-04-16
**Depends on:** Weeks 1+2 merged to main ✓

---

## Objective

60-second tick OEE calculator. Reads ItemCount delta from plc-modbus,
computes Availability/Performance/Quality/OEE/TEEP from machine_states,
writes to oee_snapshots, exposes REST endpoints, and alerts when OEE < 60%.

## OEE Formula

  Availability = run_time_sec / planned_time_sec
  Performance  = (ideal_cycle_sec x total_count) / max(run_time_sec, 1)
  Quality      = good_count / max(total_count, 1)
  OEE          = Availability x Performance x Quality
  TEEP         = OEE  (no schedule yet; Week 4 wires utilization)

Clamp all values to [0.0, 1.0].

## New Endpoints

  GET /api/mes/lines/{id}/oee
  GET /api/mes/lines/{id}/oee/history?hours=8
  GET /api/mes/oee/summary
  GET /api/mes/kpis

## Rollback

  git checkout main
