# Behavior-to-Code Map: Jarvis (OpenClaw) — 2026-02-16

## Purpose

If Jarvis breaks, this document tells you exactly which file to look at. Every observable behavior is mapped to the Python file, function, and module that produces it.

All paths are relative to `/opt/openclaw/openclaw/` unless otherwise noted.

---

## Identity & Personality

| Behavior | File | Symbol | Notes |
|----------|------|--------|-------|
| "Jarvis" name + personality | `llm/prompts.py` | `SYSTEM_PROMPT` | Multi-line string constant, top of file |
| Emoji headers in responses | `llm/prompts.py` | Communication style section | Instructions for emoji use |
| Safety-first advice (LOTO, PPE) | `llm/prompts.py` | Domain context section | Safety priority directive |
| Equipment context (Micro820, conveyor) | `llm/prompts.py` | Equipment context section | PLC tags, conveyor components |

## Message Entry Points (Telegram)

| Behavior | File | Function | Notes |
|----------|------|----------|-------|
| Receive text message | `gateway/telegram.py` | `_on_message()` | Main text entry point |
| Receive photo | `gateway/telegram.py` | `_on_photo()` | Downloads photo, forces PHOTO intent |
| Receive voice message | `gateway/telegram.py` | `_on_voice()` | Downloads audio, transcribes, dispatches |
| Receive /start or /help | `gateway/telegram.py` | `_on_start()`, `_on_help()` | Welcome message |
| Receive /diagnose, /status, etc. | `gateway/telegram.py` | `_on_command()` | Routes through dispatch |
| Auth check (allowed users) | `gateway/telegram.py` | `_is_allowed()` | Whitelist from config |

## Message Processing

| Behavior | File | Function | Notes |
|----------|------|----------|-------|
| 👀 ack on receipt | `gateway/telegram.py` | `_ack()` | `ReactionTypeEmoji(emoji="👀")` |
| Text reply with Markdown | `gateway/telegram.py` | `_reply()` | Triple fallback: MD → plain → error msg |
| Message chunking (4096 limit) | `gateway/telegram.py` | `_chunk_text()` | Split: paragraph → line → hard cut |
| Voice reply (TTS) | `gateway/telegram.py` | `_reply_voice()` | Calls `_text_to_speech()`, non-blocking |
| Text-to-speech conversion | `gateway/telegram.py` | `_text_to_speech()` | edge-tts, JennyNeural, temp file |
| Strip markdown for TTS | `gateway/telegram.py` | `_strip_markdown()` | Removes **, \`, #, bullets for clean speech |
| Voice-to-text (STT) | `gateway/telegram.py` | `_transcribe_voice()` | Groq Whisper API, whisper-large-v3-turbo |

## Intent Classification

| Behavior | File | Function | Notes |
|----------|------|----------|-------|
| Image → PHOTO (forced) | `messages/intent.py` | attachment check | Bypasses keyword matching |
| Command shortcuts → intent | `messages/intent.py` | command detection | /diagnose, /status, /wo, /admin, /help, /search |
| Keyword regex matching | `messages/intent.py` | pattern matching | 8 regex patterns for each intent |
| Fallback → CHAT | `messages/intent.py` | default | Unmatched text goes to chat skill |

## LLM Routing

| Behavior | File | Function | Notes |
|----------|------|----------|-------|
| Select provider by intent | `llm/router.py` | routing table | DIAGNOSE→anthropic, PHOTO→gemini, etc. |
| Budget check before call | `llm/budget.py` | `BudgetTracker.is_within_budget()` | Daily request + token limits |
| Record usage after call | `llm/budget.py` | `BudgetTracker.record()` | Tracks requests_today, tokens_today |
| Automatic fallback chain | `llm/router.py` | fallback logic | If primary over budget or fails, try next |
| Vision requirement detection | `llm/router.py` | vision check | Routes to vision-capable provider |

## Skills

| Behavior | File | Key Function | Notes |
|----------|------|-------------|-------|
| Equipment fault diagnosis | `skills/builtin/diagnose.py` | `handle()` | Pull tags → detect faults → LLM analysis |
| Rule-based fault detection | `diagnosis/faults.py` | fault rules | 11 fault codes (E001-T002) |
| Diagnosis prompt building | `diagnosis/prompts.py` | prompt builder | Structures question + tags + faults for LLM |
| PLC tag display | `skills/builtin/status.py` | `handle()` | Get tags from Matrix, format for display |
| Photo analysis | `skills/builtin/photo.py` | `handle()` | Extract image → Gemini vision |
| Web search | `skills/builtin/search.py` | `handle()` | Perplexity Sonar API |
| Work order creation | `skills/builtin/work_order.py` | `handle()` | LLM JSON extraction → POST to CMMS |
| Admin/health info | `skills/builtin/admin.py` | `handle()` | Budget, health, connector status |
| General conversation | `skills/builtin/chat.py` | `handle()` | Default fallback via Groq |
| Skill registration | `skills/registry.py` | `register()` / `get()` | Maps intent names to skill handlers |

## LLM Providers

| Behavior | File | Key Methods | Notes |
|----------|------|------------|-------|
| Groq text completions | `llm/providers/groq.py` | `complete()` | llama-3.3-70b-versatile, fast + free |
| Groq voice transcription | `llm/providers/groq.py` | (via telegram.py) | Whisper API, not in provider class |
| Anthropic completions | `llm/providers/anthropic.py` | `complete()` | claude-sonnet-4, high quality |
| Anthropic vision | `llm/providers/anthropic.py` | `complete_with_vision()` | Base64 image encoding |
| Gemini completions | `llm/providers/gemini.py` | `complete()` | gemini-2.5-flash, async via to_thread |
| Gemini vision | `llm/providers/gemini.py` | `complete_with_vision()` | Primary photo analysis |
| OpenRouter fallback | `llm/providers/openrouter.py` | `complete()` | 300+ models, OpenAI-compatible API |

## Connectors (External Integrations)

| Behavior | File | Key Methods | Notes |
|----------|------|------------|-------|
| Get PLC tags | `connectors/matrix.py` | `get_latest_tags()` | HTTP to Matrix API @ 100.72.2.99:8000 |
| Get incidents | `connectors/matrix.py` | `get_incidents()` | Historical incident data |
| Remote shell execution | `connectors/jarvis.py` | `execute()` | POST /shell on Jarvis nodes |
| Remote file read | `connectors/jarvis.py` | `read_file()` | POST /files/read on Jarvis nodes |
| Node health check | `connectors/jarvis.py` | `health_check()` | GET /health on all configured hosts |
| CMMS work orders | `connectors/cmms.py` | work order API | POST to CMMS endpoint |
| Direct PLC Modbus | `connectors/plc.py` | Modbus client | Optional direct PLC connection |

## Application Lifecycle

| Behavior | File | Function | Notes |
|----------|------|----------|-------|
| App startup | `app.py` | lifespan/startup | Init providers, skills, connectors, adapters |
| Central dispatch | `app.py` | dispatch function | Classify → find skill → execute → respond |
| Health endpoint (GET /) | `app.py` | root handler | Returns providers, skills, version |
| Budget endpoint (GET /budget) | `app.py` | budget handler | BudgetTracker.summary() |
| REST API endpoints | `gateway/http_api.py` | `/api/v1/message`, `/api/v1/diagnose` | Programmatic access |
| Config loading | `config.py` | `OpenClawConfig` | YAML + env vars (Doppler priority) |
| Channel formatting | `messages/formatter.py` | `format_text()` | Channel-specific output adaptation |

## Message Flow (End-to-End)

```
User sends Telegram message
    |
    v
