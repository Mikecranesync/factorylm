# Brain Recorder Agent

## Role
Capture diagnosis results and troubleshoot resolutions into Mem0 brain (Neon pgvector) for future KB retrieval via RAG.

## When to Capture
- DIAGNOSE intent with successful diagnosis text
- TROUBLESHOOT intent with resolution state (session completed)

## When to Skip
- STATUS, IO, GENERAL intents (not KB-worthy)
- Failed service calls
- Empty diagnosis text

## Mem0 API
```python
from services.brain.config import get_memory

mem = get_memory()
mem.add(content, user_id="mike", metadata={
    "source": "telegram-diagnosis",
    "tags": ["diagnosis", "telegram", "fault-{code}"],
    "intent": "DIAGNOSE",
    "error_code": 3,
    "has_fault": True,
    "timestamp": "2026-03-07T12:00:00Z"
})
```

Reference: `services/mcp/brain_server.py:90-114` (`brain_capture` tool)
Config: `services/brain/config.py` — Mem0 + pgvector on Neon + Gemini embeddings

## Content Format

### Diagnosis
```
Diagnosis: [user question] -> [diagnosis text]. Error code: [code]. Sources: [source list]
```

### Troubleshoot Resolution
```
Troubleshoot: [user question] -> [resolution steps]. Tree: [tree slug]
```

## Environment Requirements
- NEON_DATABASE_URL (Doppler openclaw/dev)
- GEMINI_API_KEY (Doppler factorylm/dev)
- GROQ_API_KEY (Doppler openclaw/dev)

If env vars missing, skip capture gracefully (non-fatal).

## Output Contract
```
CAPTURED: true | false | skipped
CAPTURE_REASON: <reason>
```
