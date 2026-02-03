# FactoryLM Design Decisions (DESIGN)

## Architecture Decisions

### Decision 1: Provider Abstraction Layer

**Context**: Need to support multiple LLM providers without vendor lock-in.

**Decision**: Implement abstract `BaseLLMClient` with factory function.

**Rationale**:
- Single interface for all providers
- Easy to add new providers
- Swap providers with one config change
- Consistent error handling

**Consequences**:
- Additional abstraction layer
- Must maintain interface compatibility
- Standardized response format required

### Decision 2: Standardized Response Object

**Context**: Different providers return different response formats.

**Decision**: Create `LLMResponse` dataclass with common fields.

**Rationale**:
- Consistent data structure for consumers
- Easy to track tokens and costs
- Serialization support via `to_dict()`
- Type safety with dataclass

**Format**:
```python
@dataclass
class LLMResponse:
    text: str
    tokens_used: int
    model: str
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    finish_reason: Optional[str]
    created_at: datetime
```

### Decision 3: Configuration via Environment

**Context**: Need flexible configuration for different deployments.

**Decision**: Use environment variables with `.env` file support.

**Rationale**:
- Industry standard practice
- Secure (no secrets in code)
- Easy to change without code changes
- Works with containers and CI/CD

**Variables**:
- `LLM_PROVIDER`: groq, deepseek, claude, flm
- `LLM_API_KEY`: Provider API key
- `LLM_MODEL`: Model to use
- `LOG_LEVEL`: Logging verbosity

### Decision 4: Error Handling Strategy

**Context**: Different providers throw different exceptions.

**Decision**: Custom exception hierarchy wrapping provider exceptions.

**Rationale**:
- Consistent error handling for consumers
- Preserves original error for debugging
- Provider-agnostic exception types
- Clear error categories

**Hierarchy**:
```
LLMError
├── LLMConnectionError
├── LLMAuthenticationError
├── LLMRateLimitError
└── LLMInvalidRequestError
```

### Decision 5: Industrial Focus Method

**Context**: Primary use case is industrial machine diagnostics.

**Decision**: Include specialized `analyze_machine_state()` method.

**Rationale**:
- Optimized prompts for industrial context
- Consistent formatting of machine data
- Lower temperature for factual analysis
- Domain-specific system prompts

**Interface**:
```python
def analyze_machine_state(
    question: str,
    machine_state: Dict[str, Any]
) -> LLMResponse
```

### Decision 6: Cost Tracking

**Context**: API costs can accumulate; need visibility.

**Decision**: Built-in cost estimation per provider.

**Rationale**:
- Track spending per request
- Compare provider costs
- Budget monitoring
- Usage analytics

**Implementation**:
- Per-provider pricing dictionaries
- `estimate_cost(response)` method
- Returns USD estimate

### Decision 7: Streaming Support

**Context**: Real-time applications need streaming responses.

**Decision**: Optional `stream_chat()` method with generator pattern.

**Rationale**:
- Progressive response display
- Better UX for voice interfaces
- Memory efficient for long responses

**Interface**:
```python
def stream_chat(messages) -> Iterator[str]:
    for chunk in api_stream:
        yield chunk
```

### Decision 8: FLM Client Skeleton

**Context**: Future proprietary model planned.

**Decision**: Include skeleton implementation that raises NotImplementedError.

**Rationale**:
- Reserve provider name
- Document future capabilities
- Guide alternative usage
- Easy to implement when ready

## Trade-offs Considered

### Sync vs Async

**Chosen**: Synchronous API
**Reason**: Simpler to use, most industrial applications are request-response
**Trade-off**: No native async support (can wrap if needed)

### SDK vs Raw HTTP

**Chosen**: Official SDKs where available
**Reason**: Better maintained, automatic retries, type hints
**Trade-off**: Additional dependencies

### Single Client vs Pool

**Chosen**: Single client instances
**Reason**: Simple, stateless design
**Trade-off**: No connection pooling (handled by SDKs)

## Future Considerations

1. **Async Support**: Add `async` variants if demand arises
2. **Caching**: Add response caching for repeated queries
3. **Batching**: Support batch requests for efficiency
4. **Metrics**: Prometheus metrics export
5. **Retry Logic**: Configurable retry strategies
