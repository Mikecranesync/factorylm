# TESTS: Jarvis Baseline — 2026-02-16

## Purpose

Golden test cases derived from real Telegram interactions (Feb 15-16, 2026) and the Cosmos R2 competition plan. Run these manually via Telegram after any change to verify Jarvis behavior matches the golden baseline.

## How to Run

1. Ensure VPS service is running: `ssh root@100.68.120.99 "systemctl status openclaw"`
2. Open Telegram, message @FACTORYLM_bot (MikesOPENCLAW)
3. For each test, send the input and verify the response matches expected behavior
4. Mark PASS/FAIL with date in the results table below
5. If any test fails, check the [behavior-to-code map](../baselines/2026-02-16_jarvis_behavior_to_code.md) for the responsible file

## Related

- **Baseline**: [2026-02-16_openclaw_jarvis_baseline.md](../baselines/2026-02-16_openclaw_jarvis_baseline.md)
- **Behavior Map**: [2026-02-16_jarvis_behavior_to_code.md](../baselines/2026-02-16_jarvis_behavior_to_code.md)
- **Health Check Workflow**: [WF-007](../workflows/check-jarvis-baseline.md)

---

## Baseline Tests (Must Pass Now)

### T-001: Basic Greeting

- **Input type**: text
- **Input**: `hello`
- **Expected behavior**: Jarvis responds with a greeting that includes his name or identity. Uses structured formatting (emoji headers, bullets). Does NOT return "An error occurred". Does NOT give a generic multi-paragraph OpenClaw corporate intro.
- **Validates**: `prompts.py` (personality), `intent.py` (CHAT classification), `router.py` (groq routing)
- **Pass criteria**: Response is concise (<200 words), mentions industrial/maintenance context, uses Jarvis-style formatting
- **Historical**: Feb 15 13:33 FAIL (Node.js conflict), Feb 15 14:41 OK (generic), Feb 16 04:02 OK

### T-002: Self-Description

- **Input type**: text
- **Input**: `talk to me about yourself`
- **Expected behavior**: Jarvis describes himself as Mike's AI assistant at FactoryLM. Mentions industrial focus and key capabilities. Uses emoji formatting. Not generic corporate copy.
- **Validates**: `prompts.py` (identity), `router.py` (CHAT intent), groq provider
- **Pass criteria**: Mentions FactoryLM or Mike, references industrial/PLC/equipment, concise (<500 words)
- **Historical**: Feb 16 00:14 OK (long but informative)

### T-003: Equipment IO Request

- **Input type**: text
- **Input**: `show me io`
- **Expected behavior**: Returns PLC tag/IO data in structured format. Uses code blocks or tables. References Micro820 or conveyor tags.
- **Validates**: `intent.py` (STATUS or DIAGNOSE intent), `skills/builtin/status.py` or `diagnose.py`, Matrix connector
- **Pass criteria**: Contains tag names or register values, formatted with code blocks or structured layout
- **Historical**: Feb 15 23:50 GOOD (fake data, but correct format)

### T-004: Electrical Safety Question

- **Input type**: text
- **Input**: `I'm redoing the 220V feed so I can put the dead front back on the circuit breaker panel`
- **Expected behavior**: Safety-first response with lockout/tagout procedures. Mentions PPE, de-energize. References PLC tags if relevant. Structured steps.
- **Validates**: `prompts.py` (safety instructions), `intent.py` (DIAGNOSE), `router.py` (anthropic or groq), `skills/builtin/diagnose.py`
- **Pass criteria**: Contains "lockout" or "LOTO" or "de-energize", mentions safety gear, provides step-by-step guidance
- **Historical**: Feb 16 04:03 EXCELLENT (lockout/tagout + PLC tags + structured steps)

### T-005: Build Assistance

- **Input type**: text
- **Input**: `I am building the conveyor still`
- **Expected behavior**: Component checklist or build guidance. References conveyor components (PLC, motor, sensors, pneumatics). Uses bullet points. Asks about build status.
- **Validates**: `prompts.py` (equipment context), `router.py` (CHAT or DIAGNOSE), groq provider
- **Pass criteria**: Lists components or steps, uses bullet points, references safety interlocks
- **Historical**: Feb 16 04:02 GOOD (component checklist with safety)

