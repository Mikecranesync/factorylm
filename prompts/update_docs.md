# Update Docs

Use this prompt after a change is merged to main. The goal is to keep documentation in sync with reality.

## Inputs

- **Merged PR**: The PR that was just merged (title, description, changed files).
- **PLAN.md**: The plan that was executed.

## Steps

### 1. Check README.md (The Vision)

Does this change affect:

- [ ] The component maturity table? (e.g., a component moved from "Prototype" to "Production")
- [ ] The stack description? (e.g., a new layer, provider, or interface)
- [ ] The architecture diagram? (e.g., a new service or connection)
- [ ] The roadmap? (e.g., a roadmap item was completed)
- [ ] The version number? (bump if significant)

If yes, update README.md. Remember: the README IS the vision. Keep it accurate.

### 2. Check CLAUDE.md

Does this change affect:

- [ ] The workflow rules? (e.g., a new step was added to the pipeline)
- [ ] The safety rules? (e.g., new safety-tagged code was introduced)
- [ ] The repository structure? (e.g., a new top-level directory was created)
- [ ] The VPS change protocol? (e.g., a new service was deployed)

If yes, update CLAUDE.md.

### 3. Check Operational Docs

Does this change affect:

- [ ] **RUNBOOK.md** — New operational procedures needed?
- [ ] **REPO_STRUCTURE.md** — New files or directories added?
- [ ] **PRD documents** — Requirements changed or fulfilled?
- [ ] **Service-specific README** — API endpoints, config, or deployment changed?

If yes, update the relevant doc.

### 4. Write an Ops Trace (Infrastructure Changes Only)

If the change touched infrastructure (VPS, systemd services, networking, deployment), write a trace:

```bash
# Create trace file
touch docs/ops/traces/$(date +%Y-%m-%d)-[short-description].md
```

Trace format:

```markdown
# [Date] — [Short Description]

## What Changed
[1-2 sentences]

## Why
[Link to issue or reason]

## Commands Run
```bash
[Actual commands executed on the VPS or infrastructure]
```

## Verification
[How you confirmed it worked]

## Rollback
[How to undo if needed]
```

### 5. Clean Up PLAN.md

After docs are updated:

- Archive the completed PLAN.md by moving it: `mv PLAN.md docs/plans/YYYY-MM-DD-[topic].md`
- The repo root should not have a stale PLAN.md from a finished task

## Output

A clean documentation state where:
- README.md reflects the current system
- CLAUDE.md reflects the current rules
- Operational docs are up to date
- Infrastructure changes have ops traces
- PLAN.md is archived, not lingering
