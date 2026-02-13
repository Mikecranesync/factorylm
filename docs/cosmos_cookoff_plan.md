# Cosmos Cookoff Plan — FactoryLM × NVIDIA Cosmos Reason 2

**Version:** 0.1 (Draft)  
**Author:** Mike Harper  
**Date:** 2026-02-13  
**Status:** PLANNING — Active competition entry

---

## Elevator Pitch

FactoryLM already connects to PLCs and streams real-time tag data through Voltron into a central Matrix — but when something goes wrong on the factory floor, operators still have to piece together what happened from raw alarms and spreadsheets. By plugging NVIDIA Cosmos Reason 2 into our existing pipeline, we give every incident a physical reasoning engine: Cosmos watches the short video clip around the fault, correlates it with the PLC tag history, and returns a structured root-cause hypothesis with suggested checks — all in seconds, all read-only, delivered straight to the operator's HMI or chat interface. This turns FactoryLM from a diagnostic data platform into a maintenance co-pilot that *understands* the physical world.

---

## Problem Statement

Unplanned downtime costs manufacturers an estimated $50B/year. When a PLC faults, operators see a cryptic alarm code and a wall of tag values. Diagnosing the root cause requires experience, context, and often a physical walkdown — all of which take time. Video cameras may exist on the floor, but nobody correlates footage with tag data in real time. The result: slow diagnosis, repeated failures, and tribal knowledge locked in the heads of senior techs.

---

## Solution

1. **Voltron / Matrix pipeline** — streams PLC tags, events, and timestamps into a central Postgres store with full history.
2. **NVIDIA Cosmos Reason 2** — receives an incident bundle (tag snapshot + short video clip around the fault) and applies physical-world reasoning to produce a structured `CosmosInsight`: summary, root-cause hypothesis, confidence score, and suggested operator checks.
3. **HMI + Chat integration** — the insight surfaces in a web dashboard incident view and via the Telegram/chat interface, so operators get answers where they already work.

---

## Key Milestones

| Date | Milestone | Notes |
|------|-----------|-------|
| **Feb 16** | End-to-end sim + HMIs working (no Cosmos) | Voltron pipeline, simulated PLC cell, basic web HMI |
| **Feb 19** | Register for Cosmos Cookoff | Official entry submitted |
| **Feb 20** | Cosmos connector prototype working | `cosmos/agent.py` calls Cosmos Reason 2 with simulated incident bundles |
| **Feb 22** | Real Micro820 / garage conveyor integrated | Or fully documented sim fallback if hardware unavailable |
| **Feb 24** | Demo video recorded, README for judges finalized | Polished walkthrough showing fault → insight flow |
| **Feb 26** | Submission sent | Final package delivered |

---

## Feature Checklist

### Must-Have

- [ ] Voltron pipeline streaming tags from PLC (or sim) → Matrix → Postgres
- [ ] `cosmos/agent.py` — subscribes to incidents, bundles tags + video pointer, calls Cosmos Reason 2
- [ ] Structured `CosmosInsight` stored in Postgres and returned to Matrix
- [ ] Web HMI incident detail view showing tags, video thumbnail, and CosmosInsight
- [ ] Chat endpoint answering "What went wrong?" using CosmosInsight
- [ ] Demo video (2–4 min) showing end-to-end flow
- [ ] Judge-ready README with setup instructions and architecture diagram
- [ ] Read-only safety constraint enforced throughout

### Nice-to-Have

- [ ] Live Micro820 hardware instead of simulator
- [ ] Multiple fault scenarios (jam, overtemp, sensor drift)
- [ ] Confidence-based LLM tier escalation (low Cosmos confidence → Claude)
- [ ] Historical incident comparison ("this looks like the jam on Jan 15")
- [ ] Telegram bot integration for mobile operators
- [ ] Cost tracking dashboard for Cosmos API calls

---

## TODO Stubs

- [ ] Implement `cosmos/agent.py`
- [ ] Extend Matrix API to retrieve incident bundles (tags + video pointers)
- [ ] HMI: incident detail view with CosmosInsight panel
- [ ] Demo script and video outline

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2026-02-13 | Initial plan |
