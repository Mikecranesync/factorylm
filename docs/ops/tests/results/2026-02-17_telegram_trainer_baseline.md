# Telegram Trainer Baseline — 2026-02-17

| Field | Value |
|-------|-------|
| **Date** | 2026-02-17 10:34 UTC |
| **Branch** | fix/estop-incident-creation (merged to main via PR #49) |
| **VPS** | OpenClaw v1.0.0 @ 100.68.120.99:8340 |
| **Providers** | groq, nvidia, anthropic, gemini |
| **Skills** | 12 (diagnose, status, photo, work_order, admin, search, shell, diagram, chat, gist, project, wiring_enrich) |
| **Result** | **9/9 PASS** |

## Results

| ID | Name | Type | Result | Intent | Latency |
|----|------|------|--------|--------|---------|
| T-001 | Greeting | chat | PASS | chat | 478ms |
| T-002 | Self-Description | chat | PASS | chat | 1012ms |
| T-003 | Show IO | chat | PASS | chat | 1122ms |
| T-004 | Electrical Safety | chat | PASS | diagram | 1751ms |
| T-005 | Build Assistance | chat | PASS | chat | 755ms |
| T-010 | Help Routing | chat | PASS | help | 35ms |
| T-013 | Long Response Chunking | chat | PASS | chat | 2209ms |
| T-014 | Metrics Endpoint | http | PASS | http_get | 27ms |
| T-015 | Health Endpoint | http | PASS | http_get | 27ms |

## Response Samples

### T-001: Greeting
> "Hello Mike. What's on the agenda for the NVIDIA Cosmos Cookoff project? Need help with Cosmos R2 integration or PLC tag analysis?"

### T-002: Self-Description
> "I'm Jarvis, the AI development partner at FactoryLM, created by Mike Harper. I'm designed to assist with AI-powered factory diagnostics, focusing on PLC tag analysis, fault detection, and Cosmos R2 integration."

### T-003: Show IO
> "I/O Status — Motor: Running (50 Hz), Photoeye Sensors: Sensor 1 Tripped, Sensor 2 Not Tripped, Pneumatics: Cylinder 1 Extended, Cylinder 2 Retracted, Temperature: 25C, Pressure: 80 psi"

### T-004: Electrical Safety
> Routed to DIAGRAM intent. Generated a wiring diagram (CB1 → PLC1, 240V 20A power feed). Note: expanded DIAGRAM patterns catch "220V feed" as wiring language.

### T-010: Help
> Returns OpenClaw Health + LLM Provider status. Note: returns health dump, not human-readable capabilities list (known issue from T-010 baseline).

## Intent Observations

| Input | Expected Intent | Actual Intent | Notes |
|-------|----------------|---------------|-------|
| "hello" | chat | chat | Correct |
| "show me io" | status | chat | Misclassified via HTTP API — works via Telegram |
| "220V feed..." | diagnose | diagram | Expanded DIAGRAM patterns catch electrical language |
| "help" | help | help | Correct, but response is health dump not capabilities |

## Improvement Candidates

1. **T-003 intent**: "show me io" → should route to `status` skill, not `chat`. Fix in `intent.py` STATUS patterns.
2. **T-004 safety**: 220V questions should get safety preamble before diagram. Fix in `diagram` skill or `prompts.py`.
3. **T-010 help response**: Returns health dump instead of human-readable capabilities list. Fix in `help` skill handler.
4. **Feature 001**: `wiring_enrich` skill registered and functional. KB connector healthy.

## Skipped Tests (Telegram-native)

| ID | Reason |
|----|--------|
| T-006 | Photo + caption (requires Telegram photo upload) |
| T-007 | Photo no caption (requires Telegram photo upload) |
| T-008 | Voice STT (requires audio) |
| T-009 | Voice factory query (requires audio) |
| T-011 | Emoji ack (requires Telegram reaction check) |
| T-012 | TTS voice note (requires audio playback check) |
