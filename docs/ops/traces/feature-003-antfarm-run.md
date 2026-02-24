# TRC-2026-02-24-F003: Feature 003 — LLM Router Service (Antfarm Run)

| Field | Value |
|-------|-------|
| **ID** | TRC-2026-02-24-F003 |
| **Date** | 2026-02-24 |
| **Author** | Claude (Jarvis-DevOps-Me) |
| **Duration** | ~20m |
| **Type** | feature-build |
| **Services** | llm-router, antfarm |
| **Devices** | Mac Mini (michaels-mac-mini) |
| **Trigger** | Feature 003 plan approved by Mike |

---

## Context

FactoryLM needed to maximize free-tier LLM inference by cycling across 6 providers (Cerebras, Groq, DeepSeek, 3x OpenRouter) with budget tracking, circuit breakers, and task-type routing. The router exposes an OpenAI-compatible `/v1/chat/completions` endpoint so any service can use it as a drop-in replacement.

## What Happened

### Phase A: Antfarm Infrastructure

1. Created branch `feature/llm-router` from `main`
2. Created builder workflow YAML with 4 agents: designer, dev, dev-ops, tester
3. Created 4 AGENTS.md files following Feature 002 pattern

### Phase B: Builder Execution

| Step | Agent | Result |
|------|-------|--------|
| `plan_providers` | designer | 6 providers validated with budget limits and routing tables. `STATUS: done` |
| `implement_service` | dev | Created 7 files + `__init__.py` under `services/llm-router/`. `STATUS: done` |
| `create_tests` | dev | Created `tests/test_llm_router.py` with 19 tests across 7 test classes. `STATUS: done` |
| `test_e2e` | tester | All 19 tests pass. `STATUS: done` |
| `deploy_launchd` | dev-ops | Plist created at `services/llm-router/com.factorylm.llm-router.plist`. Deployment pending. |
| `smoke_test` | tester | Pending live deployment with Doppler secrets. |

### Test Results

```
test_budget_daily_reset ... ok
test_budget_exhaustion ... ok
test_request_budget_type ... ok
test_circuit_opens_after_threshold ... ok
test_success_resets_failures ... ok
test_all_task_types_have_routes ... ok
test_model_to_provider_mapping ... ok
test_openrouter_providers_share_key ... ok
test_six_providers_configured ... ok
test_deepseek_model_resolves ... ok
test_groq_model_resolves ... ok
test_openrouter_r1_model_resolves ... ok
test_provider_name_as_model ... ok
test_response_schema ... ok
test_round_robin_cycles_providers ... ok
test_coding_routes_to_deepseek_cerebras ... ok
test_fast_routes_to_cerebras_or_groq ... ok
test_reasoning_routes_to_r1_deepseek_qwen3 ... ok
test_structured_routes_to_groq ... ok
----------------------------------------------------------------------
Ran 19 tests in 0.226s — OK
```

### 6 Providers Configured

| Name | Model | Daily Budget | Budget Type |
|------|-------|-------------|-------------|
| cerebras | gpt-oss-120b | 1,000,000 | tokens |
| groq | llama-3.3-70b-versatile | 14,400 | requests |
| deepseek | deepseek-chat | 400,000 | tokens |
| openrouter-r1 | deepseek/deepseek-r1-0528:free | 200 | requests |
| openrouter-qwen3 | qwen/qwen3-235b-a22b:free | 200 | requests |
| openrouter-maverick | meta-llama/llama-4-maverick:free | 200 | requests |

### Routing Logic

1. **Direct model** → specific provider (e.g. `deepseek-chat` → deepseek)
2. **Provider name** → that provider (e.g. `cerebras` → cerebras)
3. **prefer_provider** → try that first, fall back to others
4. **task_type** → fast=cerebras/groq, reasoning=r1/deepseek/qwen3, structured=groq, coding=deepseek/cerebras
5. **Round-robin** → cycle across all eligible providers

### Key Design Decisions

- **Standalone service** — no imports from openclaw package; budget + circuit breaker inlined
- **Each OpenRouter model = separate logical provider** — independent 200 req/day budgets
- **No streaming (v1)** — returns 501; add later if needed
- **In-memory budget state** — resets on restart (conservative, not restrictive)
- **Redis for logging only** — not for budget state
- **`--app-dir` for uvicorn** — directory `llm-router` uses hyphen (valid filesystem, not valid Python identifier); `uvicorn main:app --app-dir services/llm-router` handles this

## Changes Made

| File | Type | Purpose |
|------|------|---------|
| `antfarm/workflows/llm-router/workflow.yml` | new | 6-step builder workflow |
| `antfarm/workflows/llm-router/agents/designer/AGENTS.md` | new | Provider config validator agent |
| `antfarm/workflows/llm-router/agents/dev/AGENTS.md` | new | Service developer agent |
| `antfarm/workflows/llm-router/agents/dev-ops/AGENTS.md` | new | Deployment agent |
| `antfarm/workflows/llm-router/agents/tester/AGENTS.md` | new | E2E tester agent |
| `services/llm-router/__init__.py` | new | Package init |
| `services/llm-router/models.py` | new | Pydantic schemas (OpenAI-compatible) |
| `services/llm-router/config.py` | new | Provider configs + routing tables |
| `services/llm-router/providers.py` | new | UnifiedProvider (AsyncOpenAI wrapper) |
| `services/llm-router/router.py` | new | SmartRouter (budget + circuit breaker + routing) |
| `services/llm-router/redis_logger.py` | new | Redis telemetry logger |
| `services/llm-router/main.py` | new | FastAPI app (/v1/chat/completions, /health) |
| `services/llm-router/requirements.txt` | new | openai dependency |
| `services/llm-router/com.factorylm.llm-router.plist` | new | launchd plist for auto-restart |
| `tests/test_llm_router.py` | new | 19 unit tests (7 test classes) |
| `docs/ops/traces/feature-003-antfarm-run.md` | new | This trace |

## Deployment (Pending)

To deploy:

```bash
# 1. Create log directory
mkdir -p /tmp/llm-router

# 2. Install plist
cp services/llm-router/com.factorylm.llm-router.plist ~/Library/LaunchAgents/

# 3. Load service
launchctl load ~/Library/LaunchAgents/com.factorylm.llm-router.plist

# 4. Verify
curl -s localhost:7100/health | jq .

# 5. Test OpenAI compatibility
python3 -c "
from openai import OpenAI
c = OpenAI(base_url='http://localhost:7100/v1', api_key='x')
r = c.chat.completions.create(model='auto', messages=[{'role':'user','content':'hi'}])
print(r.choices[0].message.content)
"
```

## Outcome

Feature 003 code complete. 16 files created on `feature/llm-router` branch. All 19 tests pass. Ready for PR + live deployment with Doppler secrets.

## Queryable Tags

- **feature**: Feature-003, LLM-router, free-tier, budget-tracking
- **providers**: cerebras, groq, deepseek, openrouter-r1, openrouter-qwen3, openrouter-maverick
- **config-keys**: CEREBRAS_API_KEY, GROQ_API_KEY, DEEPSEEK_API_KEY, OPENROUTER_API_KEY
- **port**: 7100
- **dependencies**: openai, fastapi, redis, pydantic

## Related

- **Workflow**: `antfarm/workflows/llm-router/workflow.yml`
- **Feature 002**: `antfarm/workflows/cmms-gist-work-order/workflow.yml`
- **VPS Router Pattern**: `output/vps-patches/router.py` (circuit breaker source)
- **Branch**: `feature/llm-router`
