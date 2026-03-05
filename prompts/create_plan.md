# Create Plan

Use this prompt to generate a `PLAN.md` from a Linear issue and an exploration report (output of `prompts/exploration_phase.md`).

## Inputs

- **Issue**: [Linear issue title, description, acceptance criteria]
- **Exploration Report**: [Output from exploration_phase.md]

## Steps

### 1. Define the Objective

Write a clear, one-sentence objective that answers: "What are we changing and why?"

Link to the Linear issue if available.

### 2. List Affected Files

From the exploration report, list every file that will be created, modified, or deleted. For modifications, note the specific functions or sections that will change.

```
### Files to Modify
- `services/diagnosis/main.py` — Add input validation to `/diagnose` endpoint
- `services/diagnosis/test_main.py` — Add unit tests for new validation

### Files to Create
- `services/diagnosis/validators.py` — Input validation utilities

### Files to Delete
- (none)
```

### 3. Write the Approach

Break the work into ordered steps. Each step should be:
- Small enough to verify independently
- Ordered by dependency (foundations first)
- Written as a checkbox so progress can be tracked during execution

```
### Approach
- [ ] Step 1: [Description of what to do and why]
- [ ] Step 2: [Description]
- [ ] Step 3: [Description]
- [ ] Step 4: Run tests and verify
```

### 4. Identify Risks and Mitigations

From the exploration report, carry forward risks and add any new ones discovered during planning.

```
### Risks
| Risk | Impact | Mitigation |
|------|--------|------------|
| [Description] | [High/Medium/Low] | [What to do about it] |
```

### 5. Define Rollback Plan

How do you undo this change if it breaks something?

```
### Rollback
- Revert commit [hash] or cherry-pick revert
- Restart service: `systemctl restart [service]`
- Verify: `curl [health endpoint]`
```

### 6. Define Verification Steps

How do you prove the change works? Be specific.

```
### Verification
1. Run unit tests: `pytest services/diagnosis/ -v`
2. Run integration test: `curl -X POST http://localhost:8200/diagnose -d '{"question": "test"}'`
3. Check logs for errors: `journalctl -u diagnosis -n 20`
4. Confirm no regressions: `pytest core/ -v`
```

## Output

Write the complete PLAN.md to the repo root:

```markdown
# PLAN.md

## Objective
[One sentence: what and why]

**Issue**: [Link or reference]
**Branch**: `feat/[name]` or `fix/[name]`

## Affected Files
[From step 2]

## Approach
[Checkboxed steps from step 3]

## Risks
[Table from step 4]

## Rollback
[From step 5]

## Verification
[From step 6]
```

Hand this PLAN.md to `prompts/execute_plan.md` for implementation.
