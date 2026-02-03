# CLAUDE.md

## ⚠️ READ FIRST: The Vision

Before doing ANY work, read the FactoryLM Vision:
**https://github.com/Mikecranesync/factorylm/blob/main/README.md**

That document IS the architecture. Do not propose ideas that contradict it.

## Quick Reference

### The Stack (Layer 0-3)
- **Layer 0**: Deterministic code + KB (Plane, Wiseflow, Vector DB) — THE GOAL
- **Layer 1**: Edge LLM on Pi (0.5B model)
- **Layer 2**: Local GPU server (70B, air-gapped)
- **Layer 3**: Cloud AI (Claude/GPT, optional)

### Key Principle
Intelligence flows DOWNWARD. Convert Layer 3 answers into Layer 0 code over time.

### Interfaces (Priority Order)
1. WhatsApp (PRIMARY)
2. Phone
3. Telegram
4. Slack
5. Halo Glasses

### The Rule
When Mike says "update the README" → Update the VISION.
Everything references the vision. One source of truth.

---

## This Repository: factorylm-dev

Development monorepo containing:
- `apps/` — Frontend applications
- `services/` — Backend microservices  
- `adapters/` — Channel adapters (WhatsApp, Telegram)
- `core/` — Shared Python code (AI, OCR, i18n)

See `.github/copilot-instructions.md` for coding standards.
