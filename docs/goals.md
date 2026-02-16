# Goals — FactoryLM

**Version:** 0.1  
**Author:** Mike Harper  
**Date:** 2026-02-13  
**Status:** ACTIVE

---

## Top-Level Goal

**Win or place in the NVIDIA Cosmos Cookoff 2026 with FactoryLM Voltron + Cosmos Reason 2.**

Demonstrate that a read-only industrial AI platform — already capable of streaming PLC data through a distributed node architecture — becomes dramatically more useful when paired with NVIDIA's physical-world reasoning model.

---

## Cookoff Sub-Goals

### 1. Robust Voltron / Matrix Pipeline

*Status: In progress*

- Voltron nodes reliably stream PLC tags into Matrix via forwarder
- Postgres stores tag history with timestamps for any lookback window
- Events (faults, anomalies) are detected and recorded with context
- Pipeline runs repeatably in both simulated and live-hardware configurations

### 2. Simulated PLC Cell + HMIs for Repeatable Demos

- Deterministic PLC simulator produces realistic fault scenarios (jam, overtemp, drift)
- Web HMI shows live tag dashboard, event log, and incident detail view
- Demo can run on any machine without physical hardware dependencies
- Scenario playback: trigger faults on demand for demo recordings

### 3. Cosmos Reason 2 Integration

- `cosmos/agent.py` subscribes to incident events and bundles tag + video context
- Calls Cosmos Reason 2 API and stores structured `CosmosInsight` in Postgres
- Web HMI incident view displays CosmosInsight panel (summary, root cause, checks)
- Chat endpoint answers "What went wrong?" using CosmosInsight as primary source
- Graceful fallback when Cosmos is unavailable (degrade to standard intelligence stack)

### 4. Judge-Ready Documentation + Demo Video

- Architecture diagram and data flow clearly documented
- README for judges: setup instructions, what to look for, how to run it
- Demo video (2–4 min): show fault → Cosmos insight → operator action loop
- Code is clean, commented where non-obvious, and runnable from the repo

---

## Production Goals

Beyond the Cookoff, FactoryLM targets these longer-term outcomes:

- **Reduce unplanned downtime** by giving operators instant root-cause hypotheses backed by physical reasoning, not just alarm codes.
- **Push intelligence downward** — successful Cosmos insights become knowledge base entries (Layer 0), reducing future API calls.
- **Multi-protocol, multi-vendor** — support Modbus, EtherNet/IP, S7, OPC UA across Allen-Bradley, Siemens, and generic PLCs.
- **Tiered cost model** — use the cheapest intelligence tier that can answer the question (Layer 0 code → Layer 1 edge → Layer 2 local GPU → Layer 3 cloud AI / Cosmos).
- **Deployment flexibility** — run air-gapped (no cloud), hybrid, or full-stack depending on the customer's security requirements.
- **Revenue generation** — ship FactoryLM Edge as a hardware + subscription product for small-to-mid manufacturers.

---

## Open Source Goals

- **Open the core pipeline** — Voltron node framework, Matrix dispatcher, and Cosmos connector released under a permissive license so the community can build adapters for new PLC protocols and LLM providers.
- **Cookbook contributions** — publish working examples of Cosmos Reason 2 applied to industrial scenarios back to the NVIDIA Cosmos Cookbook.
- **Community adapters** — encourage third-party integrations (Slack, Discord, WhatsApp, SCADA systems) by keeping the adapter interface simple and documented.
- **Transparency** — share real performance data (latency, accuracy, cost-per-insight) so others can evaluate the approach honestly.
- **Avoid vendor lock-in** — the architecture works with any LLM provider; Cosmos is a powerful option, not a hard dependency.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2026-02-13 | Initial goals document |
