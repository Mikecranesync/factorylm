# FactoryLM Migration Plan

## Strategy: Copy-First, Archive-Later

> **Rule:** We COPY files to FactoryLM, never move or delete. Old repos stay live until everything is verified. Archive only after sign-off.

```
OLD REPOS (keep live)         FACTORYLM (new home)
─────────────────────         ────────────────────
Rivet-PRO ──────copy────────► services/plc-copilot/
grash-cmms ─────copy────────► apps/cmms/
jarvis-workspace ──copy─────► (selective pieces)
second-brain ───copy────────► apps/portal/
                │
                ▼
        [ARCHIVE after verified]
```

## Phase 1: Foundation (Week 1)
- [x] Create FactoryLM repository
- [ ] Set up monorepo structure
- [ ] Configure Turborepo/npm workspaces
- [ ] Set up CI/CD (GitHub Actions)
- [ ] Create shared ESLint/Prettier config
- [ ] Design unified auth system

## Phase 2: PLC Copilot Migration (Week 2)
**Source:** `/opt/plc-copilot/`, Rivet-PRO repo
**Target:** `factorylm/services/plc-copilot/`

- [ ] Copy photo_to_cmms_bot.py
- [ ] Copy Telegram bot integration
- [ ] Copy Gemini vision logic
- [ ] Update imports/paths
- [ ] Add tests
- [ ] Verify functionality
- [ ] ✅ Sign-off before archiving source

## Phase 3: CMMS Migration (Weeks 3-4)
**Source:** grash-cmms fork, `/root/jarvis-workspace/projects/cmms/`
**Target:** `factorylm/apps/cmms/`

- [ ] Copy frontend to apps/cmms/frontend/
- [ ] Copy API to apps/cmms/api/
- [ ] Rebrand: Atlas → FactoryLM
- [ ] Update Docker configs
- [ ] Test all functionality
- [ ] Mobile optimization pass
- [ ] ✅ Sign-off before archiving source

## Phase 4: AI Assistant Framework (Weeks 5-6)
**Source:** Clawdbot configs, jarvis-workspace
**Target:** `factorylm/services/assistant/`

- [ ] Extract reusable agent patterns
- [ ] Create multi-tenant architecture
- [ ] Build configuration UI
- [ ] Document customization options
- [ ] ✅ Sign-off before archiving source

## Phase 5: Knowledge Base / Portal (Week 7)
**Source:** `/root/jarvis-workspace/second-brain/`
**Target:** `factorylm/apps/portal/`

- [ ] Copy Express server
- [ ] Add multi-tenant support
- [ ] Build document import
- [ ] Add search indexing
- [ ] ✅ Sign-off before archiving source

## Phase 6: Integration & Launch (Week 8)
- [ ] Unified dashboard
- [ ] Single sign-on
- [ ] Billing integration
- [ ] Marketing site
- [ ] Documentation
- [ ] Launch checklist
- [ ] ✅ Final sign-off
- [ ] Archive old repos

## Archive Checklist
Only archive a repo when ALL conditions met:
- [ ] All code copied to FactoryLM
- [ ] All tests passing in new location
- [ ] Production running from FactoryLM
- [ ] Mike's verbal approval
- [ ] Repo marked "archived" (not deleted)
