# FactoryLM Evidence & Metrics Template

Before/after metrics framework for pilot deployments. Fill in baseline during factory onboarding, measure after 30/60/90 days.

---

## Pilot Measurement Plan

### Phase 0: Baseline (Week 1)

Measure these KPIs for 1 week before deploying FactoryLM agents:

| Metric | Baseline Value | Measurement Method |
|--------|---------------|-------------------|
| Mean Time to Detect (MTTD) | ___ min | Time from fault occurrence to first human awareness |
| Mean Time to Dispatch (MTTDi) | ___ min | Time from detection to tech on-site |
| Mean Time to Repair (MTTR) | ___ min | Time from dispatch to resolution |
| Mean Time Between Failures (MTBF) | ___ hours | Total run hours / failure count |
| OEE | ___% | Availability x Performance x Quality |
| Maintenance Cost per Device | $___/mo | Total maintenance spend / device count |
| Work Orders per Week | ___ | Manual count |
| Unplanned Downtime | ___ min/week | From PLC logs or shift reports |
| Technician Utilization | ___% | Wrench time / total shift hours |
| First-Time Fix Rate | ___% | Repairs resolved on first visit |

### Phase 1: Deploy + Measure (Days 1-30)

Deploy FactoryLM agents on target devices. Measure same KPIs weekly.

**Expected improvements (conservative):**

| Metric | Target Improvement | Mechanism |
|--------|-------------------|-----------|
| MTTD | 90% reduction | Alarm monitor detects in seconds vs manual rounds |
| MTTDi | 80% reduction | Auto-dispatch vs phone tree |
| MTTR | 20-30% reduction | Diagnosis + KB context sent with work order |
| First-Time Fix Rate | +15pp | Playbook cards guide correct repair |
| Work Orders (manual entry) | 100% reduction | Auto-generated CMMS Gist work orders |

### Phase 2: Learning Effect (Days 31-60)

As episodic memory grows, measure:

| Metric | Expected Trend | Why |
|--------|---------------|-----|
| Triage accuracy | Increasing | More similar incidents in KB |
| MTTR | Decreasing | Better diagnosis from playbook cards |
| Repeat faults | Decreasing | Preventive recommendations acted on |
| Playbook cards generated | Growing | System learning from resolutions |

### Phase 3: Steady State (Days 61-90)

| Metric | Target | Measurement |
|--------|--------|-------------|
| OEE improvement | +5-10pp | Compared to baseline |
| Maintenance cost reduction | 15-30% | Monthly spend comparison |
| Agent autonomy rate | >80% | % of faults handled without human intervention |
| Playbook → Layer 0 candidates | >5 cards | Cards with confidence > 0.95 |

---

## Before/After Summary Template

Use this template in pitch materials and customer reports:

```
BEFORE FactoryLM                    AFTER FactoryLM (90 days)
─────────────────                   ─────────────────────────
MTTD: 45 min (manual rounds)   →   MTTD: <1 min (auto-detect)
MTTDi: 30 min (phone tree)     →   MTTDi: <1 min (auto-dispatch)
MTTR: 90 min (guessing)        →   MTTR: 60 min (guided diagnosis)
First-time fix: 65%            →   First-time fix: 80%
WO data entry: 15 min/order    →   WO data entry: 0 min (auto)
Unplanned downtime: 8 hr/wk    →   Unplanned downtime: 4 hr/wk
OEE: 65%                       →   OEE: 75%
Monthly cost: $X               →   Monthly cost: $X - 25%
```

---

## Existing Evidence (Pre-Pilot)

From FactoryLM development and testing:

| Evidence | Value | Source |
|----------|-------|--------|
| Micro820 Modbus TCP integration | Working | Verified on PLC Laptop |
| Fault detection latency | <5 seconds | Matrix API polling interval |
| Work order generation | Automated | Feature 002, CMMS Gist |
| Agent pipeline definition | 3 workflows, 13 agents | Antfarm YAML specs |
| Development velocity | 9,554 messages in 9 days | Clawdbot conversation logs |
| Edge device | v2.0 deployed | Auto-network detection |
| Human-AI collaboration | Documented | Full conversation history |
| Memory architecture | 5-layer spec | pgvector schemas defined |

---

## ROI Calculator

For a facility with N devices at $30/device/month:

```
Monthly FactoryLM cost:     N x $30
Monthly maintenance savings: N x $30 x (reduction% / 30%)

Break-even:  When reduction% >= 30% of per-device maintenance cost
             Typical: $100-500/device/month maintenance spend
             So $30 = 6-30% of spend → break-even at ~10-15% reduction

Payback period: 3-6 months (conservative)
Annual ROI: 200-500% (based on $100-500 monthly spend per device)
```

---

## Metrics Collection Infrastructure

| Component | Status | Notes |
|-----------|--------|-------|
| PLC tag logging | Working | Via jarvis-local + Matrix API |
| Incident tracking | Working | Matrix API `/api/incidents` |
| Work order tracking | Working | CMMS Gist + `gh gist list` |
| Episode storage | Spec'd | pgvector schema defined, needs deployment |
| Weekly reporting | Spec'd | ops-reporter workflow defined |
| Dashboard | Future | Planned after pgvector deployment |
