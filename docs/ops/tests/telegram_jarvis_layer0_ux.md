# Test Plan: Jarvis Telegram UX + Layer 0

**Branch:** `feat/jarvis-ux-and-layer0` (OpenClaw)
**Date:** 2026-02-17

---

## 1. Intent Routing Fixes

### 1.1 Casual questions no longer misroute to DIAGNOSE

| # | Telegram Message | Expected Intent | Expected Behavior |
|---|-----------------|----------------|-------------------|
| 1 | "why is the sky blue?" | CHAT | General chat answer, NOT diagnosis |
| 2 | "the error in my code" | CHAT | General chat, NOT diagnosis |
| 3 | "what's currently happening?" | CHAT | General chat, NOT status (removed "current") |
| 4 | "how to repair a bicycle?" | CHAT | General chat, NOT work_order (removed "repair") |

### 1.2 Factory questions still route correctly

| # | Telegram Message | Expected Intent | Expected Behavior |
|---|-----------------|----------------|-------------------|
| 5 | "why is the motor down?" | DIAGNOSE | Diagnosis with PLC tags |
| 6 | "fault alarm on line 3" | DIAGNOSE | Diagnosis (fault + alarm match) |
| 7 | "conveyor stopped unexpectedly" | DIAGNOSE | Diagnosis (conveyor + stopped) |
| 8 | "the compressor has an error" | DIAGNOSE | Diagnosis (compressor + error) |
| 9 | "what is the motor status?" | STATUS | PLC tag readout |
| 10 | "create a work order for pump repair" | WORK_ORDER | Work order creation |

### 1.3 DIAGRAM wins over ambiguous matches

| # | Telegram Message | Expected Intent |
|---|-----------------|----------------|
| 11 | "show me the wiring diagram" | DIAGRAM |
| 12 | "/wiring conveyor motor" | DIAGRAM |
| 13 | "draw the circuit schematic" | DIAGRAM |

### 1.4 Slash commands work

| # | Telegram Message | Expected Intent |
|---|-----------------|----------------|
| 14 | `/diagnose why is the motor hot?` | DIAGNOSE |
| 15 | `/status` | STATUS |
| 16 | `/gist research on VFD protocols` | GIST |
| 17 | `/project FastAPI PLC monitor` | PROJECT |
| 18 | `/diagram conveyor wiring` | DIAGRAM |
| 19 | `/search industrial IoT trends` | SEARCH |

---

## 2. Conversation Memory

### 2.1 Follow-up works within session

| # | Step | Telegram Message | Expected Behavior |
|---|------|-----------------|-------------------|
| 20 | 1 | "what faults can you detect?" | Lists fault codes (E001, M001, etc.) |
| 21 | 2 | "tell me more about the first one" | Jarvis knows "first one" = E001 from history |
| 22 | 3 | "and the second?" | Jarvis knows "second" = M001 from history |

### 2.2 Memory has TTL

| # | Step | Action | Expected Behavior |
|---|------|--------|-------------------|
| 23 | 1 | Send "what is E001?" | Normal response |
| 24 | 2 | Wait 31 minutes | History expires |
| 25 | 3 | Send "tell me more" | Jarvis does NOT reference E001, asks for clarification |

### 2.3 /clear flushes history

| # | Step | Telegram Message | Expected Behavior |
|---|------|-----------------|-------------------|
| 26 | 1 | "explain conveyor jams" | Explanation of C001 |
| 27 | 2 | `/clear` | "Conversation history cleared." |
| 28 | 3 | "tell me more" | No context — generic or asks for topic |

### 2.4 Memory is per-user

| # | Step | Action | Expected Behavior |
|---|------|--------|-------------------|
| 29 | 1 | User A sends "what is E001?" | E-stop explanation |
| 30 | 2 | User B sends "tell me more" | User B has no history — asks for topic |

---

## 3. Layer 0 (KB Direct) Short-Circuit

### 3.1 ChatSkill Layer 0 hit

**Precondition:** KB contains a `procedure` or `troubleshooting` atom with steps/fixes and score > 0.85 for the query.

| # | Telegram Message | Expected Behavior |
|---|-----------------|-------------------|
| 31 | "how to reset e-stop?" | Direct KB answer with steps, tagged `_Layer 0 (KB direct) | 0ms_` |
| 32 | (same query) | Response includes `**Sources:**` block with linked titles |
| 33 | (same query) | NO LLM call in logs (check journalctl) |

### 3.2 ChatSkill falls through to LLM

**Precondition:** KB has no high-confidence procedural match.

| # | Telegram Message | Expected Behavior |
|---|-----------------|-------------------|
| 34 | "what's the weather like?" | LLM response, no Layer 0 tag |
| 35 | "tell me a joke" | LLM response, no Sources block (no KB match) |

### 3.3 DiagnoseSkill Layer 0 hit

**Precondition:** PLC tags show e-stop active (e_stop=1) AND KB has actionable atom for E001.

| # | Telegram Message | Expected Behavior |
|---|-----------------|-------------------|
| 36 | "why is everything stopped?" | Fault summary header (`!!! E001: Emergency Stop Active`) + KB answer + Sources + `_Layer 0 (KB direct) | 0ms_` |
| 37 | (same) | NO LLM call (check journalctl) |

### 3.4 DiagnoseSkill falls through to LLM

**Precondition:** PLC tags show motor overcurrent but KB has no actionable atom for M001.

| # | Telegram Message | Expected Behavior |
|---|-----------------|-------------------|
| 38 | "why is the motor drawing too much current?" | LLM diagnosis with model tag, Sources block if KB had partial matches |

---

## 4. Source Attribution

### 4.1 Sources always deterministic

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 39 | KB match with `source_url` | `**Sources:**` block with `[Title](url)` markdown links |
| 40 | KB match without `source_url` | `**Sources:**` block with plain titles |
| 41 | No KB match | No Sources block |
| 42 | Layer 0 hit | Sources block present with KB atom sources |

---

## 5. Typing Indicator

| # | Step | Action | Expected Behavior |
|---|------|--------|-------------------|
| 43 | 1 | Send any message | "typing..." indicator appears in Telegram immediately |
| 44 | 2 | Wait for response | Indicator disappears when response arrives |

---

## 6. Verification Commands

```bash
# Check 11 skills registered
journalctl -u openclaw -n 30 --no-pager | grep "Skills:"

# Health check
curl -s http://localhost:8340/ | python3 -m json.tool

# Watch logs during test
journalctl -u openclaw -f

# Check for Layer 0 hits (no LLM call logged)
journalctl -u openclaw --since "5 min ago" | grep -E "Layer 0|route.*DIAGNOSE|route.*CHAT"
```

---

## 7. Rollback

If any test fails critically:

```bash
# On VPS
cd /opt/openclaw
git checkout main
systemctl restart openclaw
journalctl -u openclaw -n 10 --no-pager
```

The branch changes are isolated. Main is unaffected until PR is merged.
