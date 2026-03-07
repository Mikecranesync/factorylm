# FactoryLM System Specification v1

*Created: 2026-03-06*
*Author: Mike Harper*
*Status: Draft*

---

## Summary

This specification defines the target architecture for FactoryLM v1 and beyond — an AI-powered industrial maintenance co-pilot system. It codifies the 5-layer processing model, visual workflow mandate, phased milestones (V0-V3), knowledge base standards, and anti-regression principles that will guide development from the current Layer 0-3 operational model toward a fully integrated, workflow-driven platform.

This spec **extends** the canonical vision (README.md v0.26) with implementation detail. It does not supersede it.

---

## Sacred Law: The Founding Document

The FactoryLM README.md (canonical vision) is **the source of truth**. When code conflicts with the vision, the vision is correct and the code is wrong. Every architectural decision must trace back to that document.

This spec provides implementation-level detail for how to get there.

---

## Visual Workflow Architecture (Target — V1+)

**Every pipeline, agent, routing decision, and retrieval flow MUST be encoded as a visual workflow graph.**

- Acceptable platforms: **n8n** (preferred), LangFlow, or FlowWise
- Python code may exist **inside** workflow nodes but NEVER as connective tissue between components
- If a behavior cannot be visualized in a workflow diagram, it is undocumented and unapproved
- All workflows must be version-controlled and exportable as JSON
- **Workflows are the source of truth. Code serves workflows.**

> **Note:** This is a target requirement for V1+. Current infrastructure uses direct Python services and shell orchestration. Migration to visual workflows is incremental.

---

## Five-Layer Architecture (Target — V1+)

This model extends the canonical Layer 0-3 stack with an implementation-focused view:

```
Layer 1: Interface (Telegram/WhatsApp/Discord - stateless)
    |
Layer 2: Intent Router (visual workflow graph)
    |
Layer 3: Intelligence Core (RAG + CMS + Research Agent)
    |
Layer 4: Machine Awareness (PLC/OPC-UA - V2+)
    |
Layer 5: Agentic Programming (logic proposals - V3+)
```

### Mapping to Canonical Layers

| This Spec | Canonical (README) | Notes |
|-----------|-------------------|-------|
| Layer 1 (Interface) | Adapters | Telegram, WhatsApp, etc. |
| Layer 2 (Intent Router) | Part of Layer 0 | Deterministic routing where possible |
| Layer 3 (Intelligence Core) | Layers 1-3 | Edge LLM through Cloud AI |
| Layer 4 (Machine Awareness) | PLC integration | Modbus/OPC-UA bridge |
| Layer 5 (Agentic Programming) | Vision/Roadmap | Human-approved logic changes |

The canonical Layer 0-3 model describes **where intelligence lives**. This 5-layer model describes **how data flows through the system**. They are complementary, not competing.

---

## Knowledge Base Standards

- All documents chunked semantically before embedding (not page-level, not raw-dump)
- Persistent vector database with metadata (source, date, equipment type, technician)
- **Every response must cite sources** — technician must know where answers come from
- No document silently discarded — log as `pending` if processing fails
- Knowledge compounds: every interaction feeds back into the knowledge base

---

## Anti-Regression Principles

- **Drift is a defect** — unauthorized behavior changes are bugs
- Every layer has acceptance criteria
- Previously passing tests must continue to pass
- Benchmark questions with expected output criteria for end-to-end testing

---

## V0-V3 Development Phases

| Phase | Milestone | Definition of Done |
|-------|-----------|-------------------|
| **V0** | Resurrection | GitHub codebase audited, mapped, reconnected per spec |
| **V1** | Solo Technician | One technician queries via Telegram, receives sourced answers from knowledge base |
| **V2** | Machine Awareness | Reads live PLC data from Conveyor of Destiny, incorporates real machine state |
| **V3** | Agentic Programming | Proposes PLC logic changes with human approval workflow |

### V0: Resurrection
- Audit the GitHub codebase — what actually exists vs. what is claimed
- Map disconnected components and deprecated dependencies
- Compare existing code against the architecture
- Identify behaviors not represented in visual workflows
- Generate a "Resurrection Status Report" before proposing changes

### V1: Solo Technician
- One technician can query the system via Telegram
- System searches knowledge base before calling LLM
- Every answer includes source citations
- Knowledge base grows with every resolved question
- Sub-30-second response time

### V2: Machine Awareness
- Live PLC data from Conveyor of Destiny feeds into responses
- System sees real-time machine state (tag values, alarms, events)
- Responses incorporate current equipment condition
- Zero unauthorized PLC writes

