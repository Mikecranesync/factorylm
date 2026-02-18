# Ops Trace: GistSkill + ProjectSkill

**Date:** 2026-02-17
**Branch:** `feat/gist-project-skills`
**VPS Commit:** `f2c2b56`

## What Changed

Added two new skills to OpenClaw so Jarvis can create gists and scaffold projects from Telegram.

### Files Modified (4)

| File | Change |
|------|--------|
| `openclaw/types.py` | Added `GIST` and `PROJECT` to Intent enum |
| `openclaw/messages/intent.py` | Added `/gist`, `/project` command shortcuts + regex patterns for natural language triggers |
| `openclaw/llm/router.py` | Added GIST/PROJECT routes (openrouter primary), added `json_mode` passthrough |
| `openclaw/skills/registry.py` | Registered GistSkill and ProjectSkill (11 skills total) |

### Files Created (2)

| File | Purpose |
|------|---------|
| `openclaw/skills/builtin/gist.py` | Document generation + GitHub Gist publishing |
| `openclaw/skills/builtin/project.py` | Multi-file project scaffolding + multi-file Gist publishing |

## GistSkill Flow

1. Auth check (telegram_allowed_users)
2. Strip `/gist` prefix, validate non-empty
3. Search KB for context enrichment
4. Call LLM with document generation system prompt (max 3000 words)
5. Infer filename from content type (PRD_, research_, build-guide_, spec_, etc.)
6. Write to temp file, `gh gist create --public`
7. Return gist URL + metadata (or inline content if gist fails)

## ProjectSkill Flow

1. Auth check
2. Strip `/project` prefix, validate non-empty
3. Search KB for context
4. **Phase 1:** Call LLM with `json_mode=True` for project spec JSON
5. Parse JSON (strip markdown fences if needed), cap at 8 files
6. **Phase 2:** For each file, call LLM with file-specific context
7. Write all files to temp dir, `gh gist create --public` with all files
8. Return gist URL + file list + tech stack

## Intent Classification

- `/gist ...` and `/project ...` → direct command map
- `draft a PRD`, `write up`, `technical spec`, etc. → GIST regex
- `scaffold`, `build me`, `create a project`, etc. → PROJECT regex
- PROJECT patterns placed before GIST to avoid overlap

## Verification

- 11 skills registered in journalctl (was 9)
- Health check: `curl localhost:8340/` shows gist + project in skills list
- All Python files pass `ast.parse()` syntax check

## Router Enhancement

Added `json_mode: bool = False` parameter to `LLMRouter.route()` and `_call()` methods, passing through to `LLMProvider.complete()`. Backwards compatible — existing callers unaffected.
