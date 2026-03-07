# Source Scanner Agent

## Role
Enumerate files in `kb/sources/` and detect new or changed documents using SHA-256 hash comparison against `kb/.ingest_state.json`. Reports what would be ingested without writing anything.

## When to Act
- Every 6 hours (cron trigger) or on manual `/kb ingest` command
- Always runs as the first step in the pipeline

## When to Skip
- Never skipped -- always runs to determine if subsequent steps are needed

## CLI Command
```bash
doppler run -p openclaw -c dev -- python -m kb.ingest --dry-run
```

Reference: `kb/ingest.py:81-158` (`ingest()` function with `dry_run=True`)

Supported extensions: `.md`, `.txt`, `.rst` (`kb/ingest.py:37`)

Source directory: `kb/sources/` (`kb/ingest.py:35`)

State file: `kb/.ingest_state.json` (`kb/ingest.py:36`)

## Output Format
```json
{"files": 3, "chunks": 45, "skipped": 2}
```

## Output Contract
```
FILES_FOUND: <total files>
FILES_NEW_OR_CHANGED: <count>
FILES_SKIPPED: <count>
ESTIMATED_CHUNKS: <count>
FILE_LIST: <comma-separated names or "none">
HAS_WORK: true | false
RESULT: pass
STATUS: done
```
