# FactoryLM Project Memory Graph

## Last Updated: 2026-02-12

---

## Session Actions Log

### Session: 2026-02-12 (Evening) - Bot Fix + Hetzner VPS

**Actions Completed:**

1. **Claude Code CLI fixed @UltronVPS_bot** (parallel agent session)
   - Root cause: Groq TPM limit (12K) too low for 18K system prompt
   - Fix: Switched primary to `anthropic/claude-sonnet-4-20250514` (OAuth token, 280d validity)
   - Fixed invalid fallback `groq/qwen/qwen3-32b` → `groq/llama-3.1-8b-instant`
   - Restarted openclaw systemd service — bot is responding ✅

2. **New Hetzner VPS provisioned** — `46.225.103.156`
   - Fresh server, needs full setup (Node 22, pnpm, clawdbot, Tailscale)
   - Goal: consolidate all bots here, decommission DO + Hostinger

3. **Updated docs/OPENCLAW_INSTANCES.md**
   - Reflected ultron fix (Anthropic primary, Groq fallback)
   - Added Hetzner section with setup checklist
   - Renumbered sections

**Next Steps:**
- Set up Hetzner VPS (Node 22, pnpm, Tailscale, clawdbot)
- Merge 6 cleanup PRs to main
- Rotate leaked secrets (Groq key, Axiom token)
- Top up Google Cloud billing for Gemini fallback

---

### Session: 2026-02-12 - OpenClaw Infrastructure Debugging

**Actions Completed:**

1. **Diagnosed @UltronVPS_bot inbound issue**
   - Webhook was already deleted (not the cause)
   - Confirmed Telegram polling IS working (409 conflict proves it)
   - **ROOT CAUSE**: All 3 LLM providers failing:
     - `anthropic/claude-opus-4-5`: HTTP 429 rate limit (account limit, not key issue)
     - `anthropic/claude-sonnet-4-20250514`: Auth profiles in cooldown from Opus failure
     - `google/gemini-2.5-flash`: **Billing exhausted** — API key out of credits
   - Bot receives messages but can't generate responses

2. **Fixed VPS model configuration**
   - Changed primary from `claude-opus-4-5` → `claude-sonnet-4-20250514` (cheaper, higher rate limits)
   - Fallbacks: `gemini-2.5-flash`, `claude-opus-4-5`
   - Removed duplicate `GEMINI_API_KEY` env var (was conflicting with `GOOGLE_API_KEY`)
   - Restarted openclaw systemd service

3. **Created scripts/fix_vps_models.py** — VPS model config fix script

**⚠️ BLOCKING ISSUES (Mike must fix):**
- **Google API billing**: Key `AIzaSyBwC-7nCist26ERhr_4zSXjMIRg1nLXWTI` is out of credits → Top up at https://console.cloud.google.com/billing
- **Anthropic rate limits**: "Claude Code" workspace API key has low rate limits → Create key in default workspace at https://console.anthropic.com
- Until one of these is resolved, @UltronVPS_bot will fail to respond

**OpenClaw Infrastructure Status:**

| Instance | Bot | Status | Model | Issue |
|----------|-----|--------|-------|-------|
| Local (Windows) | @TravelLaptop_bot | ✅ Working | gemini-2.5-flash | None |
| VPS (DigitalOcean) | @UltronVPS_bot | ⚠️ Partial | claude-sonnet-4 | All providers billing/rate-limited |

**VPS Connection:**
- Tailscale IP: 100.68.120.99
- SSH: `ssh root@100.68.120.99`
- Service: `systemctl status openclaw`
- Logs: `/tmp/openclaw/openclaw-2026-02-12.log`
- Config: `/root/.openclaw/openclaw.json`

---

### Session: 2026-01-23 - Rivet-PRO Integration

**Actions Completed:**

1. **Explored FactoryLM Core** (`C:\Users\hharp\OneDrive\Desktop\FactoryLM\core`)
   - Status: Complete and production-ready
   - 148 tests passing
   - Providers implemented: GROQ, DeepSeek, Claude
   - Version: v1.0.0

2. **Investigated Rivet-PRO for misplaced FactoryLM work**
   - Confirmed: No FactoryLM work was done in Rivet-PRO
   - Rivet-PRO has its own LLM router at `rivet_pro/adapters/llm/router.py`
   - No feature branches for FactoryLM in Rivet-PRO

3. **Created My-Ralph Client in Rivet-PRO**
   - File: `rivet_pro/adapters/ralph/my_ralph_client.py`
   - HTTP client for My-Ralph API integration
   - Methods: `start_loop()`, `stop_loop()`, `get_status()`, `pause_loop()`, `resume_loop()`, `list_loops()`
   - Data classes: `RalphSession`, `LoopStatus`

4. **Updated Rivet-PRO Configuration**
   - File: `rivet_pro/config/settings.py`
   - Added settings:
     - `my_ralph_api_url`: `http://localhost:8000`
     - `my_ralph_enabled`: `True`
     - `my_ralph_timeout`: `30.0`
     - `factorylm_core_path`: Path to FactoryLM core

5. **Created Rivet-PRO Integration Documentation**
   - File: `docs/MY_RALPH_INTEGRATION.md`
   - Comprehensive guide for using My-Ralph with Rivet-PRO

6. **Updated Rivet-PRO CLAUDE.md**
   - Added "Related Projects" section
   - Documented FactoryLM Core location and purpose
   - Documented My-Ralph API endpoints and usage

