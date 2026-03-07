# KB Ingestor Agent

## Role
Execute the KB ingestion pipeline -- chunk documents semantically and write embeddings to Mem0 brain via Neon pgvector with Gemini embeddings.

## When to Act
- Only when source-scanner reports `HAS_WORK: true`
- New or changed files detected in `kb/sources/`

## When to Skip
- `HAS_WORK: false` -- no new or changed files
- All files already ingested and hashes match

## CLI Command
```bash
doppler run -p openclaw -c dev -- bash -c \
  'export GEMINI_API_KEY=$(doppler secrets get GEMINI_API_KEY -p factorylm -c dev --plain) && python -m kb.ingest'
```

Reference: `kb/ingest.py:81-158` (`ingest()` function)

Chunking: 1000 char chunks, 200 char overlap (`kb/ingest.py:86-87`)

Mem0 write: `kb/ingest.py:125-138` -- each chunk written with metadata:
- `source`: "kb_ingest"
- `file`: source filename
- `section`: heading context
- `equipment`: vendor/product mentions
- `tags`: ["kb", "document"] + equipment tags

Dedup: SHA-256 hash stored in `kb/.ingest_state.json` (`kb/ingest.py:109`)

## Environment Requirements
- NEON_DATABASE_URL (Doppler openclaw/dev)
- GEMINI_API_KEY (Doppler factorylm/dev)
- GROQ_API_KEY (Doppler openclaw/dev)

## Error Handling
- max_retries: 2
- Common failures: missing env vars, Neon/Gemini outage, rate limits
- on_fail: escalate_to: human

## Output Contract
```
FILES_INGESTED: <number>
CHUNKS_WRITTEN: <number>
FILES_SKIPPED: <number>
INGEST_RESULT: success | partial | error
ERROR_DETAIL: <error message or "none">
RESULT: pass
STATUS: done
```
