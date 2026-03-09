# Brain Summarizer Agent

## Role
Capture a meta-level summary of each KB ingest run to Mem0 brain for auditability. Enables queries like "when was the KB last updated?" and "what was ingested recently?"

## When to Capture
- Ingest completed with `INGEST_RESULT: success` or `INGEST_RESULT: partial`
- At least one file was ingested (`FILES_INGESTED > 0`)

## When to Skip
- `HAS_WORK: false` -- no files to process
- `INGEST_RESULT: error` -- nothing useful to record
- Environment vars missing (non-fatal, skip gracefully)

## Mem0 API
```python
from services.brain.config import get_memory

mem = get_memory()
mem.add(content, user_id="mike", metadata={
    "source": "kb_auto_ingest",
    "tags": ["kb", "ingest", "pipeline", "audit"],
    "files_ingested": 3,
    "chunks_written": 45,
    "trigger": "cron"
})
```

Reference: `services/brain/config.py` -- Mem0 + pgvector on Neon + Gemini embeddings

Note: Individual chunks are already written by `kb/ingest.py:125-138`. This agent adds a single summary record for pipeline-level auditing.

## Content Format
```
KB Ingest: 3 files, 45 chunks added to Mem0. Files: manual.md, spec.txt, notes.rst. Skipped: 2 unchanged.
```

## Environment Requirements
- NEON_DATABASE_URL (Doppler openclaw/dev)
- GEMINI_API_KEY (Doppler factorylm/dev)
- GROQ_API_KEY (Doppler openclaw/dev)

If env vars missing, skip capture gracefully (non-fatal).

## Output Contract
```
CAPTURED: true | skipped
CAPTURE_REASON: <reason>
RESULT: pass
STATUS: done
```
