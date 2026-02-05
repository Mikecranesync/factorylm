# 📜 Spec-Driven Development (SDD)

> "Spec first, prompt template second, execute third. How can you possibly fail?"
> — Mike, 2026-02-04

---

## The Problem

When something is "not done," it's just... not done. Sitting on a Trello board. No urgency. No proactive completion.

**Current state:** Agents note gaps, move on.
**Desired state:** Agents are relentless. They TRY. They're gated by QA, so let them experiment.

---

## The Principle

```
┌─────────────────────────────────────────────────────────────┐
│                 SPEC-DRIVEN DEVELOPMENT                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. SPEC FIRST                                               │
│     Define what "done" looks like                            │
│     Acceptance criteria, not vague goals                     │
│     "The quality gate will be wired when..."                 │
│                                                              │
│  2. PROMPT TEMPLATE SECOND                                   │
│     Create reusable prompt for this task type                │
│     Tailored to model context window                         │
│     Includes success criteria from spec                      │
│                                                              │
│  3. EXECUTE THIRD                                            │
│     Agent attempts the work                                  │
│     Hammurabi judges output                                  │
│     If fail → retry with polish                              │
│     If pass → archive + celebrate                            │
│                                                              │
│  4. HOW CAN YOU FAIL?                                        │
│     Spec is clear → know what to build                       │
│     Template is ready → know how to ask                      │
│     QA gates exist → safe to try                             │
│     Feedback loop → learn from attempts                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Agent Behavior Mandate

**AGENTS.md must enforce:**

1. **No quitting** — If something is "not done," attempt it or create a plan to attempt it
2. **Proactive completion** — Don't wait to be asked. See gap → fill gap
3. **Safe experimentation** — Hammurabi gates everything. Try things.
4. **Escalate blockers** — If truly stuck, ping Mike with specifics, not vague "couldn't do it"

**Anti-patterns to eliminate:**
- ❌ "This is not yet implemented"
- ❌ "TODO: wire this up"
- ❌ "Future work"

**Replace with:**
- ✅ "Attempting to implement now..."
- ✅ "Implementation blocked by [X]. Creating card. Notifying Mike."
- ✅ "Spec exists at [path]. Executing phase 1 of 3..."

---

## Prompt Template System

### Why Templates?

| Model | Context Window | Interaction Style |
|-------|---------------|-------------------|
| Claude Opus | 200K | Long-form, detailed |
| Claude Sonnet | 200K | Balanced |
| GPT-4o | 128K | Structured JSON |
| Gemini | 1M+ | Massive context |
| Local (Ollama) | 4-32K | Short, focused |

One prompt doesn't fit all. Templates adapt to:
- Context window limits
- Model strengths (reasoning vs speed)
- Output format preferences
- Task complexity

### Template Structure

```yaml
# /templates/{task_type}.yaml

name: "wire_quality_gate"
description: "Wire Hammurabi quality gate to worker outputs"
version: 1.0

spec:
  acceptance_criteria:
    - All worker outputs pass through quality_gated decorator
    - Judgments logged to database
    - Failed outputs trigger polish loop
  success_metric: "100% of outputs judged before archive"

prompt:
  system: |
    You are implementing a quality gate system.
    The spec is: {spec}
    
    Rules:
    1. Attempt implementation, don't just describe
    2. If blocked, state exactly what's missing
    3. Output working code, not pseudocode
    
  user: |
    Wire Hammurabi to {worker_name} worker.
    
    Current worker code:
    {worker_code}
    
    Hammurabi interface:
    {hammurabi_interface}
    
    Produce: Modified worker code with quality gate.

variants:
  short_context:
    # For Ollama/local models
    max_tokens: 2000
    system: "Implement quality gate. Be concise."
    
  long_context:
    # For Claude/GPT-4
    include_examples: true
    include_full_spec: true
```

---

## Template Categories

### 1. Code Generation Templates
- `implement_feature.yaml`
- `fix_bug.yaml`
- `refactor_code.yaml`
- `add_tests.yaml`

### 2. Documentation Templates
- `write_spec.yaml`
- `create_readme.yaml`
- `document_api.yaml`
- `write_procedure.yaml`

### 3. Analysis Templates
- `review_code.yaml`
- `analyze_logs.yaml`
- `find_patterns.yaml`
- `research_topic.yaml`

### 4. Communication Templates
- `summarize_for_mike.yaml`
- `write_email.yaml`
- `create_report.yaml`
- `escalate_blocker.yaml`

---

## Implementation Plan

### Phase 1: Create Template Directory
```
mikes-brain/templates/
├── code/
├── docs/
├── analysis/
├── communication/
└── _base.yaml  # Shared components
```

### Phase 2: Wire Templates to Workers
- Each worker loads relevant template
- Template includes spec + prompt + variants
- Worker selects variant based on target model

### Phase 3: Auto-Generation
- When creating new task type, generate template skeleton
- Fill in spec from Trello card
- Prompt engineering becomes systematic, not ad-hoc

---

## The Tablet (Canonical Reference)

All of this gets ensconced in:

| File | Purpose |
|------|---------|
| `AGENTS.md` | Behavior rules for all agents |
| `SOUL.md` | Personality and principles |
| `templates/*.yaml` | Prompt templates per task type |
| `specs/*.md` | Acceptance criteria per feature |

**The Tablet = AGENTS.md + SOUL.md + templates/ + specs/**

If it's not in the Tablet, it doesn't exist.

---

## Enforcement

Hammurabi will judge:
1. **Did the agent attempt the work?** (not just note it)
2. **Did the agent use the correct template?**
3. **Does output match spec acceptance criteria?**

Agents that quit without trying get flagged in evolution cycle.

---

*Captured 2026-02-04. This is law.*
