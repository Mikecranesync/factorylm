# WF-007: Check Jarvis Baseline

| Field | Value |
|-------|-------|
| **ID** | WF-007 |
| **Created** | 2026-02-16 |
| **Last Verified** | 2026-02-16 |
| **Status** | draft |
| **Services** | openclaw |
| **Devices** | vps, phone (Telegram) |
| **Est. Duration** | 10m |

---

## Purpose

Repeatable Telegram health check to verify Jarvis behavior matches the golden baseline. Run after any deployment, config change, or service restart on the VPS.

## Prerequisites

- [ ] Telegram app with access to @FACTORYLM_bot (MikesOPENCLAW)
- [ ] VPS (100.68.120.99) reachable via Tailscale
- [ ] SSH access: `ssh -i ~/.ssh/id_ed25519 root@100.68.120.99`

## Steps

### 1. Verify service is running

- **Device**: VPS (SSH)
- **Command**:
  ```bash
  ssh -i ~/.ssh/id_ed25519 root@100.68.120.99 "systemctl status openclaw --no-pager | head -5"
  ```
- **Expected Output**: `Active: active (running)`
- **Verify**: Status shows "active"

### 2. Check health endpoint

- **Device**: any (via Tailscale)
- **Command**:
  ```bash
  curl -s http://100.68.120.99:8340/
  ```
- **Expected Output**: JSON with `"name": "Jarvis (OpenClaw)"`, providers list (groq, anthropic, gemini), skills list (7 skills)
- **Verify**: All expected providers and skills present

### 3. Check budget endpoint

- **Device**: any
- **Command**:
  ```bash
  curl -s http://100.68.120.99:8340/budget
  ```
- **Expected Output**: JSON with per-provider stats. Anthropic: daily_request_limit=100, daily_token_limit=100000. Groq: daily_request_limit=14000.
- **Verify**: Limits match baseline values

### 4. Test greeting (baseline T-001)

- **Device**: Phone (Telegram)
- **Action**: Send `hello` to @FACTORYLM_bot
- **Expected**: Jarvis-style greeting referencing industrial maintenance
- **Verify**: Not "An error occurred", not a multi-paragraph generic OpenClaw intro

### 5. Test emoji ack (baseline T-011)

- **Device**: Phone (Telegram)
- **Action**: Send any message and watch for 👀 reaction
- **Expected**: 👀 emoji reaction appears on your message immediately
- **Verify**: Reaction visible within 1 second of sending

### 6. Test photo analysis (baseline T-006)

- **Device**: Phone (Telegram)
- **Action**: Send a photo of industrial equipment with caption `What is this?`
- **Expected**: Equipment identification with details (vendor, model, components)
- **Verify**: Returns analysis text, no "Sorry, something went wrong" error

### 7. Test help routing (baseline T-010)

- **Device**: Phone (Telegram)
- **Action**: Send `help`
- **Expected**: Capability guide listing what Jarvis can do
- **Verify**: NOT a health dump or raw JSON. Lists capabilities in friendly language.

### 8. Check logs for errors

- **Device**: VPS (SSH)
- **Command**:
  ```bash
  ssh -i ~/.ssh/id_ed25519 root@100.68.120.99 "journalctl -u openclaw -n 50 --no-pager | grep -i error"
  ```
- **Expected Output**: No ERROR lines (or only known/benign ones)
- **Verify**: No unexpected errors since last restart

## Verification

All 8 steps pass = baseline verified. Record results:

```
Date: ___________
Steps 1-3 (infrastructure): PASS / FAIL
Steps 4-7 (Telegram behavior): PASS / FAIL
Step 8 (logs): PASS / FAIL
Overall: PASS / FAIL
Notes: ___________
```

## Rollback

If baseline check fails after a change:
1. SSH to VPS: `ssh -i ~/.ssh/id_ed25519 root@100.68.120.99`
2. Revert code: `cd /opt/openclaw && git checkout v0.9.0-jarvis-baseline`
3. Restart: `systemctl restart openclaw`
4. Wait 5 seconds, re-run this workflow to confirm restoration

If the tag doesn't exist yet, compare current code against the JARVIS-IS-DEAD repo.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Service not running | Crash or failed restart | `journalctl -u openclaw -n 100` for root cause |
| Health endpoint unreachable | Port blocked or service down | Check `systemctl status openclaw`, check Tailscale |
| Generic personality | `prompts.py` reverted | Compare against baseline, re-apply SYSTEM_PROMPT |
| "An error occurred" on text | Provider API key failure | Check Doppler keys: `doppler secrets` in `/opt/openclaw` |
| Photo analysis fails | Gemini API key missing/exhausted | Verify `GEMINI_API_KEY` in Doppler |
| No emoji ack | `feat/tts-emoji-ack` not deployed | Verify branch: `git -C /opt/openclaw branch` |
| Help returns health dump | Router misroute regression | Check `messages/intent.py` HELP keyword handling |
| Budget exceeded | Heavy usage day | Check `/budget` endpoint, wait for daily reset |

## Decomposition

| Task | Can Automate | Notes |
|------|-------------|-------|
| Check service status | yes | SSH + systemctl |
| Check health/budget endpoints | yes | curl |
| Send Telegram test messages | partial | Could use Bot API, but manual is more realistic |
| Verify Telegram responses | no | Human judgment on tone/quality |
| Check logs for errors | yes | grep in journalctl |

## History

| Date | Change | Trace |
|------|--------|-------|
| 2026-02-16 | Initial creation | Golden baseline documentation sprint |
