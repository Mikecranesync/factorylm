# ARRESTED DEVELOPMENT

## FactoryLM Strategic Pause — March 2026

> "Pause development. Get core basic things in place. Come back stronger."
> — Mike, March 6, 2026

This is not a setback. This is a controlled stabilization before the next build
cycle. Every system that ships fast without a foundation eventually collapses.
This phase installs the foundation.

---

## WHY THIS PHASE EXISTS

FactoryLM has working Factory IO integration, a fault injector with 7 scenarios,
Cosmos AI stubs, a Matrix API incident hub, 42 Celery workers, an LLM router,
and an MCP brain server. It also has 86 repos mapped, 5 files to merge, and a
complete consolidation plan committed to PR #126.

What it does NOT have:
- A knowledge base Claude can query with confidence
- A Digital Twin Universe (Factory IO as automated test harness)
- RAG output from the Neon DB (massive data, no retrieval)
- A working ingest pipeline for maintenance manuals
- MCP tools so Claude can read/write PLC state directly
- A verified end-to-end loop: inject → diagnose → log → learn

Arrested Development fixes all of that before any new features are built.

---

## THE ONE RULE DURING THIS PHASE

**No new features. No new repos. No new product ideas.**

Every session starts with: "Does this build the foundation or add to it?"

If it adds to it → park it in BACKLOG.md and continue.
If it builds the foundation → proceed.

---

## WHAT "COME BACK STRONGER" LOOKS LIKE

When Arrested Development is complete, Claude can:

1. Read live PLC state from Factory IO via MCP tool call
2. Inject any of 14 fault scenarios and receive a verified diagnosis
3. Query maintenance manuals, fault history, and tag data via RAG
4. Run 50+ fault scenarios overnight unattended and post results to Discord
5. Export any Factory IO run as training data (Parquet + SFT JSONL)
6. Answer "what does fault V003 mean on this VFD?" from real OEM manuals

That is Level 4 on the Dark Factory spectrum.
Full Level 5 (no human reads or writes code) comes after.

---

## THE FIVE PILLARS

### Pillar 1 — Repo Foundation (DONE)

