# FactoryLM CAD Files

**Versioned engineering drawings and build specifications.**

## Structure
```
cad/
├── README.md
└── conveyor-yc-demo/
    ├── v1.0/           # Original Unistrut design (archived)
    └── v2.0/           # Current 2x4 lumber build
        ├── BUILD-SPEC.md
        └── BLUEPRINTS.md
```

## Versioning Rules

1. **Never overwrite** - Create new version folders
2. **Tag releases** - `git tag cad/conveyor-v2.0`
3. **Link photos** - Document actual vs planned
4. **Archive old versions** - Keep history

## Current Projects

| Project | Current Version | Status |
|---------|-----------------|--------|
| YC Demo Conveyor | v2.0 | 🔧 Building |

---

*Use overhead cranes, not blocking tackle.*
