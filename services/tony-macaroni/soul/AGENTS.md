# Sub-Agent Roster

## Active Agents

### ultron — Cloud Reasoning & Web Research

| Field | Value |
|-------|-------|
| **Instance ID** | `ultron` |
| **Bot Handle** | @UltronVPS_bot |
| **Host** | DigitalOcean VPS |
| **Tailscale IP** | 100.68.120.99 |
| **Config** | `/root/.openclaw/openclaw.json` |
| **Status** | Active |

**Capabilities:**
- Web research and document analysis
- Heavy reasoning and multi-step computation
- Cloud-based tasks that don't require local hardware
- Long-running background jobs

**Limitations:**
- No direct PLC/Modbus access
- No access to Mac Mini filesystem
- No SSH key from Mac Mini (Tailscale only)

---

### jarvis-local — PLC & Edge Compute

| Field | Value |
|-------|-------|
| **Instance ID** | `jarvis-local` |
| **Bot Handle** | @TravelLaptop_bot |
| **Host** | PLC Laptop (Travel Laptop) |
| **Tailscale IP** | 100.83.251.23 |
| **Local User** | `hharp` (not mike) |
| **Config** | `C:\Users\hharp\.openclaw\openclaw.json` |
| **Status** | Active |

**Capabilities:**
- Modbus TCP to Micro820 PLC (192.168.1.100:502) — VERIFIED WORKING
- Read/write PLC registers (holding registers, coils, input status)
- Edge compute on local factory network
- Jarvis Node running on :8765

**Limitations:**
- Windows machine — command syntax differs
- On factory floor network — may have intermittent connectivity
- PLC operations are safety-critical — always confirm before writes

---

### hetzner — Batch Compute (Future)

| Field | Value |
|-------|-------|
| **Instance ID** | `hetzner` |
| **Bot Handle** | _(pending — needs bot creation)_ |
| **Host** | Hetzner dedicated server |
| **Tailscale IP** | 100.67.25.53 |
| **Public IP** | 46.225.103.156 |
| **Status** | Fresh — needs full clawdbot install |

**Planned Capabilities:**
- Batch compute and large model inference
- Training runs
- Heavy data processing
- Backup/redundancy for ultron

---

## Decommissioning

### jarvis-legacy — Hostinger (Retiring)

| Field | Value |
|-------|-------|
| **Instance ID** | `jarvis-legacy` |
| **Host** | Hostinger (72.60.175.144) |
| **Status** | Decommissioning — migrate remaining duties to Tony/ultron |

---

## Other Bots (Not Clawdbot)

These are standalone Python/Node bots, not part of the clawdbot swarm. Tony should NOT delegate to them via the swarm protocol.

| Bot | Handle | Purpose |
|-----|--------|---------|
| Gus | @FactoryLM_bot | Factory floor Python bot |
| FRIDAY | @FRIDAY_MCU_bot | Dev companion |
| RemoteMe | @JarvisMIO_bot | PLC Copilot / VPS heartbeat |
| Pepper | @Spicyclawd_bot | God-mode pepper service (Doppler-managed) |
| RivetCMMS | @RivetCMMS_bot | **DEPRECATED** |

---

## Factory Agent Workflows (Antfarm)

Tony delegates to these autonomous workflows via antfarm triggers. Defined in `factorylm/antfarm/workflows/`.

### maintenance-dispatcher — Alarm → Dispatch → Resolution

| Field | Value |
|-------|-------|
| **Workflow ID** | `maintenance-dispatcher` |
| **Location** | `antfarm/workflows/maintenance-dispatcher/workflow.yml` |
| **Trigger** | PLC fault (poll/webhook) or `/dispatch` command |
| **Agents** | alarm-monitor → triager → wo-creator → dispatcher → followup |
| **Status** | Defined — awaiting antfarm CLI install |

**Pipeline:** Detects PLC alarms via jarvis-local, triages against KB (pgvector), creates CMMS Gist work order, dispatches tech via Telegram (Gus), tracks resolution and stores episode for learning.

**Integration:** Matrix API, jarvis-local (Modbus TCP), CMMS Gist (Feature 002), Telegram (@FactoryLM_bot).

---

### robot-advisor — Robot Program Change Safety Review

| Field | Value |
|-------|-------|
| **Workflow ID** | `robot-advisor` |
| **Location** | `antfarm/workflows/robot-advisor/workflow.yml` |
| **Trigger** | `/robot-review` command or webhook |
| **Agents** | change-analyzer → safety-checker → diff-generator → reviewer |
| **Status** | Defined — awaiting antfarm CLI install |

**Pipeline:** Analyzes robot program changes, checks safety envelopes (speed, payload, zones, I/O), generates annotated diffs, and gates deployment with human approval for safety-critical changes.

**Integration:** Telegram (@FactoryLM_bot) for escalation to Mike.

---

### ops-reporter — Weekly Operations Intelligence

| Field | Value |
|-------|-------|
| **Workflow ID** | `ops-reporter` |
| **Location** | `antfarm/workflows/ops-reporter/workflow.yml` |
| **Trigger** | Cron (Monday 6:00 AM ET) or `/ops report` command |
| **Agents** | data-collector → analyzer → report-writer → distributor |
| **Status** | Defined — awaiting antfarm CLI install |

**Pipeline:** Collects OEE/scrap/downtime data, identifies anomalies and trends, generates formatted markdown report, distributes via Telegram and archives as Gist.

**Integration:** Matrix API, jarvis-local, CMMS Gist, Telegram (@FactoryLM_bot).

---

## Delegation Quick Reference

```
Web search / research     → ultron (@UltronVPS_bot)
PLC register read/write   → jarvis-local (@TravelLaptop_bot)
Batch compute (future)    → hetzner (pending setup)
Alarm → dispatch pipeline → maintenance-dispatcher (antfarm)
Robot program review      → robot-advisor (antfarm)
Weekly ops report         → ops-reporter (antfarm)
Everything else           → Tony handles locally
```

## Mike Harper

- **Telegram User ID:** 8445149012
- **Schedule:** Night shift Tue-Fri 10PM-8:30AM ET, days off Sat/Sun/Mon
- Tony is the ONLY agent that communicates directly with Mike
