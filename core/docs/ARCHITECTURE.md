# FactoryLM Architecture

## Overview

FactoryLM Core provides an abstraction layer for LLM providers, enabling industrial applications to leverage AI for machine diagnostics without vendor lock-in.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Application Layer                            │
│   (Voice HMI, Web Dashboard, PLC Client, Custom Applications)   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FactoryLM Core                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              create_llm_client()                         │   │
│  │                 Factory Function                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│              ┌───────────────┼───────────────┐                  │
│              ▼               ▼               ▼                  │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐         │
│  │  GroqClient   │ │DeepSeekClient │ │ ClaudeClient  │         │
│  └───────────────┘ └───────────────┘ └───────────────┘         │
│              │               │               │                  │
│              └───────────────┼───────────────┘                  │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              BaseLLMClient (Abstract)                    │   │
│  │  - analyze_machine_state()                               │   │
│  │  - chat()                                                │   │
│  │  - stream_chat()                                         │   │
│  │  - estimate_cost()                                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    LLMResponse                           │   │
│  │  - text, tokens_used, model                              │   │
│  │  - input_tokens, output_tokens                           │   │
│  │  - finish_reason, created_at                             │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    External LLM APIs                             │
│         GROQ API    │    DeepSeek API    │    Anthropic API     │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Machine State Analysis

```
1. Application receives sensor data from PLC
   │
   ▼
2. Application calls client.analyze_machine_state(question, state)
   │
   ▼
3. Client formats data into LLM-optimized prompt
   │
   ▼
4. Client sends request to provider API
   │
   ▼
5. Provider returns completion
   │
   ▼
6. Client wraps response in LLMResponse
   │
   ▼
7. Application receives standardized response
```

## Component Details

### BaseLLMClient

Abstract base class defining the interface all LLM clients must implement:

```python
class BaseLLMClient(ABC):
    @abstractmethod
    def analyze_machine_state(self, question: str, machine_state: Dict) -> LLMResponse

    @abstractmethod
    def get_model_name(self) -> str

    @abstractmethod
    def estimate_cost(self, response: LLMResponse) -> float
```

### LLMResponse

Standardized response object ensuring consistent data format:

```python
@dataclass
class LLMResponse:
    text: str                    # Generated text
    tokens_used: int            # Total tokens consumed
    model: str                  # Model identifier
    input_tokens: Optional[int]  # Prompt tokens
    output_tokens: Optional[int] # Completion tokens
    finish_reason: Optional[str] # Why generation stopped
    created_at: datetime        # Response timestamp
```

### Factory Function

The `create_llm_client()` factory enables provider switching:

```python
# Switch providers with one line
client = create_llm_client("groq", api_key)     # Use GROQ
client = create_llm_client("deepseek", api_key) # Use DeepSeek
client = create_llm_client("claude", api_key)   # Use Claude
```

## Configuration

Configuration is managed through environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | Active provider | `groq` |
| `LLM_API_KEY` | Provider API key | Required |
| `LLM_MODEL` | Model to use | Provider default |
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `DEBUG` | Enable debug mode | `false` |

## Error Handling

Custom exception hierarchy for error handling:

```
LLMError (base)
├── LLMConnectionError    # Network/connectivity issues
├── LLMAuthenticationError # Invalid API key
├── LLMRateLimitError     # Rate limit exceeded
└── LLMInvalidRequestError # Bad request parameters
```

## Future Extensions

### FLM (FactoryLM Model)

A planned proprietary model specifically trained for industrial diagnostics:

- Specialized knowledge of PLC protocols
- Understanding of industrial sensors and actuators
- On-premise deployment options
- Lower latency for real-time applications

### Additional Providers

The architecture supports easy addition of new providers:

1. Create new client class inheriting from `BaseLLMClient`
2. Implement all abstract methods
3. Add to factory function mapping
4. Add pricing data for cost estimation