### T-006: Photo Analysis (Micro820 PLC)

- **Input type**: photo + text
- **Input**: Photo of a Micro820 PLC with caption `Do you know what this is and what it means?`
- **Expected behavior**: Detailed PLC identification. Mentions Allen-Bradley/Rockwell, Micro820 model family. Identifies LEDs, terminal blocks, I/O modules. Notes visible labels or markers.
- **Validates**: `telegram.py:_on_photo()`, `intent.py` (PHOTO forced), `skills/builtin/photo.py`, gemini provider (vision)
- **Pass criteria**: Correctly identifies PLC vendor and model family, describes visible components, no error
- **Historical**: Feb 16 06:49 EXCELLENT (full analysis with LED states, wiring assessment, PMC V1.0 label)

### T-007: Photo Analysis (No Caption)

- **Input type**: photo (no caption)
- **Input**: Photo of industrial equipment, no text caption
- **Expected behavior**: Analysis of the equipment in the photo. Should NOT return error. Should identify visible components.
- **Validates**: `telegram.py:_on_photo()` (empty caption handling), gemini provider
- **Pass criteria**: Returns equipment description, no "An error occurred" or "Sorry, something went wrong"
- **Historical**: Feb 16 04:04 FAIL (no Gemini key), Feb 16 04:12 FAIL (Gemini error), Feb 16 06:49 PASS

### T-008: Voice Input (Basic STT)

- **Input type**: voice message
- **Input**: Voice message saying "Can you hear me now? Testing 1, 2, 3."
- **Expected behavior**: Accurate transcription displayed as `Heard: "..."`. Intelligent response acknowledging the voice test.
- **Validates**: `telegram.py:_on_voice()`, `_transcribe_voice()` (Groq Whisper), then text pipeline
- **Pass criteria**: Transcription matches spoken words, response acknowledges voice input
- **Historical**: Feb 16 07:31 GOOD ("Heard: 'Can you hear me now? Do you know what I'm saying? Testing 1, 2, 3.'")

### T-009: Voice Input (Factory Query)

- **Input type**: voice message
- **Input**: Voice message saying "Can you find the GIST file for my conveyor project?"
- **Expected behavior**: Transcription displayed, then asks clarifying questions about project name, location, or access level.
- **Validates**: STT → intent classification → appropriate skill
- **Pass criteria**: Understands the request, provides helpful guidance, does not hallucinate files
- **Historical**: Feb 16 07:31 GOOD (asked for project name, file location, access level)

### T-010: Help Routing

- **Input type**: text
- **Input**: `help`
- **Expected behavior**: Helpful guide to capabilities. Lists what Jarvis can do (diagnose, photo analysis, search, etc.). Uses friendly language.
- **Validates**: `intent.py` (HELP or CHAT, NOT ADMIN), `router.py` (correct routing), `prompts.py`
- **Pass criteria**: Does NOT return a health dump or raw JSON status. Lists capabilities in human-readable format.
- **Historical**: Feb 16 04:03 FAIL (returned health dump), fixed in commit b06806c

### T-011: Emoji Ack

- **Input type**: any text
- **Input**: Any message (e.g., "hello")
- **Expected behavior**: 👀 emoji reaction appears immediately on the sent message, BEFORE the text response arrives.
- **Validates**: `telegram.py:_ack()`, `ReactionTypeEmoji`
- **Pass criteria**: Emoji reaction visible within 1 second of sending
- **Historical**: Not in export (added in feat/tts-emoji-ack branch)

### T-012: TTS Voice Response

- **Input type**: text
- **Input**: `Tell me about the Micro820 PLC`
- **Expected behavior**: Text response AND a voice note (MP3) sent as a follow-up message. Voice should be the JennyNeural voice reading a cleaned-up version of the text.
- **Validates**: `telegram.py:_reply_voice()`, `_text_to_speech()`, `_strip_markdown()`, edge-tts
- **Pass criteria**: Voice note received alongside text, clearly spoken English, no garbled audio
- **Historical**: Not in export (added in feat/tts-emoji-ack branch)

### T-013: Long Response Chunking

