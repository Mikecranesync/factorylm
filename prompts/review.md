# Review

Use this prompt to review your own diff before pushing. This is the last gate before code leaves your machine.

## Inputs

- **Branch**: The feature branch you're about to push.
- **PLAN.md**: The plan you executed against.

## Steps

### 1. Check the Basics

```bash
# Confirm you're NOT on main
git branch --show-current

# Confirm all plan steps are checked off
cat PLAN.md | grep "\- \[ \]"
# Expected output: (empty — all boxes checked)
```

### 2. Read Every Changed Line

```bash
git diff main...HEAD
```

For each file in the diff, verify:

- [ ] The change matches what PLAN.md says it should do
- [ ] No unrelated changes leaked in (debug prints, formatting-only edits, commented-out code)
- [ ] No hardcoded secrets, tokens, passwords, or API keys
- [ ] No `TODO` or `FIXME` left without a linked issue

### 3. Safety Check

- [ ] No code tagged `# SAFETY` was modified without explicit session approval
- [ ] No code tagged `# PLC` was modified without explicit session approval
- [ ] No code tagged `# CRITICAL` was modified without explicit session approval

If any were modified, confirm you have written approval in this session before proceeding.

### 4. Security Scan (OWASP Top 10)

Check the diff for:

- [ ] **Injection**: Are user inputs sanitized before use in queries, commands, or file paths?
- [ ] **Broken Auth**: Are authentication/authorization checks in place for new endpoints?
- [ ] **Sensitive Data**: Are secrets loaded from environment variables, not hardcoded?
- [ ] **XXE/Deserialization**: Are untrusted inputs parsed safely?
- [ ] **Misconfiguration**: Are CORS, headers, and error responses configured correctly?

### 5. Code Quality

- [ ] Functions are under 50 lines where possible
- [ ] No duplicated logic that should be extracted
- [ ] Error handling is present for external calls (HTTP, PLC, LLM)
- [ ] Imports are clean (no unused imports, no circular dependencies)

### 6. Test Verification

```bash
# Run the relevant test suite
pytest [path/to/tests] -v

# Run the full core tests if core was touched
pytest core/ -v

# Confirm all pass
```

- [ ] All existing tests pass
- [ ] New tests were added for new logic
- [ ] Edge cases are covered (empty input, timeout, malformed data)

### 7. Commit Message Check

```bash
git log --oneline main..HEAD
```

- [ ] Each commit follows conventional format: `feat(scope):`, `fix(scope):`, `chore(scope):`
- [ ] Messages describe the "why", not just the "what"
- [ ] No commit message says "fix" for something that was actually a "feat"

## Output

If all checks pass:

```bash
git push -u origin [branch-name]
```

Then open a PR linking to the Linear issue. After merge, run `prompts/update_docs.md`.

If any check fails, fix the issue before pushing. Do not push with known problems.
