# FactoryLM Core

**LLM Abstraction Layer for Industrial Applications**

FactoryLM Core provides a unified interface for interacting with multiple LLM providers (GROQ, DeepSeek, Claude) for industrial machine diagnostics and automation.

## Features

- **Provider Agnostic**: Switch between LLM providers with a single environment variable
- **Standardized Responses**: Consistent `LLMResponse` format across all providers
- **Cost Tracking**: Built-in cost estimation for API calls
- **Industrial Focus**: Specialized `analyze_machine_state()` method for PLC/sensor data analysis
- **Streaming Support**: Stream responses for real-time applications
- **Extensible**: Easy to add new LLM providers

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/factorylm/core.git
cd core

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -e .
```

### Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Edit `.env`:

```env
LLM_PROVIDER=groq
LLM_API_KEY=your-api-key-here
LLM_MODEL=llama-3.3-70b-versatile
```

### Usage

```python
from factorylm import create_llm_client
from factorylm.config import get_llm_provider, get_llm_api_key

# Create LLM client
client = create_llm_client(
    provider=get_llm_provider(),
    api_key=get_llm_api_key()
)

# Analyze machine state
response = client.analyze_machine_state(
    question="Why is the motor temperature rising?",
    machine_state={
        "motor_temp": 185,
        "ambient_temp": 72,
        "rpm": 1200,
        "load": 0.85
    }
)

print(response.text)
print(f"Tokens used: {response.tokens_used}")
print(f"Estimated cost: ${client.estimate_cost(response):.6f}")
```

## Supported Providers

| Provider | Status | Default Model |
|----------|--------|---------------|
| GROQ | ✅ Full | llama-3.3-70b-versatile |
| DeepSeek | ✅ Full | deepseek-chat |
| Claude | ✅ Full | claude-sonnet-4-20250514 |
| FLM | 🔜 Planned | flm-industrial-v1 |

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/factorylm --cov-report=term-missing

# Run only unit tests
pytest tests/unit -v

# Run only integration tests
pytest tests/integration -v
```

### Code Quality

```bash
# Format code
black src tests

# Check imports
isort src tests

# Lint
flake8 src tests

# Type check
mypy src
```

## Project Structure

```
core/
├── src/factorylm/
│   ├── __init__.py          # Package exports
│   ├── config.py            # Configuration management
│   ├── llm/
│   │   ├── __init__.py      # Factory function
│   │   ├── base.py          # Abstract base classes
│   │   ├── groq_client.py   # GROQ implementation
│   │   ├── deepseek_client.py
│   │   ├── claude_client.py
│   │   └── flm_client.py    # Future FLM
│   └── utils/
│       ├── logger.py        # Logging utilities
│       └── validators.py    # Input validation
├── tests/
│   ├── unit/
│   └── integration/
├── docs/
└── .github/workflows/
```

## Documentation

- [Architecture Overview](docs/ARCHITECTURE.md)
- [LLM Integration Guide](docs/LLM_INTEGRATION.md)
- [Setup Guide](docs/SETUP.md)
- [Contributing](docs/CONTRIBUTING.md)

## License

MIT License - see LICENSE file for details.

## Related Projects

- **Voice HMI** (PRD-002): Voice interface for machine operators
- **PLC Client** (PRD-003): Modbus/PLC communication layer
- **Web Dashboard** (PRD-004): Real-time monitoring dashboard
