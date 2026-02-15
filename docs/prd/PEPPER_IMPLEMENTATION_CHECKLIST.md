# PEPPER Implementation Checklist

**Status:** Ready to Execute
**Total Phases:** 6
**Estimated Days:** 12

---

## Pre-Flight Checklist

- [ ] Read and understand PRD: `docs/prd/PEPPER_SYSTEM_PRD.md`
- [ ] Verify VPS access: `ssh root@100.68.120.99`
- [ ] Verify PLC laptop online: `curl http://100.72.2.99:8765/health`
- [ ] Verify Travel laptop online: `curl http://100.83.251.23:8765/health`
- [ ] Create new Telegram bots via @BotFather:
  - [ ] @PepperPrimeBot (private, God Mode)
  - [ ] @FactoryLMBot (public, Demo Mode)
- [ ] Add bot tokens to Doppler

---

## Phase 1: Foundation (Days 1-2)

### 1.1 Create Directory Structure

```bash
mkdir -p services/telegram/pepper/{tools,personas,intelligence,scripts}
touch services/telegram/pepper/__init__.py
```

- [ ] Create `services/telegram/pepper/` directory
- [ ] Create subdirectories: `tools/`, `personas/`, `intelligence/`, `scripts/`
- [ ] Create `__init__.py` files

### 1.2 Core Files

| File | Description | Status |
|------|-------------|--------|
| `gateway.py` | Main entry point, Telegram bot setup | [ ] |
| `modes.py` | UserMode enum, get_user_mode(), mode configs | [ ] |
| `node_router.py` | NodeRouter class, node definitions | [ ] |
| `config.yaml` | Bot tokens, node URLs, model settings | [ ] |
| `requirements.txt` | Dependencies | [ ] |

### 1.3 Acceptance Tests

- [ ] `pytest test_phase1.py::test_god_mode_detection` — Mike's ID returns GOD
- [ ] `pytest test_phase1.py::test_demo_mode_detection` — Other IDs return DEMO
- [ ] `pytest test_phase1.py::test_blocked_detection` — Blocked IDs return BLOCKED
- [ ] Manual: Message @PepperPrimeBot → Responds as Pepper Prime
- [ ] Manual: Message @FactoryLMBot → Responds as Pepper
- [ ] Manual: `/status` → Shows all nodes health

### 1.4 Deploy Phase 1

```bash
ssh root@100.68.120.99 "cd /root/jarvis-workspace/factorylm-dev && git pull"
ssh root@100.68.120.99 "systemctl restart pepper"
```

- [ ] Push to branch `feat/pepper-phase1`
- [ ] Test on VPS
- [ ] Merge to main

---

## Phase 2: God Mode (Days 3-4)

### 2.1 Tool Files

| File | Description | Status |
|------|-------------|--------|
| `tools/__init__.py` | Tool registry | [ ] |
| `tools/filesystem.py` | read_file, write_file, search_files | [ ] |
| `tools/shell.py` | execute_command, run_script | [ ] |
| `tools/database.py` | query, insert, update, delete | [ ] |
| `tools/plc.py` | read_tags, write_tags, inject_fault | [ ] |
| `tools/git.py` | status, commit, push, deploy | [ ] |
| `tools/n8n.py` | list_workflows, trigger, debug | [ ] |
| `audit.py` | log_action, get_audit_trail | [ ] |
| `god_mode.py` | GodModeOrchestrator class | [ ] |

### 2.2 Integration Tests

- [ ] Shell command on PLC laptop works
- [ ] Shell command on Travel laptop works
- [ ] Shell command on VPS works
- [ ] File read from any node works
- [ ] File write with confirmation works
- [ ] Database query works
- [ ] All actions logged to audit trail

### 2.3 Acceptance Tests

- [ ] Mike: "Run `ls -la` on PLC laptop" → Returns directory listing
- [ ] Mike: "Read /etc/hostname on VPS" → Returns hostname
- [ ] Mike: "Show me yesterday's error logs" → Returns formatted logs
- [ ] Mike: "Deploy latest changes" → Prompts for confirmation, deploys
- [ ] Audit log contains all actions

---

## Phase 3: Demo Mode (Days 5-6)

### 3.1 Guardrail Files

