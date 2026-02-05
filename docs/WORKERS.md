# 🏛️ Worker Registry - Mike's Brain

> "Give me a lever long enough and a fulcrum on which to place it, and I shall move the world." — Archimedes

## The Pantheon

All workers are named after historical figures who shaped knowledge, justice, or engineering.

| Worker | Role | Historical Figure | Status |
|--------|------|-------------------|--------|
| **Herodotus** | Archivist - collects & synthesizes | Father of History (484-425 BC) | ✅ Code ready |
| **Hammurabi** | Judge - QA gates & quality | Babylonian lawgiver (1792-1750 BC) | ✅ Code ready |
| **Archimedes** | Orchestrator - coordinates swarm | Greek engineer (287-212 BC) | 🔄 Renamed from Master of Puppets |
| **Tesla** | Executor - takes autonomous actions | Inventor & engineer (1856-1943) | 📋 Planned |
| **Hypatia** | Analyst - finds patterns & insights | Alexandrian mathematician (350-415 AD) | 📋 Planned |
| **Gutenberg** | Publisher - output formatting | Printing press inventor (1400-1468) | 📋 Planned |
| **Prometheus** | Trainer - creates training data | Titan who brought fire to humanity | 📋 Planned |
| **Edison** | Inventor - extracts ideas from chaos | "Genius is 1% inspiration, 99% perspiration" | 📋 Planned |

---

## Archimedes (formerly Master of Puppets)

**Role:** The Orchestrator — coordinates all Celery workers, manages the swarm, ensures tasks flow correctly.

**Location:** `/opt/master_of_puppets/` (legacy path, will migrate to `/opt/archimedes/`)

**Capabilities:**
- 22-agent Celery swarm coordination
- Task scheduling and routing
- Health monitoring
- Synthetic KB generation
- GitHub analysis

**Why Archimedes:**
- Invented the lever, pulley, and screw — fundamental automation tools
- "Give me a lever and I'll move the world" = give me a swarm and I'll automate everything
- Engineer + mathematician + inventor

---

## Prometheus (NEW)

**Role:** The Trainer — documents every process as training data for future AI systems.

**Philosophy:** Every workflow Mike builds through natural language is valuable training data. Prometheus captures:
- Input: What Mike said (voice/text)
- Process: What actions were taken
- Output: What was produced
- Outcome: Did it work? What was learned?

**Format:** JSONL training pairs
```json
{"input": "set up doppler for api key management", "process": [...steps...], "output": "doppler configured", "success": true}
```

---

## The Pipeline

```
[Mike's Voice/Text]
        ↓
   [Telegram]
        ↓
   [Clawdbot]
        ↓
   [Archimedes] ← Orchestrates everything
        ↓
   ┌────┴────┐
   ↓         ↓
[Workers]  [Prometheus]
   ↓         ↓
[Actions]  [Training Data]
   ↓         ↓
[Results]  [Future AI]
```

---

## Adding New Workers

1. Pick a historical figure whose legacy matches the role
2. Create worker file in `/workers/{name}.py`
3. Add to this registry
4. Document capabilities and status