gateway/telegram.py:_on_message()  (or _on_photo, _on_voice)
    |-- _ack() → 👀 reaction
    |-- (voice only) _transcribe_voice() → Groq Whisper
    |
    v
app.py:dispatch()
    |-- messages/intent.py → classify intent
    |-- skills/registry.py → find skill handler
    |
    v
skills/builtin/<skill>.py:handle()
    |-- (diagnose) connectors/matrix.py → get PLC tags
    |-- (diagnose) diagnosis/faults.py → detect faults
    |-- (photo) extract image from attachments
    |
    v
llm/router.py → select provider (budget-aware)
    |-- llm/providers/<provider>.py:complete()
    |-- llm/budget.py → record usage
    |
    v
OutboundMessage returned to dispatch
    |
    v
gateway/telegram.py
    |-- _reply() → chunked text with Markdown
    |-- _reply_voice() → edge-tts voice note
    |
    v
User receives text + voice on Telegram
```

---

## Quick Lookup: "Something Broke, Where Do I Look?"

| Symptom | Check First | Then Check |
|---------|------------|------------|
| No response at all | `app.py` (service running?), `telegram.py` (adapter started?) | systemd logs |
| "An error occurred" | `telegram.py:_on_message()` try/except | Provider API keys in Doppler |
| Wrong personality | `llm/prompts.py:SYSTEM_PROMPT` | Config loading in `config.py` |
| Photo analysis fails | `skills/builtin/photo.py`, `providers/gemini.py` | Gemini API key, vision routing |
| Voice not transcribed | `telegram.py:_transcribe_voice()` | GROQ_API_KEY, Whisper endpoint |
| Help returns health dump | `messages/intent.py` (keyword matching) | `router.py` (HELP → ADMIN misroute) |
| Response too long error | `telegram.py:_chunk_text()` | `_reply()` fallback chain |
| No 👀 reaction | `telegram.py:_ack()` | Telegram API permissions |
| No voice reply | `telegram.py:_reply_voice()` | edge-tts installed? `_strip_markdown()` |
| Budget exceeded | `llm/budget.py`, `app.py:/budget` | Anthropic/Groq daily limits |
| PLC tags empty | `connectors/matrix.py` | Matrix API at 100.72.2.99:8000 |