7. **Committed and Pushed to Rivet-PRO**
   - Commit: `7661df6` - "feat: Add My-Ralph and FactoryLM integration"
   - Pushed to: `origin/main`

---

## Project Structure

```
FactoryLM/
├── core/                      # LLM Abstraction Layer (COMPLETE)
│   ├── factorylm/             # Main package
│   │   ├── clients/           # LLM provider clients
│   │   │   ├── groq.py        # GROQ client
│   │   │   ├── deepseek.py    # DeepSeek client
│   │   │   └── claude.py      # Claude/Anthropic client
│   │   └── config.py          # Configuration
│   └── tests/                 # 148 tests passing
│
├── My-Ralph/                  # Autonomous Development Loop API (COMPLETE)
│   ├── api/                   # FastAPI service
│   │   ├── main.py            # Entry point
│   │   ├── routes/            # API endpoints
│   │   └── services/          # Business logic
│   ├── lib/                   # Bash library modules
│   ├── tests/                 # 321 BATS + 34 pytest tests
│   ├── .claude/               # Claude Code settings
│   ├── .mcp.json              # MCP server config
│   └── CLAUDE.md              # Project guidance (31KB)
│
├── plc-client-factoryio/      # PLC Client (in progress)
├── docs/                      # Documentation
├── scripts/                   # Utility scripts
└── PRD-*.md                   # Product Requirements Documents
```

---

## Integration Map

### Rivet-PRO -> My-Ralph Integration

| Rivet-PRO Component | My-Ralph Endpoint | Purpose |
|---------------------|-------------------|---------|
| `MyRalphClient.start_loop()` | `POST /api/loop/start` | Start autonomous dev loop |
| `MyRalphClient.stop_loop()` | `POST /api/loop/stop/{id}` | Stop running loop |
| `MyRalphClient.get_status()` | `GET /api/loop/status/{id}` | Get loop status |
| `MyRalphClient.pause_loop()` | `POST /api/loop/pause/{id}` | Pause loop |
| `MyRalphClient.resume_loop()` | `POST /api/loop/resume/{id}` | Resume loop |
| `MyRalphClient.list_loops()` | `GET /api/loop/list` | List active loops |

### Settings Reference

```python
# Rivet-PRO settings.py
my_ralph_api_url = "http://localhost:8000"
my_ralph_enabled = True
my_ralph_timeout = 30.0
factorylm_core_path = "C:/Users/hharp/OneDrive/Desktop/FactoryLM/core"
```

---

## Pending Work

### FactoryLM Core
- Status: **COMPLETE** - No pending work

### My-Ralph
- Phase 1: **COMPLETE** (CLI Modernization)
- Phase 2: **NOT STARTED** (Agent SDK Integration)
  - #32 - Create Agent SDK proof of concept
  - #33 - Define custom tools for Agent SDK
  - #34 - Implement hybrid CLI/SDK architecture
- Phase 3: **NOT STARTED** (Configuration & Infrastructure)
  - #18 - Log rotation feature
  - #19 - Dry-run mode
  - #20 - Config file support (.ralphrc)

### PLC Client (plc-client-factoryio)
- Status: In progress
- PRD: `PRD-005_FactoryIO_Micro820_Integration.md`

---

## Related Projects

| Project | Location | Status | Integration |
|---------|----------|--------|-------------|
| **Rivet-PRO** | `C:\Users\hharp\OneDrive\Desktop\Rivet-PRO` | Production | Uses My-Ralph client |
| **FactoryLM Core** | `C:\Users\hharp\OneDrive\Desktop\FactoryLM\core` | Complete | Available for import |
| **My-Ralph** | `C:\Users\hharp\OneDrive\Desktop\FactoryLM\My-Ralph` | Complete | API at localhost:8000 |

---

## Quick Commands

### Start My-Ralph API
```bash
cd C:\Users\hharp\OneDrive\Desktop\FactoryLM\My-Ralph
python -m uvicorn api.main:app --reload --port 8000
```

### Verify My-Ralph Health
```bash
curl http://localhost:8000/health
```

### Use from Rivet-PRO
```python
from rivet_pro.adapters.ralph import MyRalphClient

async with MyRalphClient() as client:
    session = await client.start_loop(
        project_path="C:/path/to/project",
        rate_limit=100
    )
```

---

## Git Status

### Rivet-PRO Repository
- Branch: `main`
- Latest commit: `7661df6` - "feat: Add My-Ralph and FactoryLM integration"
- Remote: `https://github.com/Mikecranesync/Rivet-PRO.git`
- Status: Pushed and up-to-date

### My-Ralph Repository
- Version: v1.0.1
- Tests: 321 BATS + 34 pytest (100% pass rate)
- Remote: `https://github.com/Mikecranesync/My-Ralph`

---

## Resume Instructions

To continue work after restart:

1. **Start My-Ralph API** (if needed):
   ```bash
   cd C:\Users\hharp\OneDrive\Desktop\FactoryLM\My-Ralph
   python -m uvicorn api.main:app --reload
   ```

2. **Check this file** for pending work and session context

3. **Read project-specific RESUME_PROMPT.md** files:
   - My-Ralph: `My-Ralph/RESUME_PROMPT.md`

4. **Verify integrations**:
   ```bash
   # Check Rivet-PRO has My-Ralph client
   ls C:\Users\hharp\OneDrive\Desktop\Rivet-PRO\rivet_pro\adapters\ralph\
   ```