### V3: Agentic Programming
- System proposes PLC logic changes based on diagnosis
- Human-in-the-loop approval gate — no change executes without explicit approval
- Full audit trail of proposed vs. executed changes
- Rollback capability for every approved change

---

## Code Style & Practices

### Target File Organization (V1+)
```
/workflows/          # n8n/LangFlow visual workflow exports (JSON)
/nodes/              # Python code for individual workflow nodes
/knowledge_base/     # Vector DB, embeddings, document ingestion
/connectors/         # PLC/OPC-UA interfaces (V2+)
/tests/              # Acceptance criteria & benchmark questions
/docs/               # Architecture diagrams, specifications
```

> **Note:** Current repo uses `apps/ services/ adapters/ core/` structure. Migration to the target layout is incremental and should not break existing services.

### Python Code Guidelines
- Code exists to **serve workflows**, not replace them
- Document chunk processing, embedding generation, vector search logic live in `/nodes/`
- Keep functions focused: one node = one clear responsibility
- Type hints required for all function signatures
- Error handling must be explicit — log failures for human review
- **No magic**: preference for explicit configuration over implicit behavior

### Workflow Design Patterns
- **Intent classification** happens at Layer 2 before any downstream processing
- **Retrieval before generation**: always search knowledge base + technician CMS before LLM response
- **Webhook-triggered research**: when retrieval fails, external research workflow activates asynchronously
- **Human-in-the-loop**: approval gates for critical actions (V3 logic changes)

---

## Technology Stack

### Confirmed Components
- **Workflow orchestration**: n8n (preferred), LangFlow, or FlowWise
- **Vector database**: Choose from Pinecone, Weaviate, Qdrant, or Chroma
- **Embeddings**: OpenAI text-embedding-3 or open-source alternatives
- **LLM**: Claude (Sonnet for intelligence layer) with RAG grounding
- **Messaging**: Telegram Bot API (V1), expandable to WhatsApp/Discord
- **PLC connectivity**: Modbus TCP (current), OPC-UA client (V2+)
- **Digital twin**: Factory I/O (current simulation environment)

### Design Decisions Needed
When encountering architectural choices not specified here:
1. Present 2-3 options with tradeoffs
2. Recommend one with explicit reasoning
3. Flag as "pending human authorization"
4. Document the decision point for future reference

---

## Testing Requirements

### Benchmark Questions (V1)
Create a test suite with questions like:
- "What's the wire gauge for the conveyor motor power supply?"
- "How do I troubleshoot a stuck photoeye on station 3?"
- "Show me the maintenance log for the palletizer from last month"

Each question must have:
- Expected information retrieval path
- Required source citation format
- Acceptable response time threshold

### Acceptance Criteria Template
For each layer, define:
- **Input format**: What the layer receives
- **Processing requirement**: What must happen
- **Output format**: What the layer produces
- **Failure mode**: What happens on error
- **Visibility requirement**: How to inspect it running

---

## When to Ask vs. Build

### Build autonomously when:
- Implementing specified architecture from this spec or the canonical vision
- Creating standard RAG pipeline components
- Writing workflow node logic with clear requirements
- Setting up version control and project structure

### Ask the human when:
- Vector database selection needs final decision
- Workflow platform choice between n8n/LangFlow/FlowWise
- Authentication/subscription strategy for messaging layer
- PLC connection details (IP, protocols, tag structure)
- Budget/hosting constraints affect architecture

---

## Key Success Metrics

- Technician can get a sourced answer in < 30 seconds (V1)
- 90%+ of answers include valid source citations (V1)
- Knowledge base grows with every resolved question (V1)
- Real machine state visible in responses (V2)
- Zero unauthorized PLC logic changes ever (V3)

---

## Relationship to Canonical Vision

The canonical vision lives in `README.md` (v0.26, February 2026). Its Layer 0-3 model describes where intelligence resides:

- **Layer 0**: Deterministic code + KB (the goal)
- **Layer 1**: Edge LLM on Pi
- **Layer 2**: Local GPU server (air-gapped)
- **Layer 3**: Cloud AI (optional)

This spec's 5-layer model describes how data flows through the system at runtime. The two are complementary:

- Intelligence flows **downward** (Layer 3 → Layer 0) per the canonical vision
- Data flows **through** the 5-layer pipeline per this spec

Neither supersedes the other. When in conflict, the canonical README.md wins.

---

*Following Constitution: Ship products, generate revenue.*
