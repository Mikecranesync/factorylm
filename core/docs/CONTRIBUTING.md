# Contributing to FactoryLM

Thank you for your interest in contributing to FactoryLM!

## Development Process

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR-USERNAME/core.git
cd core
git remote add upstream https://github.com/factorylm/core.git
```

### 2. Create Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 3. Make Changes

- Write code following our style guidelines
- Add tests for new functionality
- Update documentation as needed

### 4. Run Tests

```bash
# Run full test suite
pytest

# Run with coverage (must be 80%+)
pytest --cov=src/factorylm --cov-fail-under=80
```

### 5. Check Code Quality

```bash
# Format
black src tests

# Sort imports
isort src tests

# Lint
flake8 src tests

# Type check
mypy src
```

### 6. Commit Changes

```bash
git add .
git commit -m "feat: add your feature description"
```

Follow [Conventional Commits](https://www.conventionalcommits.org/):
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation
- `test:` - Adding tests
- `refactor:` - Code refactoring
- `chore:` - Maintenance

### 7. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

## Code Standards

### Python Style

- Follow PEP 8
- Use type hints for all public functions
- Maximum line length: 100 characters
- Use docstrings for all public classes and methods

### Docstring Format

```python
def function_name(param1: str, param2: int = 10) -> bool:
    """
    Short description of function.

    Longer description if needed. Can span multiple lines
    and include more details about behavior.

    Args:
        param1: Description of param1
        param2: Description of param2 (default: 10)

    Returns:
        Description of return value

    Raises:
        ValueError: When param1 is empty

    Example:
        >>> result = function_name("test", 20)
        >>> print(result)
        True
    """
```

### Type Hints

```python
from typing import Dict, List, Optional, Any

def process_data(
    items: List[str],
    config: Optional[Dict[str, Any]] = None
) -> bool:
    pass
```

## Testing Requirements

### Test Structure

```
tests/
├── unit/           # Fast, isolated tests
│   ├── test_config.py
│   ├── test_llm_interface.py
│   └── test_groq_client.py
├── integration/    # Tests with external dependencies
│   └── test_llm_switching.py
└── conftest.py     # Shared fixtures
```

### Writing Tests

```python
import pytest

class TestMyFeature:
    """Tests for my feature."""

    def test_basic_functionality(self):
        """Test basic operation."""
        result = my_function()
        assert result == expected

    def test_edge_case(self):
        """Test edge case handling."""
        with pytest.raises(ValueError):
            my_function(invalid_input)

    @pytest.fixture
    def sample_data(self):
        """Provide sample data for tests."""
        return {"key": "value"}
```

### Coverage Requirements

- Minimum 80% coverage overall
- All new code must have tests
- All bug fixes must include regression tests

## Adding New LLM Providers

1. Create client in `src/factorylm/llm/`
2. Inherit from `BaseLLMClient`
3. Implement all abstract methods
4. Add to factory in `__init__.py`
5. Add pricing data
6. Write comprehensive tests
7. Update documentation

See [LLM Integration Guide](LLM_INTEGRATION.md) for details.

## Documentation

- Update README.md for user-facing changes
- Update relevant docs/ files
- Include docstrings in code
- Add examples where helpful

## Pull Request Checklist

Before submitting:

- [ ] Tests pass locally
- [ ] Coverage is 80%+
- [ ] Code is formatted (black)
- [ ] Imports are sorted (isort)
- [ ] Linting passes (flake8)
- [ ] Type checking passes (mypy)
- [ ] Documentation is updated
- [ ] Commit messages follow convention
- [ ] PR description explains changes

## Review Process

1. CI checks must pass
2. At least one maintainer review
3. All review comments addressed
4. Squash merge to main

## Questions?

- Open an issue for bugs or features
- Use discussions for questions
- Check existing issues before creating new ones

Thank you for contributing!
