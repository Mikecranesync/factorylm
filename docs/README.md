# FactoryLM Documentation

## Structure

```
docs/
├── specs/          # Feature specifications (write before coding)
├── architecture/   # Architecture decision records (ADRs)
└── runbooks/       # Operations guides
```

## Specs Directory

Contains feature specifications. **Always write a spec before implementing a new feature.**

Use `specs/TEMPLATE.md` as a starting point.

### Process
1. Copy TEMPLATE.md to `specs/feature-name.md`
2. Fill in all sections
3. Review with team
4. Get approval before coding
5. Update status as you implement

## Why Specs First?

> "90% of Claude Code is written by Claude Code itself" — Anthropic

AI-assisted development works best with clear specifications. The upfront investment in planning pays off enormously during implementation.

## Creating a New Spec

```bash
cp docs/specs/TEMPLATE.md docs/specs/my-feature.md
# Edit the file with your feature details
```

---

*Following Constitution: Ship products, generate revenue.*