| File | Description | Status |
|------|-------------|--------|
| `guardrails.py` | GuardrailEngine, permission checks | [ ] |
| `demo_mode.py` | DemoModeOrchestrator class | [ ] |
| `escalation.py` | escalate_to_mike, tier_routing | [ ] |
| `tools/equipment.py` | read_status, read_faults (assigned only) | [ ] |
| `tools/diagnosis.py` | diagnose_fault, get_procedures | [ ] |
| `tools/knowledge.py` | search_kb, get_manual | [ ] |
| `tools/work_orders.py` | create, update, close (own only) | [ ] |

### 3.2 Guardrail Tests

- [ ] Demo user: "Run `ls -la`" → BLOCKED with friendly message
- [ ] Demo user: "Read /etc/passwd" → BLOCKED with friendly message
- [ ] Demo user: "Show me other users" → BLOCKED
- [ ] Demo user: "Write to PLC" → BLOCKED with work order suggestion
- [ ] Rate limit triggers after 100 actions/hour

### 3.3 Acceptance Tests

- [ ] Demo user: "What's wrong with conveyor 3?" → AI diagnosis
- [ ] Demo user: "Show me the VFD manual" → Returns manual section
- [ ] Demo user: "Create work order for motor inspection" → Creates WO
- [ ] Demo user: "Escalate this to Mike" → Notifies Mike
- [ ] Demo user: "I need shell access" → Friendly refusal + escalation offer

---

## Phase 4: Persona System (Days 7-8)

### 4.1 Persona Files

| File | Description | Status |
|------|-------------|--------|
| `personas/SOUL_GOD.md` | God mode personality definition | [ ] |
| `personas/SOUL_DEMO.md` | Demo mode personality definition | [ ] |
| `personas/loader.py` | load_persona, build_system_prompt | [ ] |
| `formatters.py` | format_response, apply_output_law | [ ] |

### 4.2 Persona Tests

- [ ] God Mode responses are casual, direct, can push back
- [ ] Demo Mode responses are professional, helpful, patient
- [ ] Technical jargon filtered in Demo Mode
- [ ] Raw JSON never sent to user (OUTPUT FORMAT LAW)
- [ ] Persona consistent across multi-turn conversation

### 4.3 Acceptance Tests

- [ ] Mike: "That's a bad idea" → Pepper Prime challenges it
- [ ] Demo: Same input → Pepper offers alternative politely
- [ ] Mike: "Show raw JSON" → Returns JSON (allowed)
- [ ] Demo: "Show raw JSON" → Returns plain English summary

---

## Phase 5: Intelligence Layer (Days 9-10)

### 5.1 Intelligence Files

| File | Description | Status |
|------|-------------|--------|
| `intelligence/__init__.py` | IntelligenceRouter | [ ] |
| `intelligence/router.py` | route_query, layer selection | [ ] |
| `intelligence/layer0_kb.py` | KnowledgeBase search | [ ] |
| `intelligence/layer1_edge.py` | Edge LLM (stub for future) | [ ] |
| `intelligence/layer2_local.py` | Groq integration | [ ] |
| `intelligence/layer3_cloud.py` | Claude fallback | [ ] |
| `metrics.py` | track_layer_usage, get_stats | [ ] |

### 5.2 Layer Tests

- [ ] Known question → Layer 0 returns instant answer
- [ ] Common fault code → Layer 0 or 2
- [ ] Novel question → Layer 2 (Groq) or Layer 3 (Claude)
- [ ] Groq failure → Falls back to Claude
- [ ] Claude failure → Returns helpful error
- [ ] Metrics track queries per layer

### 5.3 Acceptance Tests

- [ ] "What does fault code E-001 mean?" → Instant from KB
- [ ] "Why did the conveyor stop?" → AI diagnosis (Layer 2/3)
- [ ] Groq API down → Claude handles gracefully
- [ ] `/stats` shows layer distribution

---

## Phase 6: Polish & Deploy (Days 11-12)

### 6.1 Deployment Files

| File | Description | Status |
|------|-------------|--------|
| `Dockerfile` | Container image | [ ] |
| `docker-compose.yaml` | Container orchestration | [ ] |
| `pepper.service` | Systemd unit file | [ ] |
| `scripts/deploy.sh` | Deployment script | [ ] |
| `scripts/health.sh` | Health check script | [ ] |
| `scripts/rollback.sh` | Rollback script | [ ] |
| `README.md` | Documentation | [ ] |

### 6.2 Watchdog System (See PEPPER_WATCHDOG_SPEC.md)

