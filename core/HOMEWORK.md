# FactoryLM Research Findings (HOMEWORK)

## LLM Provider SDK Research

### GROQ SDK
- **Package**: `groq` (official)
- **API Style**: OpenAI-compatible
- **Key Features**:
  - Extremely fast inference (100+ tokens/sec)
  - Streaming support
  - Usage tracking in response
  - Simple error handling
- **Rate Limits**: 30 requests/minute (free tier)
- **Best For**: High-volume, latency-sensitive applications

### DeepSeek SDK
- **Package**: `openai` (OpenAI-compatible API)
- **Base URL**: `https://api.deepseek.com`
- **Key Features**:
  - Standard OpenAI interface
  - Competitive pricing
  - Strong reasoning capabilities
  - Code-focused models available
- **Best For**: Cost-effective general use

### Anthropic SDK
- **Package**: `anthropic` (official)
- **Key Features**:
  - Different message format (no system in messages array)
  - Streaming via context manager
  - Content blocks in response
  - Detailed usage tracking
- **Best For**: Complex reasoning, instruction following

## Python Project Structure Best Practices

### src/ Layout
Chosen the `src/` layout for:
- Clear separation of source and tests
- Prevents accidental imports of uninstalled package
- Standard for pip-installable packages

### Package Structure
```
src/
└── factorylm/
    ├── __init__.py      # Public API exports
    ├── config.py        # Centralized configuration
    ├── llm/            # Provider implementations
    └── utils/          # Shared utilities
```

## Abstract Base Classes Pattern

### Benefits
1. **Type Safety**: IDE autocomplete and type checking
2. **Contract Enforcement**: Can't instantiate without implementing all methods
3. **Documentation**: Interface defines expected behavior
4. **Testing**: Easy to mock for unit tests

### Implementation
```python
from abc import ABC, abstractmethod

class BaseLLMClient(ABC):
    @abstractmethod
    def method(self): pass
```

## Factory Pattern Research

### Simple Factory
Chosen for simplicity:
```python
def create_llm_client(provider: str, api_key: str) -> BaseLLMClient:
    providers = {"groq": GroqClient, ...}
    return providers[provider](api_key)
```

### Benefits
- Single point of client creation
- Easy to add new providers
- Encapsulates instantiation logic
- Enables provider switching via config

## Error Handling Strategy

### Custom Exception Hierarchy
```
LLMError (base)
├── LLMConnectionError
├── LLMAuthenticationError
├── LLMRateLimitError
└── LLMInvalidRequestError
```

### Rationale
- Maps to common API error patterns
- Preserves original exceptions
- Enables specific error handling
- Provider-agnostic error types

## Configuration Management

### Environment Variables
Using `python-dotenv` for:
- `.env` file support
- No code changes for different environments
- Secure (excluded from git)
- Standard practice

### Key Configuration Points
- `LLM_PROVIDER`: Active provider
- `LLM_API_KEY`: Authentication
- `LLM_MODEL`: Model selection
- `LOG_LEVEL`: Verbosity

## Testing Strategy

### Unit Tests
- Mock external APIs
- Test business logic in isolation
- Fast execution
- 80%+ coverage target

### Integration Tests
- Test provider switching
- Verify interface compliance
- Use fixtures for consistency

## Cost Tracking Research

### Pricing Sources
- GROQ: https://console.groq.com/docs/rate-limits
- DeepSeek: https://platform.deepseek.com/pricing
- Anthropic: https://www.anthropic.com/pricing

### Implementation
Per-provider pricing dictionaries with input/output rates per 1M tokens.
