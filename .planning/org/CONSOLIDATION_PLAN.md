# CONSOLIDATION PLAN — Mikecranesync Org

> Date: 2026-03-06
> Source: 86 repos mapped across 3 tiers (see INDEX.yaml, OUTCOMES.md)
> Status: DECISIONS MADE, awaiting execution

---

## Q1: Top 5 Repos to Consolidate into factorylm NOW

| # | Repo | File(s) to merge | Target in monolith | Why |
|---|------|-------------------|-------------------|-----|
| 1 | pi-factory-cosmos | `fault_classifier.py` (449 LOC) | `diagnosis/` | Most complete: 14 rules incl VFD (V001-V006). Monolith copy has only 10 rules. |
| 2 | pi-factory-cosmos | `vfd_reader.py` (229 LOC) | `services/plc-modbus/` or new `hardware/` | Only async Modbus reader. Graceful degradation + configurable register map. |
| 3 | pi-factory-cosmos + cookoff | `belt_tachometer.py` + `frame_capture.py` | `cosmos/` | Vision tachometer duplicated in 2 repos. Monolith `cosmos/` dir already exists. |
| 4 | cookoff | `modbus_tag_source.py` (198 LOC) | `services/plc-modbus/` | Most production-hardened Micro 820 map. Verified against cluster memory. |
| 5 | cookoff | `net/diagnosis/vfd_conflicts.py` (154 LOC) | `diagnosis/` | Standalone VFD conflict engine. Complements fault_classifier V-codes. |

### Evidence: Fault Classifier Comparison

| Implementation | Rules | VFD? | LOC | Severity levels |
|----------------|-------|------|-----|-----------------|
| **pi-factory-cosmos** (winner) | 14 (E001, M001-M003, T001-T002, C001, P001, V001-V006) | YES | 449 | 4 (INFO/WARN/CRIT/EMERG) |
| factorylm/diagnosis/ | 10 (no V-codes) | NO | 389 | 4 |
| cookoff/diagnosis/ | 10 (identical to above) | NO | 389 | 4 |
| cookoff/net/diagnosis/fault_engine.py | 8 (F001-F008, different scheme) | NO | 262 | 3 |

### Evidence: VFD/Modbus Comparison

| Implementation | Language | LOC | Async? | Tests? | Scope |
|----------------|----------|-----|--------|--------|-------|
| **factorylm/services/plc-modbus** (PLC winner) | Python | ~686 | NO | 9 files, ~11k LOC | Client + Micro820 + FactoryIO |
| **pi-factory-cosmos/vfd_reader.py** (VFD winner) | Python | 229 | YES | NO | VFD registers only |
| cookoff/modbus_tag_source.py | Python | 198 | NO | YES | Micro 820 canonical map |
| cookoff/vfd_reader.py | Python | 155 | NO | YES | ATO GS10 specific |

---

## Q2: Repos to Archive Immediately

### Already Archived (confirm stay archived)
- nexus-cmms-recovery-point-2
- ProjectNexus
- Nexus
- Nexus1
- Nexus-backend

### New Archive Candidates (need Mike's approval)

| Repo | Reason | Risk |
|------|--------|------|
| voltron | Superseded by factorylm-cosmos-cookoff | None — cookoff is superset |
| factorylm-cmms | GitHub Issues experiment, superseded by apps/cmms/ | None — different approach, never shipped |
| jarvis-android-voice-proto | PowerShell prototype, no active development | None — prototype only |
| jarvis-core | Superseded by jarvis-unified | Low — check jarvis-unified has everything |

---

## Q3: Outcome Groups with Most Duplication

1. **Diagnose PLC/Factory Faults** — 3 independent fault classifiers, 3 Modbus readers
2. **Control PLC Hardware** — 3 Modbus implementations (sync, async, template-driven)
3. **Route Messages to AI** — openclaw standalone vs embedded copy, jarvis-core vs jarvis-unified
4. **Vision/Inspection** — belt_tachometer + frame_capture duplicated in 2 repos
5. **Manage Maintenance** — cmms fork in monolith, cmms experiment, 5 dead Nexus repos

