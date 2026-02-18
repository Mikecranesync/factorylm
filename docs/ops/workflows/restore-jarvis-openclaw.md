# WF-006: Restore Jarvis Soul into Python OpenClaw

| Field | Value |
|-------|-------|
| **ID** | WF-006 |
| **Created** | 2026-02-16 |
| **Last Verified** | 2026-02-16 |
| **Status** | verified |
| **Services** | openclaw |
| **Devices** | vps |
| **Est. Duration** | 15m |

---

## Purpose

Restore the Jarvis personality, routing config, and message chunking into the Python OpenClaw service after a fresh deploy or config reset. Run this whenever OpenClaw is redeployed with default/generic settings.

## Prerequisites

- [ ] SSH access to VPS (100.68.120.99)
- [ ] OpenClaw systemd service exists (`/etc/systemd/system/openclaw.service`)
- [ ] Doppler configured with `openclaw` project / `dev_bot` config
- [ ] ANTHROPIC_API_KEY in Doppler (optional — Groq fallback works without it)

## Steps

### 1. Update system prompt with Jarvis identity

- **Device**: VPS
- **File**: `/opt/openclaw/openclaw/llm/prompts.py`
- **Change**: Replace generic "OpenClaw" system prompt with Jarvis personality
- **Verify**: `grep "Jarvis" /opt/openclaw/openclaw/llm/prompts.py`

### 2. Fix Telegram message chunking

- **Device**: VPS
- **File**: `/opt/openclaw/openclaw/gateway/telegram.py`
- **Change**: Add `_chunk_text()` helper and update `_reply()` to chunk long messages
- **Verify**: `grep "_chunk_text" /opt/openclaw/openclaw/gateway/telegram.py`

### 3. Update routing table

- **Device**: VPS
- **File**: `/opt/openclaw/openclaw/llm/router.py`
- **Change**: Set Anthropic as primary for DIAGNOSE/WORK_ORDER, Groq for everything else
- **Verify**: `grep "anthropic" /opt/openclaw/openclaw/llm/router.py`

### 4. Add Anthropic budget limits

- **Device**: VPS
- **Files**: `/opt/openclaw/openclaw/config.py`, `/opt/openclaw/openclaw/app.py`
- **Change**: Add `anthropic_daily_request_limit=100` and `anthropic_daily_token_limit=100000`
- **Verify**: `grep "anthropic_daily" /opt/openclaw/openclaw/config.py`

### 5. Update openclaw.yaml

- **Device**: VPS
- **File**: `/opt/openclaw/openclaw.yaml`
- **Change**: Add Anthropic model/limits, matrix_url, jarvis_hosts
- **Verify**: `cat /opt/openclaw/openclaw.yaml`

### 6. Add ANTHROPIC_API_KEY to Doppler (manual)

- **Device**: VPS
- **Command**:
  ```bash
  doppler secrets set ANTHROPIC_API_KEY "sk-ant-..." --project openclaw --config dev_bot
  ```
- **Verify**: `doppler secrets get ANTHROPIC_API_KEY --project openclaw --config dev_bot`

### 7. Restart service

- **Device**: VPS
- **Command**:
  ```bash
  systemctl restart openclaw
  ```
- **Expected Output**: `active (running)` in status
- **Verify**: `systemctl status openclaw --no-pager`

## Verification

```bash
# Check service is running
systemctl status openclaw --no-pager

# Check providers are active
curl -s http://localhost:8340/ | python3 -m json.tool

# Check logs for clean startup
journalctl -u openclaw -n 10 --no-pager

# Check budget endpoint
curl -s http://localhost:8340/budget | python3 -m json.tool
```

## Rollback

1. Restore original files from git: `cd /opt/openclaw && git checkout -- .`
2. Restart: `systemctl restart openclaw`

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| "Message is too long" in logs | Missing _chunk_text in telegram.py | Re-apply Step 2 |
| Only groq+gemini in providers | ANTHROPIC_API_KEY not in Doppler | Run Step 6 |
| Generic "OpenClaw" personality | prompts.py not updated | Re-apply Step 1 |
| Service won't start | Syntax error in edited file | Check `journalctl -u openclaw -n 50` |

## Decomposition

| Task | Can Automate | Notes |
|------|-------------|-------|
| Edit Python files on VPS | yes | SSH + heredoc writes |
| Edit YAML config | yes | SSH + heredoc writes |
| Add Doppler secret | no | Requires API key value |
| Restart service | yes | `systemctl restart openclaw` |
| Verify health | yes | `curl + jq` |

## History

| Date | Change | Trace |
|------|--------|-------|
| 2026-02-16 | Initial creation | [TRC-2026-02-16-001](../traces/2026-02-16_jarvis-soul-restore.md) |
