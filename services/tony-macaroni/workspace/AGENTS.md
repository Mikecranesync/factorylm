# AGENTS

## Safety Defaults

These defaults apply for the first week of operation. Expand permissions only after confirming each capability works correctly.

### Permissions

| Capability | Status | Notes |
|-----------|--------|-------|
| File system (local) | Allowed | Read/write within workspace |
| Web search | Allowed | Research, documentation, parts lookup |
| Shell commands | Allowed | Local commands only, no remote execution |
| Email — read | Allowed | Read-only, no replies or forwards |
| Email — send | Blocked | Requires explicit Telegram approval per message |
| Outbound HTTP | Blocked | No calling external APIs without approval |
| Purchases | Blocked | Never. Always escalate to Mike Harper |
| Database writes | Blocked | Read-only until Phase 4 |

### Escalation Rules

- **Any destructive action** (delete, overwrite, format) → Confirm via Telegram first
- **Any external communication** (email, API call, webhook) → Confirm via Telegram first
- **Any uncertainty about safety** → Stop and ask. Do not guess.

### Week One Focus

1. Learn the workspace structure
2. Index existing documentation
3. Build familiarity with equipment naming conventions
4. Establish daily note-taking rhythm via nightly extraction cron
