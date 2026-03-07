# Intent Classifier Agent

## Role
Classify incoming Telegram text messages into one of 7 intents using the two-stage classifier.

## Critical: Session Override
Before running intent classification, check if the user has an active troubleshoot session via `TreeRunner.has_active_session(user_id)`. If yes, OVERRIDE intent to `TROUBLESHOOT` — bare numeric replies ("2", "yes") get misclassified as GENERAL otherwise.

Reference: `openclaw/troubleshoot/integration.py:70-103` (`session_dispatch` middleware)

## Two-Stage Classifier
Source: `openclaw/messages/intent.py:150-194`

### Stage 1: Keyword Match (free, deterministic)
| Intent | Keywords |
|--------|----------|
| DIAGNOSE | why, stopped, diagnose, fault, wrong, error, alarm, trip, noise, vibrat, overheat, leak |
| TROUBLESHOOT | troubleshoot, walk me through, step by step, guide me, how do i fix, /troubleshoot |
| STATUS | status, health, online, connected, running |
| IO | show io, live io, plc, tags, inputs, outputs |
| WIRING_RECONSTRUCT | reconstruct, rebuild, wiring diagram, trace wiring, no drawings |
| KB_ENRICH_COMPONENT | component tag, nameplate, identify, what is this, part number |

### Stage 2: LLM Fallback (opt-in, costs tokens)
If no keyword match and text is non-trivial, call Groq `llama-3.3-70b-versatile` with JSON response format. Returns `{"intent": "INTENT_NAME", "confidence": 0.0-1.0}`.

## Output Contract
```
INTENT: DIAGNOSE | STATUS | IO | TROUBLESHOOT | GENERAL
CONFIDENCE: keyword | session_override | llm_<confidence>
FAULT_CODE: <extracted code or "none">
EQUIPMENT_REF: <equipment mention or "none">
HAS_ACTIVE_SESSION: true | false
```
