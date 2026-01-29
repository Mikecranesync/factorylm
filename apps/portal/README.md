# FactoryLM Portal

Knowledge management and document viewer — the "Second Brain" for industrial operations.

## Overview
Web-based portal for:
- 📄 Document management (create, edit, view)
- 📊 System status monitoring
- 🔍 Full-text search across knowledge base
- 🧠 AI-powered insights (planned)

## Source
Migrated from: `/root/jarvis-workspace/second-brain/`

## Features
- Dark theme (Obsidian-inspired)
- Markdown rendering with syntax highlighting
- Real-time updates
- Category organization (concepts, journals, research, workflows)
- System health dashboard

## Setup
```bash
cd apps/portal
npm install
npm start
```

## Environment
```
PORT=3001
BRAIN_PATH=/path/to/documents
```

## Architecture
```
Express Server
├── /api/documents      # CRUD for markdown docs
├── /api/workspace      # Core config files
├── /api/status         # System health
└── /                   # SPA frontend
```

## Status
- [x] Copied from source
- [ ] Multi-tenant support
- [ ] Document import (PDF, Word)
- [ ] Search indexing
- [ ] AI chat integration