| File | Description | Status |
|------|-------------|--------|
| `watchdog/__init__.py` | Watchdog package | [ ] |
| `watchdog/main.py` | Main watchdog service | [ ] |
| `watchdog/health_checker.py` | Node/service health checks | [ ] |
| `watchdog/drift_detector.py` | Config drift detection | [ ] |
| `watchdog/api_validator.py` | API key validation | [ ] |
| `watchdog/fingerprint.py` | System structural fingerprint | [ ] |
| `watchdog/recovery.py` | Auto-recovery actions | [ ] |
| `watchdog/alerts.py` | Alert routing engine | [ ] |
| `watchdog.yaml` | Watchdog configuration | [ ] |
| `pepper-watchdog.service` | Systemd unit file | [ ] |

### 6.3 Watchdog Acceptance Tests

- [ ] Health check detects node down → Alert sent
- [ ] Config change detected → Backup + Alert
- [ ] API key invalid → Alert sent
- [ ] Service crash → Auto-restart + Alert
- [ ] Daily digest sent at 8 AM
- [ ] Baseline can be reset after intentional changes

### 6.4 Versioning & Rollback (See PEPPER_VERSIONING_ROLLBACK.md)

| File | Description | Status |
|------|-------------|--------|
| `deploy/__init__.py` | Deploy package | [ ] |
| `deploy/deploy.py` | Version deployer class | [ ] |
| `deploy/state.py` | State snapshot/restore | [ ] |
| `deploy/cli.py` | CLI commands | [ ] |
| `/usr/local/bin/pepper` | CLI wrapper | [ ] |

### 6.5 Versioning Acceptance Tests

- [ ] `pepper deploy --dry-run` → Shows preview, no changes
- [ ] `pepper deploy` → Creates version, deploys, health checks
- [ ] `pepper rollback` → Reverts to previous in <30s
- [ ] `pepper rollback v1.0.0` → Reverts to specific version
- [ ] `pepper rollback --list` → Shows all available versions
- [ ] Failed health check → Auto-rollback triggered
- [ ] Version manifest contains git commit, hash, changelog
- [ ] Emergency manual rollback via symlinks works

### 6.6 Observability

- [ ] Logs ship to Axiom
- [ ] Traces ship to Honeycomb
- [ ] Heartbeat every 2h to Mike
- [ ] Alert on crash/restart
- [ ] Dashboard for layer metrics

### 6.3 Migration

- [ ] Stop old bots: `systemctl stop clawdbot factorylm-telegram`
- [ ] Deploy PEPPER: `systemctl enable --now pepper`
- [ ] Verify God Mode works
- [ ] Verify Demo Mode works
- [ ] Archive old bot code
- [ ] Update documentation

### 6.4 Demo Day Readiness (Feb 10)

- [ ] End-to-end demo script tested
- [ ] Backup plan if primary fails
- [ ] Mike has both bot links ready
- [ ] Customer demo user whitelisted
- [ ] Response time <3s verified

---

## Post-Launch Tasks

- [ ] Monitor first 24h of logs
- [ ] Address any guardrail gaps
- [ ] Capture common queries for Layer 0
- [ ] Gather customer feedback
- [ ] Plan v1.1 improvements

---

## Quick Commands Reference

```bash
# Deploy to VPS
ssh root@100.68.120.99 "cd /root/jarvis-workspace/factorylm-dev && git pull && systemctl restart pepper"

# View logs
ssh root@100.68.120.99 "journalctl -u pepper -f"

# Check status
ssh root@100.68.120.99 "systemctl status pepper"

# Test God Mode
curl -X POST "http://100.68.120.99:18789/test" -d '{"user_id": 8445149012, "message": "test"}'

# Test Demo Mode
curl -X POST "http://100.68.120.99:18789/test" -d '{"user_id": 123456789, "message": "test"}'
```

---

## Sign-Off

| Phase | Completed | Verified By | Date |
|-------|-----------|-------------|------|
| Phase 1: Foundation | [ ] | ________ | ____ |
| Phase 2: God Mode | [ ] | ________ | ____ |
| Phase 3: Demo Mode | [ ] | ________ | ____ |
| Phase 4: Persona | [ ] | ________ | ____ |
| Phase 5: Intelligence | [ ] | ________ | ____ |
| Phase 6: Deploy | [ ] | ________ | ____ |
| **PRODUCTION READY** | [ ] | Mike | ____ |

---

*Checklist v1.0 | PEPPER System Implementation*
