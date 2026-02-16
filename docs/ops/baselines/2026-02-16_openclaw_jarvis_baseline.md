# Baseline: OpenClaw Jarvis — 2026-02-16

| Field | Value |
|-------|-------|
| **Service** | openclaw |
| **Version** | feat/tts-emoji-ack @ `85949ac` (main @ `8dce07d`) |
| **Date** | 2026-02-16 |
| **Author** | Claude Code (Travel Laptop) |
| **Status** | verified-in-production |

This is the version restored after the Feb 16 debugging marathon and Jarvis soul restore. Node.js Clawdbot was replaced with Python OpenClaw. Identity, routing, voice STT, TTS, emoji ack, and rich formatting were restored or added.

---

## Identity

- **Name**: Jarvis (OpenClaw)
- **Bot handle**: @FACTORYLM_bot (MikesOPENCLAW) on Telegram
- **Personality**: Direct, confident, slightly witty. Safety-first for electrical/industrial work.
- **Voice**: en-US-JennyNeural (Edge TTS)
- **Communication style**: Emoji headers, bold key terms, `code` backticks for tags, bullet points, status emojis
- **No SOUL.md or MEMORY.md** — identity lives entirely in `prompts.py:SYSTEM_PROMPT`

## Infrastructure

| Component | Value |
|-----------|-------|
| **Host** | VPS (100.68.120.99, factorylm-prod) |
| **Port** | 8340 |
| **Service manager** | systemd via Doppler (`systemctl status openclaw`) |
| **Python** | 3.12+ with venv at `/opt/openclaw/.venv` |
| **Codebase** | `/opt/openclaw/` (GitHub: Mikecranesync/openclaw) |
| **Branch** | `feat/tts-emoji-ack` (1 commit ahead of main) |
| **Process** | Uvicorn via `python -m openclaw` |

## LLM Providers

| Provider | Model | Used For | Daily Budget |
|----------|-------|----------|--------------|
| Groq | llama-3.3-70b-versatile | chat, status, admin, search, diagnose fallback | 14,000 req |
| Anthropic | claude-sonnet-4-20250514 | diagnose (primary), work_order | 100 req, 100K tokens |
| Gemini | gemini-2.5-flash | photo analysis (vision) | per-request |
| OpenRouter | anthropic/claude-sonnet-4 | last-resort fallback | 500 req, 500K tokens |
| OpenAI | gpt-4o | configured but not primary | per-request |
| NVIDIA | cosmos | configured but not primary | per-request |

## Routing Table

| Intent | Primary Provider | Fallback(s) |
|--------|-----------------|-------------|
| DIAGNOSE | anthropic | groq, gemini |
| PHOTO | gemini | anthropic |
| WORK_ORDER | anthropic | groq |
| STATUS | groq | — |
| CHAT | groq | — |
| SEARCH | groq | — |
| ADMIN | groq | — |
| HELP | groq | — |
| UNKNOWN | groq | — |

## Skills

| Skill | Intent(s) | Description |
|-------|-----------|-------------|
| diagnose | DIAGNOSE | Equipment fault diagnosis using PLC tags + LLM |
| status | STATUS | Current PLC tag values display |
| photo | PHOTO | Equipment photo analysis via Gemini vision |
| work_order | WORK_ORDER | CMMS work order creation |
| admin | ADMIN, HELP | Health status, budget info, connector status |
| search | SEARCH | Web search via Perplexity Sonar |
| chat | CHAT, UNKNOWN | General conversation fallback |

## Telegram Behaviors

| Behavior | Status | Implementation |
|----------|--------|----------------|
| 👀 ack on receipt | active | `_ack()` fires `ReactionTypeEmoji("👀")` |
| Text reply + Markdown | active | `_reply()` with triple fallback (MD → plain → error) |
| Message chunking | active | `_chunk_text()` splits at 4096 chars (paragraph → line → hard) |
| TTS voice reply | active | `_reply_voice()` via edge-tts, JennyNeural, skip < 20 chars |
| Voice STT | active | `_transcribe_voice()` via Groq Whisper (whisper-large-v3-turbo) |
| Photo analysis | active | `_on_photo()` → forced PHOTO intent → Gemini |
| Auth whitelist | active | `allowed_users` config (user 8445149012 = Mike) |

## Intent Classification

Rule-based keyword matching in `messages/intent.py`:

