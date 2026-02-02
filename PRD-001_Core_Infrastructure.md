# PRD-001: FactoryLM Core Infrastructure & Project Bootstrap
## Phase 0: Repository Setup, Architecture Foundation, Mock LLM Integration

**Domain:** factorylm.com  
**GitHub:** github.com/factorylm/core  
**Product:** FactoryLM Core (Foundational Infrastructure)  
**Version:** 0.1.0  
**Status:** PRE-BUILD - Infrastructure Phase  

---

## Executive Summary

FactoryLM Core is the foundational infrastructure layer that sets up the complete project structure, mock LLM integration, and testing scaffolding. This phase establishes:

- Complete GitHub repository structure (monorepo or multi-repo strategy)
- Mock LLM abstraction layer (swappable between GROQ, DeepSeek, Claude, proprietary FLM)
- Base configuration system
- Testing infrastructure
- CI/CD pipeline setup
- Development environment automation

**This phase MUST complete before any feature development begins.**

---

## Architecture Overview

```
factorylm/
├── core/                          (This repo - infrastructure)
│   ├── .github/
│   │   ├── workflows/
│   │   │   ├── ci.yml
│   │   │   └── tests.yml
│   │   └── ISSUE_TEMPLATE/
│   ├── src/
│   │   ├── factorylm/
│   │   │   ├── __init__.py
│   │   │   ├── config.py          (Config management)
│   │   │   ├── llm/               (Mock LLM abstraction)
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py        (Abstract LLM interface)
│   │   │   │   ├── groq_client.py (GROQ implementation)
│   │   │   │   ├── deepseek_client.py
│   │   │   │   ├── claude_client.py
│   │   │   │   └── flm_client.py  (Future: FactoryLM LLM)
│   │   │   └── utils/
│   │   │       ├── logger.py
│   │   │       └── validators.py
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── test_config.py
│   │   │   ├── test_llm_interface.py
│   │   │   └── test_groq_client.py
│   │   ├── integration/
│   │   │   └── test_llm_switching.py
│   │   └── conftest.py
│   ├── docs/
│   │   ├── ARCHITECTURE.md
│   │   ├── LLM_INTEGRATION.md
│   │   ├── SETUP.md
│   │   └── CONTRIBUTING.md
│   ├── .env.example
│   ├── requirements.txt
│   ├── setup.py
│   ├── pytest.ini
│   ├── .gitignore
│   ├── README.md
│   └── HOMEWORK.md                (Research findings)

├── voice-hmi/                     (Phase 1 repo - will reference core)
├── plc-client/                    (Phase 2 repo)
├── web-dashboard/                 (Phase 3 repo)
└── ml-training/                   (Phase 4 repo - future)
```

---

## Detailed Implementation Requirements

### 1. Repository Structure & Git Setup

#### 1.1 Create factorylm/core repo

```bash
mkdir -p ~/projects/factorylm/core
cd ~/projects/factorylm/core
git init
git config user.email "your-email@example.com"
git config user.name "Your Name"
```

#### 1.2 Directory structure creation

Claude Code MUST create the EXACT structure above with:
- [ ] All directories with proper `__init__.py` files
- [ ] `.gitignore` with Python patterns
- [ ] `.github/workflows/` CI/CD setup
- [ ] `docs/` folder with architecture documentation

#### 1.3 Initial commit

```bash
git add .
git commit -m "Initial: FactoryLM Core infrastructure setup"
```

### 2. Mock LLM Abstraction Layer

#### 2.1 Base LLM Interface (src/factorylm/llm/base.py)

```python
# Abstract base class that ALL LLM clients must implement
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

class LLMResponse:
    """Standardized response object from any LLM"""
    def __init__(self, text: str, tokens_used: int, model: str):
        self.text = text
        self.tokens_used = tokens_used
        self.model = model

class BaseLLMClient(ABC):
    """Abstract interface for all LLM providers"""
    
    @abstractmethod
    def __init__(self, api_key: str, model: str):
        pass
    
    @abstractmethod
    def analyze_machine_state(self, question: str, machine_state: Dict) -> LLMResponse:
        """Analyze PLC state and answer technician question"""
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """Return the model name being used"""
        pass
    
    @abstractmethod
    def estimate_cost(self, response: LLMResponse) -> float:
        """Estimate cost of this API call"""
        pass
```

