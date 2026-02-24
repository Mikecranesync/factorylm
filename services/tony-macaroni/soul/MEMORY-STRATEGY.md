# FactoryLM Memory Architecture

5-layer memory system for persistent factory intelligence. Tony orchestrates writes; sub-agents and antfarm workflows read.

---

## Layer 1: Context Memory

**What:** Active conversation state within a single session.
**Owner:** Clawdbot's built-in `contextPruning` (already working).
**Scope:** Per-session, ephemeral.

No additional infrastructure needed — this is handled by the clawdbot runtime. Context is pruned automatically as conversations grow beyond the context window.

**Integration:** All agents inherit context memory from their session. Tony's SOUL.md and AGENTS.md are loaded as system context.

---

## Layer 2: Episodic Memory

**What:** Timestamped event log of factory incidents, maintenance actions, and agent decisions. Each episode is a complete record: what happened, what was tried, what worked.

**Owner:** Tony writes episodes; all agents read.

**pgvector Schema:**

```sql
CREATE TABLE episodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    event_type TEXT NOT NULL,        -- 'fault', 'repair', 'dispatch', 'escalation'
    source TEXT NOT NULL,            -- 'alarm-monitor', 'triager', 'wo-creator', etc.
    node_id TEXT,                    -- PLC/equipment identifier
    fault_code TEXT,
    summary TEXT NOT NULL,
    details JSONB,                   -- Full structured data
    resolution TEXT,                 -- What fixed it (null if unresolved)
    resolution_time_min INTEGER,
    technician TEXT,
    tags TEXT[],                     -- Searchable labels
    embedding VECTOR(1536) NOT NULL  -- OpenAI text-embedding-3-small
);

CREATE INDEX idx_episodes_embedding ON episodes
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_episodes_event_type ON episodes (event_type);
CREATE INDEX idx_episodes_node_id ON episodes (node_id);
CREATE INDEX idx_episodes_fault_code ON episodes (fault_code);
CREATE INDEX idx_episodes_timestamp ON episodes (timestamp DESC);
```

**Write pattern (from antfarm workflows):**

```python
# maintenance-dispatcher/followup stores resolution episodes
episode = {
    "event_type": "repair",
    "source": "maintenance-dispatcher",
    "node_id": "plc-laptop",
    "fault_code": "E001",
    "summary": "Motor bearing failure on conveyor 3",
    "details": {"tags": {...}, "wo_id": "WO-2026-0223-001"},
    "resolution": "Replaced bearing, realigned coupling",
    "resolution_time_min": 45,
    "technician": "Mike",
    "tags": ["motor", "bearing", "conveyor"]
}
embedding = embed(episode["summary"] + " " + episode.get("resolution", ""))
insert_episode(episode, embedding)
```

**Read pattern (from triager agent):**

```python
# Find similar past incidents for triage
similar = query_episodes(
    embedding=embed("Motor stalled, high current on conveyor 3"),
    filter={"fault_code": "E001"},
    limit=5
)
# Returns: past resolutions, avg repair time, common root causes
```

**Workflow integration:**
- `maintenance-dispatcher` → followup agent writes repair episodes
- `maintenance-dispatcher` → triager agent reads similar episodes
- `ops-reporter` → data-collector queries episode counts and patterns

---

## Layer 3: Semantic Memory

**What:** RAG index over factory documentation — manuals, SOPs, post-mortems, wiring diagrams, parts lists.

**Owner:** Indexed on ingest; queried by any agent.

**pgvector Schema:**

```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type TEXT NOT NULL,       -- 'manual', 'sop', 'post_mortem', 'wiring', 'parts'
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,                  -- manufacturer, model, section, page
    equipment_tags TEXT[],           -- Equipment this doc applies to
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    embedding VECTOR(1536) NOT NULL
);

CREATE INDEX idx_documents_embedding ON documents
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_documents_source_type ON documents (source_type);
```

**Document types:**

| Type | Source | Example |
|------|--------|---------|
| manual | PDF ingest | Allen-Bradley Micro820 User Manual |
| sop | Mike's notes | "How to replace motor bearings on conveyor" |
| post_mortem | Incident reviews | "2026-02-15: Pressure sensor failure root cause" |
| wiring | Feature 001 output | Panel A wiring reconstruction |
| parts | KB enrichment | Eaton DILM25-10 contactor datasheet |

**Read pattern (from triager, diagnosis, or robot-advisor):**

```python
# Find relevant SOPs for a fault
docs = query_documents(
    embedding=embed("Allen-Bradley Micro820 fault code E001 motor stall"),
    filter={"source_type": ["manual", "sop"]},
    limit=3
)
```

**Workflow integration:**
- `wiring-telegram` → KB enrichment writes parts/wiring docs
- `maintenance-dispatcher` → triager reads manuals + SOPs
- `robot-advisor` → safety-checker reads robot manuals
- `ops-reporter` → analyzer references post-mortems

---

## Layer 4: Lessons Learned

**What:** Structured playbook cards distilled from resolved episodes. Each card is a proven fix pattern: "When you see X, do Y, because Z."

**Owner:** Tony generates cards after episode resolution; reviewed by Mike.

**pgvector Schema:**