---

## Q4: Fault Classifier — Winner

**pi-factory-cosmos** (`pifactory/simulator/fault_classifier.py`)

- 14 rules vs 10 in others
- Only one with VFD detection (V001-V006)
- Has `format_diagnosis_for_technician()` utility
- Belt vision cross-reference (V006: mistrack + high torque)
- FaultDiagnosis dataclass with `requires_safety_review` and `requires_maintenance` flags

---

## Q5: VFD/Modbus — Winners (both survive)

**For PLC communication**: `factorylm/services/plc-modbus/` (best tests, state models, control ops)

**For VFD-specific reads**: `pi-factory-cosmos/vfd_reader.py` (async, graceful degradation, configurable register map)

Different concerns. VFD reader gets added to monolith as new module alongside existing PLC code.

---

## Q6: Forks Safe to Delete

**Requires verification** — must check each fork for custom commits before deleting.

**VERIFIED** — 19 forks have 0 custom commits (safe to delete). 2 have custom work (keep).

**Safe to delete (19):**
- tailwindcss, ui, magicui, daisyui, motion, primitives, spectrum-ui, svelte-animations, galaxy, saasternity, tailwind-landing-page-template (11 UI)
- cal.com, n8n-docs (2 infra)
- exo (1 AI)
- ModbusTools, modbus-simulator, motulator (3 industrial — note: motulator embedded in monolith `simulation/`)
- antfarm (1 agent)
- langchain-crash-course (1 tutorial)

**Keep (have custom commits):**
- RealtimeSTT (1 custom commit)
- VideoAgent (1 custom commit)
```

---

## Q7: Repos That Stay Standalone (Do NOT Merge)

| Repo | Why |
|------|-----|
| openclaw | Deployed on VPS (100.68.120.99), separate lifecycle, systemd service |
| IndustrialSkillsHub + native | Separate product, different audience (technician training) |
| nautobot-docker-compose | Infrastructure tool, cluster health monitor |
| jarvis-unified | Personal AI OS, different domain |
| jarvis-for-gmail | Email automation product |
| clawdbot | Personal AI assistant |
| FactoryLM_OS | Obsidian vault (knowledge, not code) |
| factorylm-agent-space | Obsidian agent workspace |
| factorylm-landing | Marketing site |
| plc-copilot-landing | Marketing site |
| factorylm-conveyor-demo | Hardware docs (schematics, BOM, drawings) |
| JARVIS-IS-DEAD | Insurance backup — must stay frozen |
| RideView | Different domain (ride/bolt inspection) |
| ralph / My-Ralph / CodeBang / Archon / Agent-Factory / master-of-puppets-v2 / Backlog.md | Agent experiments, different audiences |
| Blog-writer-multi-agent | Content tool, standalone |
| remoteme-jarvis-node | MCP server for remote control |
| Thefuture / pai-config-windows / clawd / claudegen-coach | Personal AI config |
| frame_realtime_gemini_voicevision | AR glasses prototype |
| resurrected-tools | Utility collection |

---

## Execution Checklist

- [ ] Merge fault_classifier.py from pi-factory-cosmos into factorylm/diagnosis/
- [ ] Add vfd_reader.py (async) to factorylm services
- [ ] Merge belt_tachometer.py + frame_capture.py into factorylm/cosmos/
- [ ] Merge modbus_tag_source.py into factorylm services
- [ ] Merge vfd_conflicts.py into factorylm/diagnosis/
- [ ] Verify fork custom commits (script above)
- [ ] Archive: voltron, factorylm-cmms, jarvis-android-voice-proto, jarvis-core (with Mike approval)
- [ ] Delete verified-clean forks (with Mike approval)
- [ ] Update all YAML consolidation.status fields
- [ ] Update OUTCOMES.md with final decisions