Requirements:
- [ ] All methods documented with docstrings
- [ ] Type hints on all parameters
- [ ] Standardized response format (LLMResponse)
- [ ] Error handling interface defined

#### 2.2 GROQ Implementation (src/factorylm/llm/groq_client.py)

- [ ] Use official GROQ Python SDK
- [ ] Implement all BaseLLMClient abstract methods
- [ ] Handle API errors gracefully
- [ ] Support streaming responses
- [ ] Track token usage

#### 2.3 DeepSeek Implementation (src/factorylm/llm/deepseek_client.py)

- [ ] Implement all BaseLLMClient abstract methods
- [ ] Compatible with OpenAI-compatible API
- [ ] Cost tracking

#### 2.4 Claude Implementation (src/factorylm/llm/claude_client.py)

- [ ] Use official Anthropic SDK
- [ ] Implement all BaseLLMClient abstract methods
- [ ] Support streaming responses

#### 2.5 Factory Function (src/factorylm/llm/__init__.py)

```python
def create_llm_client(provider: str, api_key: str, model: str) -> BaseLLMClient:
    """Factory function to create appropriate LLM client"""
    if provider == "groq":
        return GroqClient(api_key, model)
    elif provider == "deepseek":
        return DeepSeekClient(api_key, model)
    elif provider == "claude":
        return ClaudeClient(api_key, model)
    elif provider == "flm":
        return FLMClient(api_key, model)
    else:
        raise ValueError(f"Unknown provider: {provider}")
```

### 3. Configuration Management (src/factorylm/config.py)

Requirements:
- [ ] Load from `.env` file
- [ ] Support multiple LLM providers via `LLM_PROVIDER` env var
- [ ] Validate all required env vars on startup
- [ ] Default to GROQ for MVP

```python
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")  # groq, deepseek, claude, flm
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "mixtral-8x7b-32768")  # GROQ model
```

### 4. Testing Infrastructure

#### 4.1 Unit Tests (tests/unit/)

- [ ] test_config.py
  - Verify env vars load correctly
  - Verify validation works
  - Verify defaults set properly

- [ ] test_llm_interface.py
  - Verify BaseLLMClient abstract methods exist
  - Verify LLMResponse structure

- [ ] test_groq_client.py
  - Mock GROQ API responses
  - Verify request/response flow
  - Verify error handling

#### 4.2 Integration Tests (tests/integration/)

- [ ] test_llm_switching.py
  - Verify can switch between providers
  - Verify all providers implement interface correctly
  - Verify responses are standardized

### 5. Documentation

#### 5.1 ARCHITECTURE.md

Explain:
- Complete system architecture
- Data flow diagram
- How LLM abstraction works
- Why modular approach

#### 5.2 LLM_INTEGRATION.md

Explain:
- How to add new LLM provider
- How to use LLM client in code
- Supported providers and models
- Cost tracking per provider

#### 5.3 SETUP.md

Step-by-step:
- Clone repo
- Create venv
- Install dependencies
- Set up `.env`
- Run tests
- Run example

#### 5.4 CONTRIBUTING.md

Guidelines for:
- Adding new LLM providers
- Code standards
- Testing requirements
- PR process

### 6. Requirements & Dependencies

```
# Core dependencies
python-dotenv==1.0.0
groq==0.14.0
openai==1.6.1  # For DeepSeek (OpenAI-compatible)
anthropic==0.28.1

# Testing
pytest==7.4.3
pytest-cov==4.1.0
pytest-mock==3.12.0

# Development
black==23.12.0
flake8==6.1.0
mypy==1.7.1
```

### 7. CI/CD Pipeline (.github/workflows/)

#### 7.1 ci.yml

