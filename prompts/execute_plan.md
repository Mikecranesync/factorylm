# Execute Plan

Use this prompt to implement a `PLAN.md` step by step. The plan must already exist in the repo root before starting.

## Inputs

- **PLAN.md**: Read `PLAN.md` from the repo root.

## Rules

1. **Work in order.** Do not skip steps. Do not reorder steps without updating PLAN.md first.
2. **One step at a time.** Complete each step fully before moving to the next.
3. **Check the box.** After completing each step, update PLAN.md to mark it `[x]`.
4. **Test after each significant change.** Run the relevant test suite after any logic change.
5. **Stop on surprises.** If something unexpected happens (test failure, missing dependency, unclear requirement), STOP. Do not hack around it. Reassess the plan.
6. **Respect safety tags.** If you encounter `# SAFETY`, `# PLC`, or `# CRITICAL`, stop and ask for explicit approval before modifying.

## Steps

### 1. Read and Confirm

Read PLAN.md. Confirm you understand:
- The objective
- All affected files
- The order of operations
- The verification criteria

State: "I understand the plan. Starting execution."

### 2. Create the Branch

```bash
git checkout -b feat/[name-from-plan]
```

Never work directly on main.

### 3. Execute Each Step

For each checkbox in the Approach section:

1. Read the step description
2. Identify the file(s) to modify
3. Read the current state of those files
4. Make the change
5. Run tests relevant to the change
6. Update PLAN.md: change `- [ ]` to `- [x]`
7. Commit with a meaningful message: `feat(scope): description`

### 4. Handle Failures

If a test fails or something breaks:

1. **Do not move to the next step.**
2. Read the error message carefully.
3. Check if the failure is related to your change or pre-existing.
4. Fix the root cause, not the symptom.
5. Re-run tests to confirm the fix.
6. If the fix requires plan changes, update PLAN.md first.

### 5. Final Verification

After all steps are checked off:

1. Run the full verification section from PLAN.md.
2. Confirm every verification step passes.
3. Run `git diff` to review all changes.

Hand the diff to `prompts/review.md` for self-review before pushing.

## Output

A completed PLAN.md with all boxes checked and a clean branch ready for review.
