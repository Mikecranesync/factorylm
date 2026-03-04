# Exploration Phase

Use this prompt before touching any code. The goal is to fully understand the problem space, the affected code, and the risks before writing a plan.

## Inputs

- **Issue**: [Paste the Linear issue title, description, and acceptance criteria]
- **Area**: [Which part of the stack? e.g., services/diagnosis, core/llm, openclaw]

## Steps

### 1. Understand the Request

Read the issue carefully. Answer these questions:
- What is being asked for? (feature, fix, refactor, chore)
- What is the acceptance criteria? What does "done" look like?
- What is the user-facing impact?

### 2. Identify Affected Files

Search the codebase for all files related to this change:
- Grep for key terms from the issue (function names, error messages, feature names)
- List every file that could be affected, even indirectly
- Note which files have `# SAFETY`, `# PLC`, or `# CRITICAL` tags — these require explicit approval to modify

### 3. Trace the Data Flow

For the feature area in question:
- Where does data enter the system? (API endpoint, Telegram message, PLC read)
- What transforms or processes it? (service logic, LLM call, rule engine)
- Where does data exit? (response, database write, Telegram reply)
- Draw the flow: `Input → Service A → Service B → Output`

### 4. Find Existing Patterns

Before proposing new code, check:
- Does a similar feature already exist? How was it implemented?
- Are there utilities, base classes, or abstractions that should be reused?
- What testing patterns are used in this area? (pytest fixtures, mocks, etc.)
- What error handling patterns are used?

### 5. Identify Risks and Unknowns

- What could break? List the blast radius.
- Are there dependencies on external services (VPS, PLC laptop, Telegram API)?
- Are there race conditions, concurrency issues, or state management concerns?
- What don't you know yet? List explicit unknowns.

## Output

Produce a structured exploration report:

```
## Exploration Report: [Issue Title]

### Summary
[1-2 sentences on what this change does]

### Affected Files
- `path/to/file.py` — [why it's affected]
- `path/to/other.py` — [why it's affected]

### Data Flow
[Input] → [Step 1] → [Step 2] → [Output]

### Existing Patterns to Reuse
- [Pattern/utility] in `path/to/file.py`

### Safety-Tagged Code
- [ ] No safety-tagged code affected
- [ ] Safety-tagged code found in: [files] — REQUIRES APPROVAL

### Risks
1. [Risk description] — Mitigation: [approach]

### Unknowns
1. [What you don't know yet and how to find out]
```

Hand this report to `prompts/create_plan.md` as input.
