# FactoryLM Setup Guide

## Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Git

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/factorylm/core.git
cd core
```

### 2. Create Virtual Environment

**Linux/macOS:**
```bash
python -m venv venv
source venv/bin/activate
```

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Install all dependencies
pip install -r requirements.txt

# Install package in development mode
pip install -e .
```

### 4. Configure Environment

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# LLM Provider (groq, deepseek, claude)
LLM_PROVIDER=groq

# Your API key
LLM_API_KEY=your-api-key-here

# Model (optional - uses provider default if not set)
LLM_MODEL=llama-3.3-70b-versatile

# Logging
LOG_LEVEL=INFO
DEBUG=false
```

## Getting API Keys

### GROQ
1. Go to https://console.groq.com/
2. Sign up or log in
3. Navigate to API Keys
4. Create new key

### DeepSeek
1. Go to https://platform.deepseek.com/
2. Sign up or log in
3. Navigate to API Keys
4. Create new key

### Claude (Anthropic)
1. Go to https://console.anthropic.com/
2. Sign up or log in
3. Navigate to API Keys
4. Create new key

## Verify Installation

### Run Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/unit/test_config.py
```

### Test Import

```python
python -c "from factorylm import create_llm_client; print('Import successful!')"
```

### Quick Test

```python
from factorylm import create_llm_client
from factorylm.config import get_config

# Load config
config = get_config()
print(f"Provider: {config.llm_provider}")
print(f"Model: {config.llm_model}")

# Create client (requires valid API key)
client = create_llm_client(
    provider=config.llm_provider,
    api_key=config.llm_api_key
)

print(f"Client: {client}")
print(f"Model: {client.get_model_name()}")
```

## Development Setup

### Install Dev Dependencies

```bash
pip install -r requirements.txt
```

This includes:
- `pytest` - Testing framework
- `pytest-cov` - Coverage reporting
- `black` - Code formatter
- `flake8` - Linter
- `mypy` - Type checker
- `isort` - Import sorter

### Code Quality Commands

```bash
# Format code
black src tests

# Sort imports
isort src tests

# Run linter
flake8 src tests

# Type check
mypy src

# Run all checks
black src tests && isort src tests && flake8 src tests && mypy src
```

### Running Tests with Coverage

```bash
# Generate coverage report
pytest --cov=src/factorylm --cov-report=term-missing

# Generate HTML report
pytest --cov=src/factorylm --cov-report=html
# Open htmlcov/index.html in browser
```

## Troubleshooting

### Import Error: Module not found

Ensure package is installed in development mode:
```bash
pip install -e .
```

### API Key Invalid

1. Check `.env` file has correct key
2. Ensure no extra spaces around the key
3. Verify key is active in provider console

### Tests Failing

1. Ensure all dependencies are installed: `pip install -r requirements.txt`
2. Check Python version: `python --version` (needs 3.10+)
3. Run with verbose: `pytest -v --tb=long`

### Rate Limit Errors

- GROQ: 30 requests/minute on free tier
- DeepSeek: Varies by plan
- Claude: Check your plan limits

Wait and retry, or upgrade your plan.

## Project Structure After Setup

```
core/
├── .env                    # Your configuration (git ignored)
├── .env.example           # Example configuration
├── .gitignore
├── requirements.txt
├── setup.py
├── pytest.ini
├── README.md
├── src/
│   └── factorylm/
│       ├── __init__.py
│       ├── config.py
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── groq_client.py
│       │   ├── deepseek_client.py
│       │   ├── claude_client.py
│       │   └── flm_client.py
│       └── utils/
│           ├── logger.py
│           └── validators.py
├── tests/
│   ├── conftest.py
│   ├── unit/
│   └── integration/
└── docs/
    ├── ARCHITECTURE.md
    ├── LLM_INTEGRATION.md
    ├── SETUP.md
    └── CONTRIBUTING.md
```
