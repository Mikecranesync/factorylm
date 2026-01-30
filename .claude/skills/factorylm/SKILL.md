# FactoryLM Domain Knowledge

## What is FactoryLM?

FactoryLM is an industrial AI platform for maintenance and operations. It combines:
- **CMMS** — Computerized Maintenance Management System
- **PLC Copilot** — AI-powered equipment diagnostics
- **AI Assistant** — Chat-based maintenance support (WhatsApp, Telegram)
- **Knowledge Base** — Equipment manuals, troubleshooting guides

## Target Markets

### Primary: Latin America (Venezuela Focus)
- Oil & gas industry (PDVSA, service companies)
- Legacy equipment with limited documentation
- Spanish-first communication
- WhatsApp as primary channel

### Secondary: US Industrial
- Manufacturing plants
- Crane/heavy equipment companies
- Field technicians

## Technical Stack

### Frontend (apps/)
- React with TypeScript
- Material-UI components
- Redux for state management

### Backend (services/)
- Node.js APIs
- PostgreSQL (Neon) for data
- Redis for caching

### AI/ML (core/)
- Python services
- Claude for analysis and synthesis
- Groq for fast screening
- OpenAI embeddings for search

### Adapters
- WhatsApp (Twilio)
- Telegram
- Slack (planned)

## Equipment Taxonomy

FactoryLM recognizes 50+ manufacturers across categories:
- **VFDs:** Allen-Bradley, Siemens, ABB, Yaskawa, Danfoss
- **PLCs:** Allen-Bradley, Siemens, Mitsubishi, Omron
- **Motors:** WEG, Baldor, Siemens, ABB
- **Pumps:** Grundfos, Flowserve, ITT Goulds

## Key Patterns

### Photo Analysis Pipeline
1. **Stage 1:** Groq screening (is it industrial equipment?)
2. **Stage 2:** DeepSeek extraction (specs from nameplate)
3. **Stage 3:** Claude synthesis (troubleshooting guidance)

### Message Routing
Platform-agnostic routing via `core/services/message_router.py`:
- Handles text, photos, voice messages
- Returns structured `BotResponse` objects
- Adapters only handle I/O

### Internationalization
Full Spanish support via `core/i18n/`:
- Equipment terminology
- Troubleshooting steps
- Error messages

## Coding Standards

### Python (core/)
- Python 3.11+
- Type hints required
- async/await for I/O
- pydantic for data models

### TypeScript (apps/, services/, packages/)
- Strict mode enabled
- ESLint + Prettier
- Functional components with hooks

### Commits
- Conventional commits: `feat:`, `fix:`, `docs:`, etc.
- Reference issue numbers: `#14`

## Environment Variables

Key configuration (never commit secrets):
```
DATABASE_URL=postgresql://...
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

## Common Tasks

### Adding a new adapter
1. Create directory in `adapters/`
2. Implement webhook handler
3. Use `core/services/message_router.py` for routing
4. Add tests

### Adding equipment support
1. Update `core/services/equipment_taxonomy.py`
2. Add manufacturer patterns
3. Test with sample photos

### Adding translations
1. Edit `core/i18n/translations/es.json`
2. Add English fallback in `en.json`
3. Use translator in code: `t("key", param=value)`

---
*FactoryLM: Industrial AI for the real world.*
