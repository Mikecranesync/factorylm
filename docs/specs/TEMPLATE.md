# Feature Specification: [Feature Name]

*Created: YYYY-MM-DD*
*Author: [Name]*
*Status: Draft | Review | Approved | Implemented*

---

## Summary

One paragraph describing what this feature does and why it matters.

## Background

Why are we building this? What problem does it solve?

## Goals

- [ ] Primary goal 1
- [ ] Primary goal 2

## Non-Goals

What this feature explicitly does NOT include (to prevent scope creep):
- Non-goal 1
- Non-goal 2

## Design

### Architecture

How does this fit into the existing system?

```
[Component A] → [New Feature] → [Component B]
```

### Data Model

```python
class NewModel:
    id: str
    name: str
    created_at: datetime
```

### API Changes

```
POST /api/v1/feature
{
  "param": "value"
}
```

### UI Changes

Describe any user interface changes.

## Implementation Plan

### Phase 1: Foundation
- [ ] Task 1
- [ ] Task 2

### Phase 2: Core Logic
- [ ] Task 3
- [ ] Task 4

### Phase 3: Polish
- [ ] Task 5
- [ ] Task 6

## Testing Strategy

- Unit tests for core logic
- Integration tests for API
- E2E tests for critical paths

## Rollout Plan

1. Deploy to staging
2. Internal testing
3. Beta users
4. GA release

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Risk 1 | Medium | High | Mitigation strategy |

## Open Questions

- [ ] Question that needs answering before implementation

## References

- Related issue: #XX
- Design doc: [link]
- Similar feature: [link]

---

*Following Constitution: Ship products, generate revenue.*
