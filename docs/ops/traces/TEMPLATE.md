# TRC-YYYY-MM-DD-NNN: <title>

| Field | Value |
|-------|-------|
| **ID** | TRC-YYYY-MM-DD-NNN |
| **Date** | YYYY-MM-DD |
| **Author** | name |
| **Duration** | Xh Ym |
| **Type** | deployment / fix / recovery / config-change / investigation / feature-build |
| **Services** | service-1, service-2 |
| **Devices** | travel-laptop / plc-laptop / vps |
| **Trigger** | What initiated this activity |

---

## Context

State before the activity. What was happening, what was the starting point.

## What Happened

1. Step one — what was done and why
2. Step two — command or decision made
3. Step three — result observed

## Changes Made

| File/Config | Before | After | Why |
|-------------|--------|-------|-----|
| `path/to/file` | old value | new value | reason |

## Outcome

Result of the activity. New state of the system.

## Queryable Tags

- **error-codes**: E001, E002
- **root-cause**: brief description
- **config-keys**: KEY_NAME
- **ports**: 8000, 502
- **dependencies**: package-name

## Related

- **Workflows**: [WF-NNN](../workflows/slug.md)
- **Config Snapshots**: [YYYY-MM-DD_service.yaml](../config-snapshots/YYYY-MM-DD_service.yaml)
- **Commits**: `abc1234`
- **Prior Traces**: [TRC-YYYY-MM-DD-NNN](./prior-trace.md)
