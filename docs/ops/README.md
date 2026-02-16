# FactoryLM Operational Documentation

Lightweight ops documentation framework that captures deployment knowledge, fix procedures, and service configuration as queryable artifacts.

## What's Here

```
docs/ops/
├── registry.yaml              # Master index — all services, scripts, configs, network
├── traces/                    # Activity logs (deploys, fixes, investigations)
├── workflows/                 # Repeatable procedures with verification steps
├── config-snapshots/          # Point-in-time service configuration captures
└── incidents/                 # Post-incident reviews
```

## Artifact Types

### Traces (`traces/YYYY-MM-DD_slug.md`)

A trace documents **what happened** during a specific activity — a deployment, bug fix, recovery, or investigation. It captures the context, steps taken, changes made, and outcome.

**Create a trace when**: you deploy, fix a bug, recover from a failure, change config, or investigate an issue.

### Workflows (`workflows/slug.md`)

A workflow documents **how to do** a repeatable procedure. Each step includes the device, command, expected output, and verification. Workflows also include rollback and troubleshooting sections.

**Create a workflow when**: you find yourself running the same sequence of steps more than once, or when a procedure is critical enough that someone else needs to be able to follow it.

### Config Snapshots (`config-snapshots/YYYY-MM-DD_service.yaml`)

A config snapshot captures the **current state** of a service's configuration — env vars, config file paths, key settings, and dependencies. Date-prefixed so you can track changes over time.

**Create a config snapshot when**: you deploy a service, change its configuration, or need to document what's running.

### Incidents (`incidents/INC-YYYY-MM-DD-NNN.md`)

An incident review documents a **production issue** — timeline, root cause, resolution, and prevention steps. Links to the resulting trace, workflow, or config snapshot.

**Create an incident review when**: something breaks in production and you want to prevent it from happening again.

## File Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Trace | `YYYY-MM-DD_slug.md` | `2026-02-16_photo-handler-fix.md` |
| Workflow | `slug.md` | `deploy-plc-copilot.md` |
| Config Snapshot | `YYYY-MM-DD_service.yaml` | `2026-02-16_plc-copilot.yaml` |
| Incident | `INC-YYYY-MM-DD-NNN.md` | `INC-2026-02-16-001.md` |

## Querying

```bash
# Find all artifacts for a service
grep -r "plc-copilot" docs/ops/

# List recent traces
ls docs/ops/traces/ | grep 2026-02

# Find workflows involving the VPS
grep -l "vps" docs/ops/workflows/

# Check what's in the registry for a service
grep -A 20 "matrix-api:" docs/ops/registry.yaml
```

## Ops-Flush Pattern

Documentation is never written inline during active work. Instead:

1. **During work** — append brief notes to `/tmp/ops-buffer.md`
2. **After work** — flush the buffer into proper artifacts under `docs/ops/`
3. **Before work** — check `registry.yaml` and recent traces before exploring the codebase

Buffer format (just append lines):
```
[TRACE] service=plc-copilot type=fix | Added message chunking for Telegram 4096 limit
[CONFIG] service=cosmos-agent | Changed model from 8b to 70b in cosmos.yaml
[WORKFLOW] name=deploy-bot | Steps: git pull, systemctl restart, verify health
```

## Future: Observability Stack Integration

This framework provides the local foundation. When external tools are added, the existing artifacts map directly:

| Tool | Maps To | Purpose |
|------|---------|---------|
| **Langfuse** | Traces | LLM call tracing (prompts, completions, token costs) |
| **Sentry** | Incidents | Automated error tracking and crash reporting |
| **Doppler** | Config Snapshots | Secrets management and config versioning |
| **Honeycomb** | Traces + Registry | Infrastructure observability (API latency, service health) |