- [ ] Run on every push/PR
- [ ] Run linting (black, flake8)
- [ ] Run type checking (mypy)
- [ ] Run all tests
- [ ] Generate coverage report

#### 7.2 tests.yml

- [ ] Run full test suite
- [ ] Test with Python 3.10+
- [ ] Ensure 80%+ coverage

### 8. Deployment & Versioning

#### 8.1 setup.py

- [ ] Define package metadata
- [ ] List all dependencies
- [ ] Enable pip install

#### 8.2 Version management

- [ ] Store version in `src/factorylm/__init__.py`
- [ ] Tag releases in git

---

## Ralph Loop Instructions for Claude Code

```text
You are setting up FactoryLM Core: the infrastructure foundation.

HOMEWORK PHASE (Do First):
1. Research Python project structure best practices
2. Review official GROQ, DeepSeek, Claude SDKs
3. Understand abstract base classes and factory patterns
4. Document findings in HOMEWORK.md

DESIGN PHASE (Plan Second):
1. Verify abstraction pattern will work for all 3 LLMs
2. Plan how to handle different API response formats
3. Design error handling strategy
4. Document in DESIGN.md

EXECUTION PHASE (Code Third - Using Ralph Loop):
1. Create directory structure exactly as specified
2. Implement BaseLLMClient abstract class
3. Implement GroqClient (simplest - use GROQ free tier)
4. Implement unit tests for GroqClient
5. Add pytest configuration
6. Add GitHub Actions CI/CD
7. Create all documentation files
8. Verify all tests pass: pytest -v --cov=src
9. Make initial commit
10. When all criteria met, output success summary

CRITICAL REQUIREMENTS:
- All LLM clients must implement BaseLLMClient interface
- All responses must return LLMResponse objects
- All env vars must be documented in .env.example
- All public methods must have docstrings
- All tests must pass before moving to next phase
- Coverage must be 80%+

When complete, append "FACTORYLM_CORE_COMPLETE" to end of this PRD.
```

---

## Completion Criteria

- [ ] GitHub repo created and initialized
- [ ] Complete directory structure in place
- [ ] BaseLLMClient abstract class implemented
- [ ] GroqClient fully implemented and tested
- [ ] DeepSeekClient skeleton (interface only, no API calls)
- [ ] ClaudeClient skeleton (interface only, no API calls)
- [ ] FLMClient skeleton for future proprietary LLM
- [ ] All unit tests passing
- [ ] Integration tests passing
- [ ] 80%+ code coverage
- [ ] CI/CD pipeline configured
- [ ] All documentation written
- [ ] Initial commit to GitHub
- [ ] `.env.example` with all required vars
- [ ] `README.md` explains the project
- [ ] `HOMEWORK.md` documents research findings
- [ ] `DESIGN.md` documents architecture decisions

---

## Success Criteria (End State)

```
FACTORYLM_CORE_COMPLETE

✓ Core infrastructure ready for feature development
✓ LLM abstraction layer prevents vendor lock-in
✓ Can switch between GROQ, DeepSeek, Claude with 1 env var change
✓ Ready for Phase 1: Voice HMI development
✓ Ready for Phase 1: PLC Client development
✓ Can be imported by other projects: from factorylm import create_llm_client
```

---

## Timeline

- **Days 1-2:** Research + Plan (HOMEWORK + DESIGN)
- **Days 3-6:** Implement Core Infrastructure
- **Days 7:** Testing + Documentation
- **Day 8:** Final Polish + Commit

**Total: 1 week to FACTORYLM_CORE_COMPLETE**

---

## Notes for Next Phases

This core layer will be **imported by** PRD-002, PRD-003, and PRD-004. Each phase will:

```python
from factorylm import create_llm_client
from factorylm.config import LLM_PROVIDER, LLM_API_KEY

llm = create_llm_client(LLM_PROVIDER, LLM_API_KEY)
response = llm.analyze_machine_state(question, machine_state)
```

This keeps all LLM logic centralized and testable.

---

**START WITH THIS PRD. Don't move to other phases until FACTORYLM_CORE_COMPLETE is appended to this file.**
