# FactoryLM V0 Resurrection Status Report

**Scope.** This report maps the current FactoryLM codebase against the governance baseline (system spec + CLAUDE.md) and the V0 milestone definition: "GitHub codebase audited, mapped, reconnected per spec." It is a read-only survey of what exists, what is broken, what is missing versus the spec, and what is undocumented.

---

## 1. WHAT EXISTS

Roughly **70% of the end-state vision has some functional implementation** in this repository, spanning production-ready services, working but rough components, prototypes, and stubs. The table below summarizes the tiers.

| Tier          | Count | Examples                                                                 |
|---------------|-------|--------------------------------------------------------------------------|
| Production    | 5     | Core LLM service, PLC Modbus stack, My-Ralph, Telegram bot, Celery jobs |
| Working       | 40+   | Diagnosis service, LLM router, OpenClaw KB, Celery workers, recovery    |
| Prototype     | 5     | CMMS fork, Matrix dashboard, Portal, PLC reader, Mission Control        |
| Stub/Planned  | 10+   | Cosmos API scaffold, API gateway, KB indexing, Antfarm                  |
| Vision Only   | 5     | Edge LLM on Pi, GPU server, Plane/Wiseflow, WhatsApp, AR HMI            |

### 1.1 Core "brain" and LLM infrastructure

- The `brain/` and `core/` directories define the central LLM orchestration, routing, and prompt logic used across services.
  - There is a working multi-provider router (8+ providers) and configuration in `config/` and `services/` that supports different backends behind a unified API.
  - Automated tests exist for the core logic under `tests/`, giving partial coverage of key flows.

### 1.2 PLC / factory integration

- PLC and Modbus connectivity is implemented across `collectors/`, `gateway/`, `integrations/`, and `sim/` / `simulation/`, supporting Micro820 and Factory I/O scenarios.
  - The `apps/` and `services/` trees include a PLC reader app and diagnosis flows that bridge PLC tags into the LLM-facing layer.

### 1.3 Diagnosis and maintenance workflows

- The `diagnosis/` folder contains the conveyor / Factory I/O diagnosis logic, including chain-of-thought style prompts and video + tag fusion for Cosmos Reason2.
  - Recovery, troubleshooting, and CMMS-adjacent behaviors are spread across `recovery/`, `cmms/`, `runbooks/`, and `analytics/`.

### 1.4 Interfaces and integrations

- Chat and notification interfaces exist via Telegram (`services/` and/or `tools/`), plus HMI-oriented assets such as `hmi-screenshot.png` and dashboard/portal prototypes in `apps/`.
  - Knowledge-base oriented structures live in `kb/` and `openclaw/`, with code that indexes or queries documents in support of maintenance workflows.

### 1.5 Governance / product definition

- The repository includes system-level specs and product requirement documents: `PRD-001_Core_Infrastructure.md` through `PRD-006_Pi_Factory.md`, plus governance files like `CLAUDE.md`, `AGENTS.md`, `SOUL.md`, and `IDENTITY.md`.
  - The cookoff-specific design is captured in `COOKOFF_README.md`, `COOKOFF_PLAN.md`, `COOKOFF_HUMAN_ACTIONS.md`, and `COSMOS_FACTORY.md`.

---

## 2. WHAT'S BROKEN

This section lists issues that appear structurally broken based on the repo layout (imports that cannot resolve, missing dependencies, or dead paths). All items should be validated with a fresh install and test run.

1. **`apps/plc-reader/app.py` -- import paths reference non-existent package layout**
   - The plan assumes imports from `packages/factorylm-cli/src` or similar; the current repo contains `packages/` but not the exact CLI path described.
   - This implies that out-of-the-box, `plc-reader` cannot run without adjusting PYTHONPATH or restructuring packages.

2. **CMMS tests reference incomplete modules**
   - Test files (e.g. `tests/test_gist_work_order*.py`) expect functionality in `cmms/` that is only partially implemented or absent.
   - As a result, the CMMS integration is not currently test-green and behaves as a prototype rather than production.

3. **Vector DB (ChromaDB) not wired in requirements**
   - KB/RAG components in `kb/`, `openclaw/`, or `analytics/` are structured as if a vector DB is present, but no ChromaDB dependency appears in top-level `requirements` or `pyproject` files.
   - Practically, this means RAG-style memory is disabled or only partially wired unless the user manually installs extra libraries.

4. **Hardcoded absolute paths in analytics utilities**
   - Files such as `analytics/pattern_embedder.py` reference hardcoded paths (e.g. `/opt/master_of_puppets` in the original audit) that do not exist in this repo's standard layout.
   - These utilities are therefore effectively dead code in a clean deployment.

5. **Hardcoded IP addressing in PLC reader code**
   - `apps/plc-reader/app.py` and related PLC clients embed fixed IPs (for example, 100.x lab networks) rather than configuration-driven endpoints.
   - This limits portability and requires editing source just to connect to a different PLC or simulator.

6. **OPC UA is declared as a direction but not implemented**
   - The spec and some configuration mention OPC UA as a target protocol, but there is no concrete OPC UA client implementation in the code folders.
   - The system is effectively Modbus-only today.

