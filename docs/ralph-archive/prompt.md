# Ralph Agent Instructions - FactoryLM PLC Client

You are an autonomous coding agent working on **FactoryLM PLC Client** - the industrial I/O layer for Micro820 PLCs.

## Project Context

**Repository**: `C:\Users\hharp\OneDrive\Desktop\FactoryLM`
**Working Directory**: `plc-client/`

**Tech Stack**:
- Python 3.11+
- pymodbus 3.6.1 for Modbus TCP
- pytest for testing

**Key Directories**:
- `core/` - LLM abstraction (already built)
- `plc-client/` - This module (building now)

**Critical Constraints**:
- All tests must pass WITHOUT real hardware (use MockPLC)
- Keep code SIMPLE - industrial systems need reliability
- Follow existing patterns in core/

## Your Task

1. Read the PRD at `scripts/ralph/prd.json`
2. Read progress log at `scripts/ralph/progress.txt` (check Codebase Patterns section first)
3. Check you're on the correct branch from PRD `branchName`. If not, check it out or create from main.
4. Pick the **highest priority** user story where `passes: false`
5. Implement that single user story
6. Run quality checks (see Quality Requirements below)
7. If checks pass, commit ALL changes with message: `feat(STORY-ID): Title`
8. Update the PRD to set `passes: true` for the completed story
9. Append your progress to `scripts/ralph/progress.txt`

## Progress Report Format

APPEND to progress.txt (never replace, always append):
```
## [Date/Time] - [Story ID]
- What was implemented
- Files changed
- **Learnings for future iterations:**
  - Patterns discovered
  - Gotchas encountered
  - Useful context
---
```

## Consolidate Patterns

If you discover a **reusable pattern** that future iterations should know, add it to the `## Codebase Patterns` section at the TOP of progress.txt. Only add patterns that are **general and reusable**, not story-specific details.

## Quality Requirements

**FactoryLM PLC Client Quality Checks** (run ALL before committing):

1. **Python Syntax**: `python -m py_compile plc-client/src/factorylm_plc/*.py`
2. **Import Check**: `cd plc-client && python -c "from factorylm_plc import *"`
3. **Tests**: `pytest plc-client/tests/ -v`
4. All tests must PASS

**Commit Rules**:
- Do NOT commit broken code
- Keep changes focused and minimal
- Follow existing code patterns in core/

## Stop Condition

After completing a user story, check if ALL stories have `passes: true`.

If ALL stories are complete and passing, reply with:
<promise>COMPLETE</promise>

If there are still stories with `passes: false`, end your response normally (another iteration will pick up the next story).

## Important

- Work on ONE story per iteration
- Commit frequently
- NO real hardware needed - MockPLC only
- Read the Codebase Patterns section in progress.txt before starting
