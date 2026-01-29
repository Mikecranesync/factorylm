# FactoryLM Migration Plan

## Phase 1: Foundation (Current)
- [x] Create FactoryLM repository
- [ ] Set up monorepo structure
- [ ] Configure shared tooling (linting, CI/CD)
- [ ] Design unified auth system

## Phase 2: PLC Copilot Migration
- [ ] Move photo_to_cmms_bot.py → factorylm/services/plc-copilot/
- [ ] Migrate Gemini vision integration
- [ ] Port work order creation logic
- [ ] Add unit tests

## Phase 3: CMMS Migration  
- [ ] Fork grash-cmms → factorylm/apps/cmms/
- [ ] Rebrand UI to FactoryLM
- [ ] Migrate API to shared auth
- [ ] Mobile-optimize remaining pages

## Phase 4: AI Assistant (Jarvis)
- [ ] Extract reusable agent framework
- [ ] Create public-facing assistant mode
- [ ] Build customer onboarding flow
- [ ] Document customization options

## Phase 5: Second Brain / Knowledge Base
- [ ] Migrate document viewer
- [ ] Add multi-tenant support
- [ ] Build customer knowledge import
- [ ] Create documentation generator

## Phase 6: Integration & Polish
- [ ] Unified dashboard
- [ ] Single sign-on across all apps
- [ ] Unified notification system
- [ ] Customer billing integration

## Timeline
| Phase | Target | Status |
|-------|--------|--------|
| Phase 1 | Week 1 | 🚧 In Progress |
| Phase 2 | Week 2 | ⏳ Pending |
| Phase 3 | Week 3-4 | ⏳ Pending |
| Phase 4 | Week 5-6 | ⏳ Pending |
| Phase 5 | Week 7 | ⏳ Pending |
| Phase 6 | Week 8 | ⏳ Pending |
