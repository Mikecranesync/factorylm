# Service Developer Agent

**Mode:** Jarvis-DevOps-Me (see `docs/jarvis-devops-mode.md`)

You implement the FastAPI LLM router service as 7 standalone files.

## Your Role

You create a fully standalone service at `services/llm-router/` with no import dependencies on the `openclaw` package. Budget tracking and circuit breaker logic are inlined. The service exposes an OpenAI-compatible `/v1/chat/completions` endpoint.

## Files to Create (7)

### 1. `models.py` (~50 lines)
- `TaskType` enum: fast, reasoning, structured, coding
- `ChatMessage`: role + content
- `ChatRequest`: Pydantic model matching OpenAI chat completion request
  - model: str (provider name, model name, or "auto")
  - messages: list[ChatMessage]
  - Optional: temperature, max_tokens, task_type, prefer_provider
- `ChatChoice`, `ChatUsage`, `ChatResponse`: OpenAI-compatible response schema

### 2. `config.py` (~60 lines)
- `ProviderConfig` dataclass: name, base_url, model, api_key_env, daily_budget, budget_type (tokens|requests)
- `PROVIDERS`: dict of 6 ProviderConfig instances
- `MODEL_TO_PROVIDER`: reverse mapping from model name → provider name
- Load API keys from environment (Doppler injects them)

### 3. `providers.py` (~50 lines)
- `UnifiedProvider` class wrapping `AsyncOpenAI(base_url=...)`
- Single `complete(messages, model, temperature, max_tokens)` method
- OpenRouter-specific: HTTP-Referer and X-Title headers
- Returns (content, usage_dict)

### 4. `router.py` (~150 lines)
- `ProviderBudget` dataclass (inlined): daily_limit, used, budget_type, reset_date
- `ProviderHealth` dataclass (inlined): consecutive_failures, circuit_open_until
- `SmartRouter` class:
  - `route(request) -> (provider_name, response)` — main routing method
  - Resolution order: direct model → prefer_provider → task_type → round-robin
  - Circuit breaker: 3 strikes → 300s cooldown
  - Budget check before each attempt

### 5. `redis_logger.py` (~70 lines)
- `RedisLogger` class using `redis.asyncio`
- `log_request(provider, model, tokens, latency_ms, task_type)`
- Keys: `llm-router:daily:{date}:{provider}`, `llm-router:totals`, `llm-router:latency`
- Uses HINCRBY for counters, ZADD for sorted sets

### 6. `main.py` (~90 lines)
- FastAPI app on port 7100
- `POST /v1/chat/completions` — route and return OpenAI-compatible response
- `GET /health` — all providers with budget status
- `GET /health/stats` — Redis-backed usage statistics
- Response includes `x_provider` field showing which provider handled the request

### 7. `requirements.txt` (~5 lines)
- `openai` — the only new dependency (FastAPI, Redis, Pydantic already installed)

## Design Constraints

- **Standalone**: no imports from `openclaw` — inline everything
- **No streaming**: return 501 for stream=true
- **In-memory budgets**: reset on restart (conservative approach)
- **Redis for logging only**: not for budget state

## Example

**Input:**
```
Create the 7 service files.
```

**Output:**
```
FILES_CREATED: 7
PROVIDERS: cerebras, groq, deepseek, openrouter-r1, openrouter-qwen3, openrouter-maverick
ENDPOINTS: /v1/chat/completions, /health, /health/stats
RESULT: pass
STATUS: done
```
