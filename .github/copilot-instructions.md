# GitHub Copilot Instructions for FactoryLM

## Project Overview

FactoryLM is an industrial AI platform combining CMMS, equipment diagnostics, and AI-powered maintenance assistance. Target market: Latin American oil & gas industry.

## Repository Structure

```
factorylm/
├── apps/           # User-facing applications (React/TS)
├── services/       # Backend microservices (Node.js)
├── packages/       # Shared TypeScript code
├── adapters/       # Channel adapters (WhatsApp, Telegram)
├── core/           # Shared Python code (AI, OCR, i18n)
└── docs/           # Documentation and specs
```

## Coding Conventions

### TypeScript (apps/, services/, packages/, adapters/)
- Use strict mode
- Prefer functional components with hooks
- Use async/await, not callbacks
- Types over `any`

### Python (core/)
- Python 3.11+
- Type hints on all functions
- Use pydantic for data models
- async/await for I/O operations

### General
- Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`
- Reference GitHub issues: `Fixes #14`
- Write tests for new functionality

## Domain Terms

- **VFD** = Variable Frequency Drive (motor controller)
- **PLC** = Programmable Logic Controller
- **Nameplate** = Equipment label with specs
- **Fault code** = Error code displayed on equipment
- **CMMS** = Computerized Maintenance Management System

## Key Files

- `turbo.json` — Monorepo build configuration
- `core/services/message_router.py` — Multi-channel message handling
- `core/services/equipment_taxonomy.py` — Equipment identification
- `core/i18n/translations/es.json` — Spanish translations

## Important Patterns

### Platform-Agnostic Routing
All messaging goes through `message_router.py`. Adapters handle only I/O.

### Cost-Optimized AI
Use cheapest provider first (Groq), escalate to Claude only when needed.

### Spanish-First
Default to Spanish for Latin American users. Detect language from phone number (+58 = Venezuela).

## Do Not

- Commit secrets or API keys
- Push directly to main branch
- Merge without approval
- Delete code without archiving first
