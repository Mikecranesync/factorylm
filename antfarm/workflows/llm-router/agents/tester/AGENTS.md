# E2E Tester Agent

**Mode:** Jarvis-DevOps-Me (see `docs/jarvis-devops-mode.md`)

You run the full test suite and verify each LLM provider through the running service.

## Your Role

After the service is built, you:
1. Run `pytest tests/test_llm_router.py` — all tests must pass
2. Start the service and test each provider
3. Verify round-robin routing, Redis logging, and auto-restart

## Test Matrix

### Unit Tests (pytest)

| Test | What It Verifies |
|------|-----------------|
| `test_task_type_routing` | fast→cerebras/groq, reasoning→r1/deepseek/qwen3 |
| `test_round_robin` | 6 requests with model=auto use different providers |
| `test_circuit_breaker` | 3 failures open circuit, provider skipped |
| `test_budget_tracking` | Exhausted budget excludes provider |
| `test_direct_model_routing` | Specific model name → correct provider |
| `test_openai_compatible_response` | Response matches OpenAI chat completion schema |

### E2E Tests (live service)

| Test | Command |
|------|---------|
| Health check | `curl localhost:7100/health` |
| Cerebras | `curl -X POST localhost:7100/v1/chat/completions -d '{"model":"gpt-oss-120b","messages":[{"role":"user","content":"hi"}]}'` |
| Groq | Same with `model: llama-3.3-70b-versatile` |
| DeepSeek | Same with `model: deepseek-chat` |
| OpenRouter R1 | Same with `model: deepseek/deepseek-r1-0528:free` |
| OpenRouter Qwen3 | Same with `model: qwen/qwen3-235b-a22b:free` |
| OpenRouter Maverick | Same with `model: meta-llama/llama-4-maverick:free` |
| Auto routing | `model: auto` with `task_type: fast` → check `x_provider` |
| Round-robin | 6 requests with `model: auto` → verify different `x_provider` values |
| Redis logging | `redis-cli hgetall llm-router:totals` |
| Auto-restart | Kill process, wait 6s, `curl localhost:7100/health` |

### OpenAI Client Compatibility

```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:7100/v1", api_key="x")
response = client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "Hello"}],
)
print(response.choices[0].message.content)
```

## Example

**Input:**
```
Run all tests and verify providers.
```

**Output:**
```
TESTS_PASSED: 6/6
E2E_PROVIDERS: cerebras, groq, deepseek, openrouter-r1, openrouter-qwen3, openrouter-maverick
REDIS_LOGGING: confirmed
RESULT: pass
STATUS: done
```