7. **Core LLM tests drift from exported interface names**
   - Some tests under `tests/` expect class names and function signatures that have evolved in the `core/` or `brain/` modules.
   - This indicates a gap between intended public API and the current implementation, and leads to failing or skipped tests.

8. **Deprecated pymodbus usage in comments and examples**
   - Legacy references to old `pymodbus` APIs remain in tests or comments, which can mislead contributors setting up new PLC integrations.
   - While mostly cosmetic, they increase the risk of copy-pasted incorrect code for new collectors.

---

## 3. WHAT'S MISSING (VS. SYSTEM SPEC)

The governance and PRD documents outline capabilities that are not yet present or are only partially realized in code.

1. **Visual workflow graphs (n8n/LangFlow)**
   - Workflows are currently captured as YAML, Python orchestration, and textual runbooks; there is no maintained n8n/LangFlow or equivalent visual flow in the repo.

2. **Intent router / classifier**
   - Routing across tools, agents, and providers appears to be done via manual keyword or endpoint selection rather than a trained intent classifier.

3. **Source citation enforcement**
   - Response templates and agent outputs do not consistently enforce source citations, despite the spec calling for traceable, grounded explanations.

4. **Benchmark question suite for validation**
   - There is no centralized Q/A benchmark harness in `tests/` or `analytics/` that runs standardized questions through the system and checks expected answers.

5. **End-to-end KB ingestion pipeline**
   - While `kb/` and `openclaw/` exist, there is no single, documented pipeline that handles document discovery, chunking, embedding, metadata, and storage.

6. **Retrieval-before-generation enforcement**
   - Many LLM calls are direct prompt -> completion without mandatory KB retrieval, which diverges from a strict "RAG-first" design in the spec.

7. **Intelligent LLM routing based on cost/latency/capability**
   - The router supports multiple providers but does not appear to implement policy-based selection driven by cost, latency, or model capability metrics.

8. **OPC UA protocol support**
   - As noted, OPC UA connectivity is unimplemented even though it is mentioned as a requirement in integration-focused PRDs.

9. **Real-time machine state in LLM context**
   - Live PLC tag streams are not yet consistently surfaced inside high-level conversational agents (e.g., "what's wrong with Line 1?") as structured context.

10. **Human approval / audit gate for PLC changes**
    - There is no robust, logged approval workflow (with rollback) in front of any PLC-writing operation, which the system spec frames as mandatory for safety.

---

## 4. WHAT'S UNDOCUMENTED

Several critical behaviors are implemented in code but lack any combination of: design docs, visual workflows, or test coverage.

1. **Telegram message routing**
   - Telegram bot handlers in the services/tools layer perform async routing and fan-out to various agents, but there is no consolidated architecture doc or state diagram.

2. **LLM provider selection logic**
   - The router that chooses between ~8 providers uses configuration flags, circuit-breaker behavior, and budget tracking across a daily window, but these rules are not written up in `docs/` or `runbooks/`.

3. **PLC -> Diagnosis -> LLM flow**
   - The end-to-end data path from PLC registers through diagnosis code into LLM outputs (including scaling factors, error-code mappings, and fallbacks) is only discoverable by reading code and tests.

4. **Photo analysis / wiring reconstruction**
   - The image analysis path (e.g., factory photos -> KB enrichment -> suggested wiring or component mapping) exists in worker modules under `workers/` or `analytics/`, but lacks a narrative explanation or sequence diagram.

5. **Celery beats and daemon jobs**
   - There are numerous Celery tasks and beat schedules defined across the repo, but no single runbook enumerates them, their cadences, or their operational impact.

6. **Gist-based work order poller**
   - Logic that watches GitHub gists or similar artifacts for work orders and commands exists in `analytics/` or `tools/`, yet is not described in the public docs.

7. **Troubleshooting session engine**
   - The in-memory troubleshooting session / state machine (TTL, crash behavior, handoff rules) is nowhere documented outside of the implementation.

8. **Hardcoded paths and env assumptions**
   - Several modules reference absolute paths under `/tmp/`, `/opt/openclaw/`, `/opt/factorylm-sync/`, etc., without documentation of expected directory layout on target systems.

---

## Executive Summary & V1 Blockers

V0 successfully establishes a rich, multi-service codebase that covers most of the envisioned capabilities at least once, but with fragmentation and gaps between the governance spec and the running system. The primary blockers for starting a clean V1 implementation phase are:

1. Fix broken import paths in `apps/plc-reader/app.py` so the PLC reader can run with the current `packages/` layout.
2. Add and wire a vector database dependency (e.g., ChromaDB or equivalent) and expose a minimal KB ingestion path.
3. Implement a basic KB ingestion pipeline (chunking + embedding + storage) that `kb/` and `openclaw/` can share.
4. Introduce a first-pass intent router for top-level user queries, even if model-simple, to replace pure keyword routing.
5. Enforce source citation in response templates for any answer that uses KB or telemetry.
6. Define 5-10 benchmark questions and expected answers that can be run as an automated test suite.

Once these are addressed, the system will be ready for a V1 phase focused on robustness, safety (human approval gates, OPC UA, PLC write controls), and full alignment with the governance spec.