1. **Image attachment** → PHOTO (forced, bypasses keywords)
2. **Command shortcuts**: `/diagnose`, `/status`, `/wo`, `/admin`, `/help`, `/search`
3. **Keyword patterns** (regex):
   - `why|stopped|fault|error|alarm|broken|down|diagnos` → DIAGNOSE
   - `status|tags|reading|current|temp|pressure|running` → STATUS
   - `work order|wo|maintenance|repair|schedule` → WORK_ORDER
   - `health|budget|admin|restart|config` → ADMIN
   - `help|commands|menu|what can you` → HELP
   - `search|look up|find|google|web search` → SEARCH
4. **Fallback** → CHAT

## Fault Detection

Rule-based fault codes in `diagnosis/faults.py`:

| Code | Severity | Description |
|------|----------|-------------|
| E001 | EMERGENCY | Emergency stop active |
| M001 | CRITICAL | Motor overcurrent (>5A) |
| M002 | CRITICAL | Motor stopped unexpectedly |
| M003 | WARNING | Motor speed mismatch |
| T001 | CRITICAL | High temperature (>80C) |
| T002 | WARNING | Elevated temperature (65-80C) |
| C001 | CRITICAL | Conveyor jam (both sensors active) |
| P001 | WARNING | Low pneumatic pressure (<60 PSI) |
| PLC### | CRITICAL | PLC fault with error code |
| OK | INFO | System running normally |
| IDLE | INFO | System idle |

Each fault includes: severity, title, description, likely causes (2-3), suggested checks (3-4), affected tag names, and flags (requires_maintenance, requires_safety_review).

## Connectors

| Connector | URL | Purpose |
|-----------|-----|---------|
| Matrix API | http://100.72.2.99:8000 | PLC tag ingestion, incident tracking |
| Jarvis (PLC laptop) | http://100.72.2.99:8765 | Shell execution, file read on PLC machine |
| Jarvis (Travel laptop) | http://100.83.251.23:8765 | Shell execution, file read on dev machine |
| CMMS | configurable | Work order creation API |
| PLC (direct) | Modbus | Direct PLC connection (optional) |

## Configuration (openclaw.yaml)

```yaml
openclaw:
  port: 8340
  log_level: "INFO"
  telegram_enabled: true
  telegram_rate_limit_per_hour: 60
  default_llm_provider: "groq"
  groq_model: "llama-3.3-70b-versatile"
  groq_daily_request_limit: 14000
  anthropic_model: "claude-sonnet-4-20250514"
  anthropic_daily_request_limit: 100
  anthropic_daily_token_limit: 100000
  gemini_model: "gemini-2.5-flash"
  matrix_url: "http://100.72.2.99:8000"
  jarvis_hosts:
    plc_laptop: "http://100.72.2.99:8765"
    travel_laptop: "http://100.83.251.23:8765"
```

## Dependencies (from pyproject.toml)

**Core**: fastapi, uvicorn, httpx, pydantic, pydantic-settings, pyyaml
**LLM**: groq, anthropic, openai, google-generativeai
**Channels**: python-telegram-bot, edge-tts
**Observability**: structlog
**Optional**: pymodbus (PLC), pytest + ruff (dev)

## Git State

| Field | Value |
|-------|-------|
| **Active branch** | `feat/tts-emoji-ack` |
| **Commit** | `85949ac` — feat(telegram): add TTS voice replies + emoji ack + rich formatting |
| **Parent** | `8dce07d` — feat: Restore Jarvis identity, routing, voice STT, and message chunking |
| **Main branch** | `8dce07d` (1 commit behind active branch) |
| **Remote** | origin/feat/tts-emoji-ack pushed |

## Known Issues at Baseline Time

1. `feat/tts-emoji-ack` not yet merged to main (PR pending)
2. No automated test suite — all testing is manual via Telegram
3. Gemini photo analysis can fail if API key is exhausted or rate-limited
4. Anthropic provider only activates if `ANTHROPIC_API_KEY` is set in Doppler
5. Matrix connector returns empty if PLC laptop is offline (graceful degradation)
6. No persistent memory/context between Telegram messages (stateless)

## Related

- **Config Snapshot**: [2026-02-16_openclaw.yaml](../config-snapshots/2026-02-16_openclaw.yaml)
- **Behavior Map**: [2026-02-16_jarvis_behavior_to_code.md](./2026-02-16_jarvis_behavior_to_code.md)
- **Test Cases**: [TESTS_jarvis_baseline.md](../tests/TESTS_jarvis_baseline.md)
- **Health Check**: [WF-007](../workflows/check-jarvis-baseline.md)
- **Traces**: [jarvis-soul-restore](../traces/2026-02-16_jarvis-soul-restore.md), [tts-emoji-ack](../traces/2026-02-16_tts-emoji-ack.md)
- **Resurrection Repo**: github.com/Mikecranesync/JARVIS-IS-DEAD