Status: Complete as of March 6, 2026 (PR #126, 8 commits)

Deliverables committed:
- INDEX.yaml — all 86 repos indexed
- OUTCOMES.md — 15 outcome groups
- CONSOLIDATION_PLAN.md — 86 repos assigned final status
- 4 tier-1 deep maps, 44 tier-2 surface maps, 38 tier-3 stubs
- 31 repos annotated with overlap relationships

Next action (one-time, this session):
- Merge PR #126
- Execute 5 partial merges into factorylm monolith:
  1. pi-factory-cosmos/fault_classifier.py → diagnosis/
  2. pi-factory-cosmos/vfd_reader.py → services/plc-modbus/
  3. cookoff/modbus_tag_source.py → services/plc-modbus/
  4. pi-factory-cosmos/belt_tachometer.py → cosmos/
  5. cookoff/net/diagnosis/vfd_conflicts.py → diagnosis/

---

### Pillar 2 — MCP Tools for Factory IO (NEXT: this weekend)

Status: Planned, not started

The single highest-leverage unblocking move. Once Claude can call
factory_read_state() and factory_inject_fault(), everything else
(RAG, training loops, dark factory) has a data source.

Files to create:
- services/mcp/factory_server.py (~250 lines, FastMCP)
  Tools: factory_read_state, factory_inject_fault, factory_list_scenarios,
         factory_clear_faults, factory_write_coil, factory_write_register,
         factory_watch_tags
- .mcp.json update — add factory_server entry
- CLAUDE.md update — append Modbus address map + safety rules

Verify gate: Claude Code calls factory_read_state() and returns live tag data.

---

### Pillar 3 — Knowledge Base (RAG) Pipeline (Week 1-2)

Status: Planned, not started

Two parallel tracks — both required, different jobs:

TRACK A: Neon DB + pgrag (operational/relational data)
  What it holds: PLC tag history, fault events, incident records,
                 Matrix API data, work orders
  How it works: pgrag extension embeds rows in-place inside PostgreSQL
  Why Neon: data is already there — no migration, no extra infra

  Files:
  - factorylm/kb/neon_rag.py
    → enable pgrag on Neon
    → embed top 3 tables from Matrix API schema (lines 32-102)
    → expose query(question, table) function

  First step: Search archived repos for lost n8n workflows
    gh repo list Mikecranesync --archived --json name,url \
      | jq -r '.[].name' \
      | while read repo; do
          gh api repos/Mikecranesync/$repo/git/trees/HEAD \
            --jq '.tree[].path' 2>/dev/null | grep -i "n8n\|workflow"
        done

TRACK B: LlamaCloud + n8n (unstructured documents)
  What it holds: OEM manuals, wiring diagrams, maintenance PDFs,
                 fault bulletins, parts catalogs
  How it works: LlamaParse → clean markdown chunks → LlamaCloud Index
  Why LlamaCloud: handles 247-page PDFs with tables and diagrams
                  pgrag would mangle these
  Integration: official n8n-llamacloud node package
    npm install @llamaindex/n8n-llamacloud

  Files:
  - factorylm/kb/llamacloud_ingest.py
    → ingest all PDFs from factorylm/docs/
    → output index_id to .env.llamacloud
  - .planning/n8n/hybrid_rag_query.json
    → n8n workflow: Neon pgrag + LlamaCloud merge → Claude answer

COMBINED n8n query flow:
  User query
    → Neon pgrag (relational + time-series matches)
    → LlamaCloud Index (document matches)
    → Merge node (10 total chunks)
    → Claude node (answer with full context)

Qdrant collections (for Factory IO run logs — local, no cloud):
  fault_history       — all Factory IO scenario run results
  factory_run_logs    — raw sensor time series
  plc_tag_map         — all Micro 820 + VFD tags with descriptions
  (embed via Ollama nomic-embed-text, zero API cost)

---

### Pillar 4 — Factory IO as Digital Twin Universe (Week 2-3)

Status: Planned, depends on Pillar 2

This converts Factory IO from "simulator you watch" to
"automated test harness that runs while you sleep."

Files:
- factorylm/tests/scenario_runner.py (~200 lines)
  → connects to Factory IO via Modbus TCP localhost:502
  → loads scenarios from tests/scenarios/*.yaml
  → for each: inject → poll → classify → log PASS/FAIL
  → produces results/run_{timestamp}.json

- factorylm/tests/scenarios/holdout/ (SACRED — Claude never reads this)
  → behavioral test cases Claude cannot see when writing classifier code
  → StrongDM pattern: agents cannot cheat by writing assert true

- n8n nightly workflow:
  2:00am → run all 14 fault scenarios
  → embed results → Qdrant fault_history
  → post summary to Discord: "14/14 passed. Training data: +14 rows."

Target: 50 scenarios/hour. First milestone: 14/14 pass nightly unattended.

---

### Pillar 5 — Skills + Boot Layer (Week 1, parallel)

Status: Partially planned

Every session Claude loads (via /boot skill):
  1. CLAUDE.md — identity, model routing, safety rules
  2. GOALS.md — what FactoryLM is, business context
  3. .planning/org/INDEX.yaml — all 86 repos
  4. .planning/org/OUTCOMES.md — what repos do
  5. .planning/org/CONSOLIDATION_PLAN.md — what merges where
  6. .planning/specs/ — current active specs
  7. DARK_FACTORY_GUIDE.md — full dark factory architecture
  8. ARRESTED_DEVELOPMENT.md — this file

Skills to write (/.claude/skills/):
  boot.md             — session loader (loads all above)
  repo-map.md         — maps any repo → MAP.md + manifest.yaml
  org-index.md        — finds what you already have by outcome
  plc-adapter.md      — checks before building any PLC interface
  maintenance-brain.md — loads GR00T + Factory IO + RAG context
  dark-factory.md     — loads DTU harness context + holdout rules

---

## EXECUTION ORDER (non-negotiable sequence)

Week 0 (TODAY):
  [ ] Merge PR #126
  [ ] Execute 5 partial merges into monolith
  [ ] Write factory_server.py (Phase 0 of 4-Focus Build)
  [ ] Verify: factory_read_state() returns live tag data

Week 1:
  [ ] Search archived repos for lost n8n workflows — resurrect if found
  [ ] factorylm/kb/neon_rag.py (pgrag on existing Neon data)
  [ ] factorylm/kb/llamacloud_ingest.py (PDF pipeline)
  [ ] Write /boot skill and GOALS.md
  [ ] n8n hybrid RAG query workflow JSON

Week 2:
  [ ] factorylm/tests/scenario_runner.py (Factory IO DTU)
  [ ] 14 fault scenario YAML files (visible)
  [ ] holdout/ folder structure (sacred, Claude-blind)
  [ ] First nightly run: 14 scenarios → results → Discord

Week 3:
  [ ] video_capture.py + scenario_runner batch (Phase 1 of 4-Focus Build)
  [ ] training_export.py → Parquet + SFT JSONL
  [ ] Qdrant running locally, first collection: fault_history
  [ ] KB builder n8n workflow ingesting nightly

Week 4-5:
  [ ] LangGraph fault_diagnosis_flow.py (Phase 4 of 4-Focus Build)
  [ ] LangGraph data_collection_flow.py
  [ ] verify_loop.py → accuracy report on all 14 scenarios
  [ ] GR00T training loop stub (ROUTE D from Dark Factory Guide)

---

## BACKLOG (parked — do NOT touch during Arrested Development)

These are real ideas that came up today. Park here, not in code:

- Full dark factory Level 5 (no human reads or reviews code)
- GR00T N1.6 conveyor visual inspection trained skill
- Cosmos R2 fine-tuning pipeline (fine_tune_pipeline.py)
- Local model migration (Ollama, drop $200/month Anthropic spend)
- IndustrialSkillsHub integration with FactoryLM KB
- RideView bolt inspection CV system
- openclaw v2 (it works, don't touch it)

---

## WHAT CLAUDE MUST CHECK EVERY SESSION

1. Is there a CONSOLIDATION_PLAN.md item that already does this?
   → cat .planning/org/CONSOLIDATION_PLAN.md | grep -i "<topic>"

2. Is there an existing file in the monolith that does this?
   → grep -r "<function_or_class>" factorylm/ --include="*.py" -l

3. Is the repo I'm about to clone already in INDEX.yaml?
   → grep -i "<repo_name>" .planning/org/INDEX.yaml

4. Am I building a new feature or building the foundation?
   → If new feature: write it to BACKLOG.md, stop.
   → If foundation: check the Arrested Development checklist above.

---

## STATUS TRACKER

| Pillar | Status | Blocking |
|---|---|---|
| 1 — Repo Foundation | Done | Nothing |
| 2 — MCP Factory Tools | This weekend | Nothing |
| 3 — RAG / KB Pipeline | Week 1 | Pillar 2 done |
| 4 — Factory IO DTU | Week 2 | Pillar 2 + 3 |
| 5 — Skills + Boot Layer | Week 1 parallel | Nothing |

Last updated: March 6, 2026
Branch: chore/arrested-development-foundation
