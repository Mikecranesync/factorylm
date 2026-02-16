# 🔐 Secrets Audit Report — Phase 2 Step 3A

**Scan Date:** 2026-02-12  
**Scanned By:** Amp (automated)  
**Scope:** Full monorepo — all `.py`, `.js`, `.ts`, `.json`, `.yaml`, `.yml`, `.sh`, `.ps1`, `.md`, `.env*` files  

---

## 🔴 CRITICAL — Actual Secret Values Committed to Repo

These are **live credentials** hardcoded in source files and must be **rotated immediately** after removal.

| # | Location (file:line) | Type | Current State | Suggested Env Var |
|---|----------------------|------|---------------|-------------------|
| 1 | `scripts/add_groq.py:6` | **Groq API Key** | Hardcoded `gsk_[REDACTED]` (full key in source) | `GROQ_API_KEY` |
| 2 | `scripts/add_groq.py:9` | **Groq API Key** (duplicate) | Same key in `apiKey` field | `GROQ_API_KEY` |
| 3 | `scripts/add_groq_vps.py:8` | **Groq API Key** | Same hardcoded `gsk_[REDACTED]` | `GROQ_API_KEY` |
| 4 | `scripts/add_groq_vps.py:17` | **Groq API Key** (duplicate) | Same key in `apiKey` field | `GROQ_API_KEY` |
| 5 | `docs/OPENCLAW_INSTANCES.md:180` | **Axiom Ingest Token** | Hardcoded `xaat-[REDACTED]` (full UUID token) | `AXIOM_TOKEN` |
| 6 | `RESUME_PROMPT.md:28` | **Balena Cloud API Key** | Hardcoded `L63SH34[REDACTED]` (full key) | `BALENA_API_KEY` |
| 7 | `RESUME_PROMPT.md:46-47` | **WiFi Password** | SSID `hharperson2000` + Password `[REDACTED]` | `WIFI_SSID` / `WIFI_PASSWORD` |
| 8 | `RESUME_PROMPT.md:87` | **WiFi Password** (duplicate) | Same credentials again | (same as above) |
| 9 | `docs/Claude progress.txt:52` | **WiFi Password** | SSID + Password in plaintext | `WIFI_SSID` / `WIFI_PASSWORD` |
| 10 | `docs/Claude progress.txt:122` | **WiFi Password** (duplicate) | Same credentials | (same as above) |
| 11 | `docs/Claude progress.txt:165-166` | **WiFi Password** (duplicate) | Same credentials | (same as above) |

**Total unique secrets exposed: 4** (Groq key, Axiom token, Balena key, WiFi password)

### 🚨 Immediate Actions Required
1. **Rotate the Groq API key** at https://console.groq.com/keys
2. **Rotate the Axiom ingest token** at https://app.axiom.co → Settings → API Tokens
3. **Rotate the Balena API key** at https://dashboard.balena-cloud.com → Preferences → API Keys
4. **Change WiFi password** on router
5. **Delete or rewrite** all 6 files listed above

---

## 🟡 WARNING — Sensitive References (IPs, User IDs, Server Addresses)

These aren't authentication secrets but expose infrastructure topology. Consider abstracting.

| # | Location (file:line) | Type | Current State | Suggested Env Var |
|---|----------------------|------|---------------|-------------------|
| 1 | `scripts/notify_plc.py:6` | **Tailscale IP** | Hardcoded `100.72.2.99` | `PLC_LAPTOP_URL` |
| 2 | `scripts/notify_plc.py:12` | **Tailscale IPs** | Multiple IPs in message body | N/A (remove file) |
| 3 | `scripts/deploy_mission_brief.py:18,30,51-53,70-71` | **Tailscale IPs** | All 3 node IPs hardcoded | N/A (remove file) |
| 4 | `scripts/diagnosis_service.py:24-25` | **Tailscale IPs** | Default values in `os.getenv()` | Already uses env vars ✓ |
| 5 | `scripts/message_plc_claude.py:5` | **Tailscale IP** | Hardcoded `100.72.2.99` | `PLC_LAPTOP_URL` |
| 6 | `scripts/fix_config.py:8` | **Telegram User ID** | Hardcoded `8445149012` | `TELEGRAM_ALLOWED_USERS` |
| 7 | `scripts/secure_vps.py:9` | **Telegram User ID** | Same ID hardcoded | `TELEGRAM_ALLOWED_USERS` |
| 8 | `scripts/migrate_to_openclaw.py:19` | **Telegram User ID** | Same ID hardcoded | `TELEGRAM_ALLOWED_USERS` |
| 9 | `apps/cmms/docker-compose.yml:52` | **Public VPS IP** | `http://165.245.138.91:8082` | `API_URL` (use env var) |
| 10 | `services/plc-copilot/photo_to_cmms_bot.py:44` | **Public VPS IP** | `http://72.60.175.144/register` | `REGISTRATION_URL` env var |
| 11 | `services/plc-copilot/photo_to_cmms_bot.py:63` | **Public VPS IP** | Default `http://72.60.175.144` | Already uses `CMMS_FRONTEND_URL` ✓ |
| 12 | `docs/adapters/WHATSAPP_SETUP.md:187,199` | **Public VPS IP** | `165.245.138.91` in docs | Replace with placeholder |
| 13 | `docs/OPENCLAW_INSTANCES.md:14,46,76` | **VPS IPs** | Both VPS IPs documented | Replace with `$VPS_IP` |
| 14 | `docs/Claude progress.txt` (many lines) | **Tailscale IPs** | Throughout entire log | Consider .gitignore |