- **Input type**: text
- **Input**: `Give me a detailed guide to troubleshooting a Micro820 PLC that won't communicate over Ethernet`
- **Expected behavior**: Long response split across multiple messages, each under 4096 chars. No "Message is too long" error from Telegram.
- **Validates**: `telegram.py:_chunk_text()`, `_reply()` (markdown fallback)
- **Pass criteria**: Response delivered in 1+ messages, no errors, readable formatting preserved
- **Historical**: Fixed in commit 8dce07d (was crashing before)

### T-014: Budget Endpoint

- **Input type**: HTTP GET
- **Input**: `curl -s http://100.68.120.99:8340/budget`
- **Expected behavior**: JSON with per-provider budget stats (requests_today, tokens_today, daily limits, within_budget flag)
- **Validates**: `app.py` (/budget endpoint), `budget.py:BudgetTracker.summary()`
- **Pass criteria**: Valid JSON returned with groq, anthropic, openrouter entries. Anthropic shows 100 req/day limit.

### T-015: Health Endpoint

- **Input type**: HTTP GET
- **Input**: `curl -s http://100.68.120.99:8340/`
- **Expected behavior**: JSON listing name ("Jarvis (OpenClaw)"), version, active providers (groq, anthropic, gemini), and all 7 skills
- **Validates**: `app.py` (root endpoint)
- **Pass criteria**: Lists groq + gemini as providers, lists all 7 skills (diagnose, status, photo, work_order, admin, search, chat)

---

## Cosmos R2 Forward-Looking Tests

These test cases anticipate the Industrial AI Swarm integration from the Phased Implementation Plan. They are **NOT expected to pass today**. They define future behavior targets.

### T-CR2-001: Drift Alert via Chat

- **Input type**: text
- **Input**: `Motor 3 vibration seems high, can you check drift against baseline?`
- **Expected (future)**: Queries InfluxDB for vibration data, compares against stored baseline, reports drift in sigma units, references similar past events from vector DB
- **Current expected**: General vibration troubleshooting advice (no live data pipeline)
- **Validates (future)**: Cosmos Phase 3 drift detection, Phase 4 vector search

### T-CR2-002: Cross-Vendor Pattern Match

- **Input type**: text
- **Input**: `The Siemens S7 motor is showing the same vibration pattern we saw on the Allen-Bradley last month`
- **Expected (future)**: Searches vector DB for cross-vendor patterns, confirms similarity score, recommends resolution based on prior AB fix
- **Current expected**: Generic vibration troubleshooting (no cross-vendor matching)
- **Validates (future)**: Cosmos Phase 4 cross-vendor pattern learning

### T-CR2-003: Auto-Execute Request

- **Input type**: text
- **Input**: `Reduce motor 3 speed to 60% until the bearing is replaced`
- **Expected (future)**: Checks action whitelist, executes via Modbus write if approved, confirms action, logs to Workflow Tracker
- **Current expected**: Explains how to reduce motor speed manually via PLC program
- **Validates (future)**: Cosmos Phase 5 auto-execution engine

### T-CR2-004: Multi-Agent Orchestration

- **Input type**: photo + text
- **Input**: Photo of a smoking motor + `Motor 3 is smoking, what should I do?`
- **Expected (future)**: Triggers emergency workflow: photo analysis + fault diagnosis + doc search + alarm triage + report generation, all in parallel, response within 60 seconds
- **Current expected**: Photo analysis + safety-first advice (LOTO, de-energize, call supervisor)
- **Validates (future)**: Cosmos Phase 3 agent orchestration, Phase 1 Celery workers

### T-CR2-005: Daily Summary

- **Input type**: text
- **Input**: `Give me yesterday's summary`
- **Expected (future)**: Retrieves alerts processed, auto-resolved, manual interventions, drift events, token usage, top anomalies
- **Current expected**: Cannot provide (no data pipeline yet), should acknowledge the limitation
- **Validates (future)**: Cosmos Phase 5 health monitor, daily summary

---

## Results Log

| Test | Date | Result | Notes |
|------|------|--------|-------|
| T-001 | | | |
| T-002 | | | |
| T-003 | | | |
| T-004 | | | |
| T-005 | | | |
| T-006 | | | |
| T-007 | | | |
| T-008 | | | |
| T-009 | | | |
| T-010 | | | |
| T-011 | | | |
| T-012 | | | |
| T-013 | | | |
| T-014 | | | |
| T-015 | | | |
