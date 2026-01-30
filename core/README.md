# FactoryLM Core (Python)

Shared Python code for AI, OCR, and backend services.

## Structure

```
core/
├── adapters/       # Channel adapters (WhatsApp webhook handlers)
├── i18n/           # Internationalization (Spanish translations)
├── models/         # Pydantic data models
├── services/       # Business logic services
└── README.md
```

## Origin

This code is extracted from **Rivet-PRO** following Constitution Amendment VI (One Brand: FactoryLM).

Original source: `rivet_pro/` (archived, not deleted)

## Key Services

### Message Router
Platform-agnostic message handling for multi-channel deployment.

```python
from core.services.message_router import MessageRouter, BotResponse

router = MessageRouter()
result = await router.route_photo(user_id, photo_bytes, "whatsapp", "es")
# result.response_text contains the response
```

### Equipment Taxonomy
50+ manufacturers with pattern matching for model identification.

```python
from core.services.equipment_taxonomy import identify_component

result = identify_component("PowerFlex 525")
# result = {"manufacturer": "Allen-Bradley", "type": "vfd", ...}
```

### Internationalization
Full Spanish support for industrial terminology.

```python
from core.i18n import get_translator

t = get_translator("es")
message = t("equipment_detected", manufacturer="ABB", model="ACS550")
# "✅ Equipo detectado: ABB ACS550"
```

## Installation

```bash
cd core/
pip install -r requirements.txt
```

## Development

```bash
# Run tests
pytest

# Type checking
mypy .

# Linting
ruff check .
```

## Dependencies

- Python 3.11+
- pydantic >= 2.0
- httpx (async HTTP)
- anthropic (Claude API)
- openai (embeddings)

---

*Extracted following Engineering Commandments: Copy, don't delete.*
