# WF-001: Deploy PLC Copilot

| Field | Value |
|-------|-------|
| **ID** | WF-001 |
| **Created** | 2026-02-16 |
| **Last Verified** | 2026-02-16 |
| **Status** | draft |
| **Services** | plc-copilot |
| **Devices** | vps |
| **Est. Duration** | 5m |

---

## Purpose

Deploy or update the PLC Copilot Telegram bot on the VPS (Jarvis, 100.68.120.99). Run this after merging fixes or features to the bot.

## Prerequisites

- [ ] SSH access to VPS (100.68.120.99) via Tailscale
- [ ] Docker installed on VPS
- [ ] Environment variables configured on VPS: `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `CMMS_BASE_URL`, `CMMS_EMAIL`, `CMMS_PASSWORD`
- [ ] Changes merged to target branch

## Steps

### 1. SSH into VPS

- **Device**: travel-laptop
- **Command**:
  ```bash
  ssh hharp@100.68.120.99
  ```
- **Expected Output**: shell prompt on VPS
- **Verify**: `hostname` returns VPS hostname

### 2. Navigate to repo and pull latest

- **Device**: vps
- **Command**:
  ```bash
  cd ~/factorylm-monorepo && git pull
  ```
- **Expected Output**: updated files listed, or "Already up to date."
- **Verify**: `git log -1 --oneline` shows expected commit

### 3. Rebuild Docker image

- **Device**: vps
- **Command**:
  ```bash
  cd services/plc-copilot && docker build -t plc-copilot .
  ```
- **Expected Output**: `Successfully built <hash>` and `Successfully tagged plc-copilot:latest`
- **Verify**: `docker images plc-copilot` shows recent image

### 4. Stop existing container

- **Device**: vps
- **Command**:
  ```bash
  docker stop plc-copilot-bot 2>/dev/null; docker rm plc-copilot-bot 2>/dev/null
  ```
- **Expected Output**: container name or "Error: No such container" (both OK)
- **Verify**: `docker ps --filter name=plc-copilot-bot` returns empty

### 5. Start new container

- **Device**: vps
- **Command**:
  ```bash
  docker run -d --name plc-copilot-bot \
    --restart unless-stopped \
    --env-file ~/plc-copilot.env \
    -v /var/log/plc-copilot:/var/log/plc-copilot \
    plc-copilot
  ```
- **Expected Output**: container ID hash
- **Verify**: `docker ps --filter name=plc-copilot-bot` shows running container

### 6. Check logs for startup

- **Device**: vps
- **Command**:
  ```bash
  docker logs -f --tail 20 plc-copilot-bot
  ```
- **Expected Output**: startup messages, no errors. Look for "Application started" or similar.
- **Verify**: no `ERROR` or `CRITICAL` lines in output

## Verification

Send `/health` to the bot in Telegram. It should respond with status information.

```bash
# Alternative: check container health
docker ps --filter name=plc-copilot-bot --format '{{.Status}}'
```

## Rollback

1. Stop the new container:
   ```bash
   docker stop plc-copilot-bot && docker rm plc-copilot-bot
   ```
2. Revert to previous commit on VPS:
   ```bash
   cd ~/factorylm-monorepo && git log --oneline -5  # find previous commit
   git checkout <previous-commit> -- services/plc-copilot/
   ```
3. Rebuild and restart using steps 3-6 above

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Container exits immediately | Missing env vars | Check `docker logs plc-copilot-bot` for "Missing required:" messages |
| "Conflict: terminated by other getUpdates request" | Another bot instance running | `docker ps -a` and stop duplicate containers |
| "Message is too long" errors in logs | Gemini response exceeds 4096 chars | Should be handled by chunking (TRC-2026-02-16-001). If still happening, check `_chunk_text` is present. |
| Bot doesn't respond to photos | Gemini API key invalid | Verify `GEMINI_API_KEY` in env file, test with `curl` |

## Decomposition

| Task | Can Automate | Notes |
|------|-------------|-------|
| SSH + git pull | yes | Via Jarvis node remote shell API |
| Docker build | yes | `curl -X POST http://100.68.120.99:8765/shell -d '{"command":"..."}'` |
| Stop/start container | yes | Same remote shell pattern |
| Verify health | yes | Send Telegram /health or check docker ps |
| Check logs for errors | yes | grep ERROR in docker logs output |

## History

| Date | Change | Trace |
|------|--------|-------|
| 2026-02-16 | Initial creation, based on photo handler fix deploy | TRC-2026-02-16-001 |
