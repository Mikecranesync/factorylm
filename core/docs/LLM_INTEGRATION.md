# LLM Integration Guide

## Using LLM Clients

### Basic Usage

```python
from factorylm import create_llm_client

# Create client with provider and API key
client = create_llm_client(
    provider="groq",
    api_key="your-api-key",
    model="mixtral-8x7b-32768"  # Optional
)

# Analyze machine state
response = client.analyze_machine_state(
    question="What's causing the high temperature?",
    machine_state={
        "motor_temp": 185,
        "ambient_temp": 72,
        "rpm": 1200,
        "status": "running"
    }
)

print(response.text)
```

### Chat Interface

```python
# Direct chat with messages
messages = [
    {"role": "system", "content": "You are an industrial diagnostics expert."},
    {"role": "user", "content": "What does error code E-501 mean?"}
]

response = client.chat(messages, temperature=0.3, max_tokens=500)
```

### Streaming Responses

```python
# Stream for real-time output
for chunk in client.stream_chat(messages):
    print(chunk, end="", flush=True)
```

## Supported Providers

### GROQ

Fast inference with open-source models.

```python
client = create_llm_client("groq", api_key)
```

**Available Models:**
- `mixtral-8x7b-32768` (default)
- `llama-3.1-70b-versatile`
- `llama-3.1-8b-instant`
- `llama3-70b-8192`
- `gemma2-9b-it`

**Pricing (per 1M tokens):**
| Model | Input | Output |
|-------|-------|--------|
| mixtral-8x7b | $0.24 | $0.24 |
| llama-3.1-70b | $0.59 | $0.79 |
| llama-3.1-8b | $0.05 | $0.08 |

### DeepSeek

Competitive pricing with strong reasoning.

```python
client = create_llm_client("deepseek", api_key)
```

**Available Models:**
- `deepseek-chat` (default)
- `deepseek-coder`
- `deepseek-reasoner`

**Pricing (per 1M tokens):**
| Model | Input | Output |
|-------|-------|--------|
| deepseek-chat | $0.14 | $0.28 |
| deepseek-coder | $0.14 | $0.28 |
| deepseek-reasoner | $0.55 | $2.19 |

### Claude (Anthropic)

Advanced reasoning and instruction following.

```python
client = create_llm_client("claude", api_key)
```

**Available Models:**
- `claude-3-sonnet-20240229` (default)
- `claude-3-opus-20240229`
- `claude-3-haiku-20240307`
- `claude-3-5-sonnet-20241022`

**Pricing (per 1M tokens):**
| Model | Input | Output |
|-------|-------|--------|
| claude-3-sonnet | $3.00 | $15.00 |
| claude-3-opus | $15.00 | $75.00 |
| claude-3-haiku | $0.25 | $1.25 |

## Adding a New Provider

To add a new LLM provider:

### 1. Create Client Class

```python
# src/factorylm/llm/newprovider_client.py

from factorylm.llm.base import BaseLLMClient, LLMResponse

class NewProviderClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str = None):
        self._api_key = api_key
        self._model = model or "default-model"
        # Initialize provider SDK

    def analyze_machine_state(self, question: str, machine_state: dict) -> LLMResponse:
        # Format prompt and call API
        pass

    def chat(self, messages: list, temperature: float = 0.7, max_tokens: int = 1024) -> LLMResponse:
        # Implement chat
        pass

    def get_model_name(self) -> str:
        return self._model

    def estimate_cost(self, response: LLMResponse) -> float:
        # Calculate cost based on token usage
        pass
```

### 2. Add to Factory

```python
# src/factorylm/llm/__init__.py

from factorylm.llm.newprovider_client import NewProviderClient

def create_llm_client(provider: str, api_key: str, model: str = None):
    providers = {
        "groq": GroqClient,
        "deepseek": DeepSeekClient,
        "claude": ClaudeClient,
        "newprovider": NewProviderClient,  # Add here
    }
    # ...
```

### 3. Add Tests

```python
# tests/unit/test_newprovider_client.py

def test_newprovider_initialization():
    client = NewProviderClient(api_key="key")
    assert client.get_model_name() == "default-model"
```

## Cost Tracking

Track API costs:

```python
# Single request cost
response = client.chat(messages)
cost = client.estimate_cost(response)
print(f"Cost: ${cost:.6f}")

# Track total session cost
total_cost = 0.0
for query in queries:
    response = client.chat([{"role": "user", "content": query}])
    total_cost += client.estimate_cost(response)

print(f"Total session cost: ${total_cost:.4f}")
```

## Error Handling

```python
from factorylm.llm.base import (
    LLMError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMConnectionError
)

try:
    response = client.chat(messages)
except LLMAuthenticationError:
    print("Invalid API key")
except LLMRateLimitError:
    print("Rate limit exceeded, please wait")
except LLMConnectionError:
    print("Failed to connect to provider")
except LLMError as e:
    print(f"LLM error: {e}")
```

## Best Practices

1. **Use Environment Variables**: Never hardcode API keys
2. **Handle Errors**: Always wrap calls in try/except
3. **Monitor Costs**: Use `estimate_cost()` to track spending
4. **Choose Appropriate Models**: Use smaller models for simple tasks
5. **Set Temperature Appropriately**: Lower (0.1-0.3) for factual, higher (0.7-1.0) for creative
