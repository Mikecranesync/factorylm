# FactoryLM Diagnosis Service

FastAPI service that bridges **Telegram / Jarvis → PLC → LLM → Response**.

Accepts natural-language questions about factory/PLC state, reads live data from the PLC laptop via the Jarvis Node API, sends the context to a Groq-hosted LLM, and returns an actionable diagnosis.

## Run

```bash
uvicorn main:app --host 0.0.0.0 --port 8200
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PLC_LAPTOP_URL` | `http://100.72.2.99:8765` | Jarvis Node URL on the PLC laptop |
| `GROQ_API_KEY` | *(none)* | Groq API key for LLM inference |
| `GROQ_MODEL` | `llama-3.1-70b-versatile` | Model to use for diagnosis |

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Service info |
| GET | `/health` | Health check |
| GET | `/network` | Laptop connectivity status |
| POST | `/diagnose` | Submit a question for AI diagnosis |

## Related Files

- `factorylm_skill.js` — OpenClaw/Clawdbot skill that routes factory questions to this service
- `INTEGRATION.md` — Integration guide for connecting Clawdbot to this service
