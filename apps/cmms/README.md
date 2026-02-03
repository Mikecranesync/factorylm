# FactoryLM CMMS

Computerized Maintenance Management System — the core of industrial maintenance operations.

## Overview
Full-featured CMMS with:
- 📋 Work Order management
- 🏭 Asset tracking
- 📦 Inventory/Parts management
- 👥 Technician assignments
- 📊 Analytics & reporting
- 📱 Mobile-friendly interface

## Source
Migrated from: `grash-cmms` fork, `/root/jarvis-workspace/projects/cmms/`

## Stack
### Frontend
- React 18
- Material-UI
- TypeScript
- Vite

### API
- Java Spring Boot
- PostgreSQL
- REST API

## Structure
```
apps/cmms/
├── frontend/           # React SPA
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── api/               # Spring Boot API
│   ├── src/
│   ├── pom.xml
│   └── Dockerfile
└── docker-compose.yml # Local dev setup
```

## Setup
```bash
# Frontend
cd apps/cmms/frontend
npm install
npm run dev

# API
cd apps/cmms/api
./mvnw spring-boot:run
```

## Rebrand Tasks
- [ ] Update logo: Atlas → FactoryLM
- [ ] Update colors to brand palette
- [ ] Update page titles
- [ ] Update email templates
- [ ] Update documentation

## Status
- [x] Copied from source
- [ ] Rebranded to FactoryLM
- [ ] Mobile optimization complete
- [ ] Shared auth integrated