```sql
CREATE TABLE playbook_cards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,              -- "Motor stall on conveyor — bearing check"
    trigger_pattern TEXT NOT NULL,    -- What symptoms activate this card
    diagnosis TEXT NOT NULL,          -- Root cause explanation
    fix_steps TEXT[] NOT NULL,        -- Ordered repair steps
    time_estimate_min INTEGER,
    skill_required TEXT[],            -- ['mechanical', 'electrical']
    equipment_tags TEXT[],            -- ['conveyor', 'motor', 'micro820']
    confidence FLOAT DEFAULT 0.5,    -- Increases with successful uses
    use_count INTEGER DEFAULT 0,
    last_used TIMESTAMPTZ,
    source_episodes UUID[],          -- Episode IDs this card was derived from
    created_at TIMESTAMPTZ DEFAULT now(),
    approved_by TEXT,                 -- null until Mike approves
    embedding VECTOR(1536) NOT NULL
);

CREATE INDEX idx_playbook_embedding ON playbook_cards
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
CREATE INDEX idx_playbook_confidence ON playbook_cards (confidence DESC);
```

**Card lifecycle:**

1. **Generate:** After 2+ similar episodes resolve the same way, Tony proposes a card
2. **Review:** Card sent to Mike via Telegram for approval
3. **Activate:** Approved cards are available to triager and diagnosis agents
4. **Strengthen:** Each successful use increments `use_count` and boosts `confidence`
5. **Promote to Layer 0:** Cards with confidence > 0.95 and use_count > 10 are candidates for conversion to deterministic PLC code (the ultimate goal)

**Read pattern (from triager):**

```python
# Find matching playbook cards for a fault
cards = query_playbook(
    embedding=embed("Motor high current, vibration spike, conveyor 3"),
    min_confidence=0.6,
    limit=3
)
# Returns: proven fix steps, time estimate, required skills
```

**Workflow integration:**
- `maintenance-dispatcher` → triager reads cards for instant diagnosis
- `maintenance-dispatcher` → followup writes new episodes that feed card generation
- Tony → periodic card generation from clustered episodes

---

## Layer 5: Technician Profiles

**What:** Skill inventories, repair history, and performance metrics per technician. Used for intelligent dispatch and training recommendations.

**Owner:** Tony maintains; dispatcher and triager read.

**pgvector Schema:**

```sql
CREATE TABLE technician_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    telegram_id BIGINT,
    skills TEXT[] NOT NULL,           -- ['electrical', 'mechanical', 'controls', 'welding']
    certifications TEXT[],            -- ['allen-bradley', 'fanuc', 'arc-flash']
    shift_pattern TEXT,               -- 'day', 'night', 'rotating'
    avg_resolution_min JSONB,         -- {"motor": 35, "sensor": 20, "plc": 45}
    total_wo_completed INTEGER DEFAULT 0,
    total_wo_escalated INTEGER DEFAULT 0,
    success_rate FLOAT DEFAULT 1.0,
    specialty_tags TEXT[],            -- Equipment they're fastest on
    training_gaps TEXT[],             -- Areas needing improvement
    last_active TIMESTAMPTZ,
    embedding VECTOR(1536) NOT NULL   -- Embedded skill+history profile
);

CREATE INDEX idx_tech_embedding ON technician_profiles
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 20);
CREATE INDEX idx_tech_skills ON technician_profiles USING gin (skills);
```

**Dispatch matching (from triager):**

```python
# Find best tech for a motor fault during night shift
candidates = query_technicians(
    embedding=embed("motor bearing replacement, conveyor, electrical"),
    filter={"shift_pattern": "night", "skills": {"$contains": "mechanical"}},
    limit=3
)
# Rank by: skill match * success_rate * (1 / avg_resolution_min["motor"])
```

**Profile update (from followup):**

```python
# After WO resolution, update tech profile
update_technician(
    name="Mike",
    wo_completed_increment=1,
    resolution_time={"motor": 45},  # Running average update
    last_active=now()
)
```

**Workflow integration:**
- `maintenance-dispatcher` → triager queries for best tech match
- `maintenance-dispatcher` → followup updates profiles after resolution
- `ops-reporter` → analyzer includes tech performance in weekly report

---

## Cross-Layer Data Flow

```
                    ┌─────────────────────┐
                    │  Layer 1: Context    │  (ephemeral, per-session)
                    └──────────┬──────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         ▼                     ▼                     ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Layer 2:        │  │ Layer 3:        │  │ Layer 5:        │
│ Episodes        │  │ Semantic (RAG)  │  │ Tech Profiles   │
│ (what happened) │  │ (how to fix)    │  │ (who can fix)   │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                    │                     │
         └────────────┬───────┘                     │
                      ▼                             │
            ┌─────────────────┐                     │
            │ Layer 4:        │◄────────────────────┘
            │ Playbook Cards  │
            │ (proven fixes)  │
            └────────┬────────┘
                     │
                     ▼ (confidence > 0.95)
            ┌─────────────────┐
            │ Layer 0:        │
            │ Deterministic   │
            │ PLC Code        │
            └─────────────────┘
```

**The Goal:** Intelligence flows downward. Every Layer 2 episode and Layer 4 playbook card is a step toward Layer 0 deterministic code that runs inside the PLC without AI.

---

## Infrastructure Requirements

| Component | Status | Notes |
|-----------|--------|-------|
| PostgreSQL + pgvector | Needed | Deploy on Hetzner (100.67.25.53) or VPS |
| text-embedding-3-small | Available | Via OpenAI API, $0.02/1M tokens |
| Antfarm CLI | Not installed | Workflows run manually until openclaw CLI available |
| Telegram (Gus bot) | Working | @FactoryLM_bot active |
| Matrix API | Working | http://100.72.2.99:8000 |
| CMMS Gist | Working | Feature 002 templates |

**Next step:** Deploy pgvector on Hetzner, create tables, seed with existing incident data from Matrix API.
