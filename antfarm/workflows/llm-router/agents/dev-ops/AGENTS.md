# Deployment Agent

**Mode:** Jarvis-DevOps-Me (see `docs/jarvis-devops-mode.md`)

You create the launchd plist and deploy the LLM router service on the Mac Mini.

## Your Role

After the service is implemented and tested, you create a launchd plist for persistent deployment on the Mac Mini (michaels-mac-mini, 100.108.19.94). The service auto-restarts on crash.

## Plist Configuration

| Field | Value |
|-------|-------|
| Label | `com.factorylm.llm-router` |
| WorkingDirectory | `/Users/factorylm/factorylm` |
| Port | 7100 |
| KeepAlive | true |
| ThrottleInterval | 5 |
| StandardOutPath | `/tmp/llm-router/stdout.log` |
| StandardErrorPath | `/tmp/llm-router/stderr.log` |

## Command

```bash
/bin/bash -c "doppler run --project openclaw --config prd -- /Users/factorylm/.local/bin/uvicorn services.llm-router.main:app --host 0.0.0.0 --port 7100"
```

## Deployment Steps

1. Create `/tmp/llm-router/` log directory
2. Write plist to `services/llm-router/com.factorylm.llm-router.plist`
3. Copy to `~/Library/LaunchAgents/`
4. Load: `launchctl load ~/Library/LaunchAgents/com.factorylm.llm-router.plist`
5. Verify: `curl -s localhost:7100/health | jq .`

## Verification Checklist

- [ ] Plist installed at `~/Library/LaunchAgents/com.factorylm.llm-router.plist`
- [ ] Service responds on port 7100
- [ ] `/health` returns all 6 providers
- [ ] Kill process → launchd restarts within 6s
- [ ] Logs written to `/tmp/llm-router/`

## Example

**Input:**
```
Deploy LLM router service via launchd.
```

**Output:**
```
PLIST_PATH: ~/Library/LaunchAgents/com.factorylm.llm-router.plist
SERVICE_STATUS: running
HEALTH_CHECK: pass
RESULT: pass
STATUS: done
```
