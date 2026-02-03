# FactoryLM

**Industrial AI Platform — Digital Twin Architecture**

FactoryLM consolidates all industrial AI capabilities into one unified platform:

## Core Components

| Component | Source | Status |
|-----------|--------|--------|
| **PLC Copilot** | Rivet-PRO | 🔄 Migrating |
| **CMMS** | Atlas/grash-cmms | 🔄 Migrating |
| **AI Assistant** | Jarvis | 🔄 Migrating |
| **Knowledge Base** | Second Brain | 🔄 Migrating |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     FactoryLM                            │
├─────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐  │
│  │   PLC    │  │   CMMS   │  │    AI    │  │ Second  │  │
│  │  Copilot │  │  (Atlas) │  │ (Jarvis) │  │  Brain  │  │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘  │
├─────────────────────────────────────────────────────────┤
│                   Shared Services                        │
│  • Authentication  • Storage  • Messaging  • Analytics   │
├─────────────────────────────────────────────────────────┤
│                   Infrastructure                         │
│  • Docker  • PostgreSQL  • Redis  • Nginx               │
└─────────────────────────────────────────────────────────┘
```

## Digital Twin Philosophy

> What we build internally = What customers get

The same platform that runs our operations becomes the product we sell. No separate "demo" version — customers get the real thing.

## Migration Status

See [MIGRATION.md](./MIGRATION.md) for detailed migration plan.

## Getting Started

*Coming soon*

---

**FactoryLM** — AI for the Factory Floor