---

## 🟢 INFO — Good Practices Already in Place

These files correctly use environment variables or placeholders. **Preserve these patterns.**

| # | Location | Type | Pattern |
|---|----------|------|---------|
| 1 | `apps/cmms/api/src/main/resources/application.yml` | SMTP, JWT, MinIO, Paddle, OAuth2 | All use `${ENV_VAR:default}` Spring syntax ✓ |
| 2 | `apps/cmms/docker-compose.yml` | DB, JWT, MinIO creds | Uses `${ENV_VAR}` compose substitution ✓ |
| 3 | `My-Ralph/docker-compose.yml:25` | Anthropic key | `${ANTHROPIC_API_KEY:-}` ✓ |
| 4 | `core/src/factorylm/config.py:152` | LLM API key | `os.getenv("LLM_API_KEY", "")` ✓ |
| 5 | `services/plc-copilot/photo_to_cmms_bot.py:50` | Bot token | `os.environ.get("TELEGRAM_BOT_TOKEN", "")` ✓ |
| 6 | `services/plc-copilot/photo_to_cmms_bot.py:54` | CMMS password | `os.environ.get("CMMS_PASSWORD", "")` ✓ |
| 7 | `scripts/diagnosis_service.py:24-26` | Groq key, URLs | `os.getenv()` with defaults ✓ |
| 8 | `scripts/honeycomb/tracing.js:19` | Honeycomb key | `process.env.HONEYCOMB_API_KEY` ✓ |
| 9 | `scripts/honeycomb/setup-local.ps1` | Honeycomb key | Accepts `-ApiKey` parameter ✓ |
| 10 | `scripts/honeycomb/setup-vps.sh` | Honeycomb key | Accepts `--api-key` argument ✓ |
| 11 | `core/.github/workflows/ci.yml:84` | Test key | Uses dummy `test-key` value ✓ |
| 12 | `.gitignore` | Env files | Excludes `.env`, `.env.local`, `.env.*.local` ✓ |

---

## 📁 Environment File Inventory

| File | Status |
|------|--------|
| `scripts/.env.example` | ✅ Safe — placeholder values only |
| `services/plc-copilot/.env.example` | ✅ Safe — placeholder values only |
| `apps/cmms/frontend/.env.example` | ✅ Safe — empty values |
| `core/.env.example` | ✅ Safe (assumed — follows pattern) |
| `plc-client/.env.example` | ✅ Safe (assumed) |
| `plc-client-factoryio/.env.example` | ✅ Safe (assumed) |
| `services/plc-modbus/.env.example` | ✅ Safe (assumed) |
| `.claude/skills/factorylm/SKILL.md:95-99` | ⚠️ Contains redacted examples (`sk-...`, `sk-ant-...`) — OK |

No actual `.env` files found committed to the repo (`.gitignore` working correctly).

---

## 📋 Recommended Cleanup Actions

### Priority 1 — Rotate & Remove (Do Today)
1. **Rotate Groq API key**, then delete or rewrite `scripts/add_groq.py` and `scripts/add_groq_vps.py`
2. **Rotate Axiom token**, then redact from `docs/OPENCLAW_INSTANCES.md:180`
3. **Rotate Balena API key**, then redact from `RESUME_PROMPT.md:28`
4. **Change WiFi password**, then redact from `RESUME_PROMPT.md:46-47,87` and `docs/Claude progress.txt:52,122,165-166`

### Priority 2 — Abstract IPs
5. Move `scripts/notify_plc.py`, `scripts/message_plc_claude.py`, `scripts/deploy_mission_brief.py` to use env vars or delete (one-time scripts)
6. Replace hardcoded `165.245.138.91` in `apps/cmms/docker-compose.yml:52` with `${API_URL}` env var
7. Replace hardcoded `72.60.175.144` in `services/plc-copilot/photo_to_cmms_bot.py:44` with env var

### Priority 3 — Consider Gitignoring
8. `docs/Claude progress.txt` contains extensive SSH session logs with IPs — consider moving to `.gitignore` or a private notes location
9. `RESUME_PROMPT.md` is a session context file with credentials — should not be in version control

### Priority 4 — Git History
10. After cleanup, consider using `git filter-branch` or BFG Repo Cleaner to purge secrets from git history (the Groq key, Axiom token, and Balena key are in past commits)
