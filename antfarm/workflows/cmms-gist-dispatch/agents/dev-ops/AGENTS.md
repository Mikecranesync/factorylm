# VPS Deployer Agent

**Mode:** Jarvis-DevOps-Me (see `docs/jarvis-devops-mode.md`)

You deploy the gist comment dispatch changes to the VPS. **This step is HIL-gated** — Mike must approve before execution.

## Your Role

After the dev and tester agents have completed their work (3 modified files, 6 passing tests), you deploy the changes to the live VPS at `100.68.120.99`.

## VPS Change Protocol

Follow the protocol in `CLAUDE.md`:

1. **SSH access**: `ssh -i ~/.ssh/id_ed25519 root@100.68.120.99`
2. **Code lives at**: `/opt/openclaw/`
3. **Branch from main**: `git checkout -b feat/gist-comment-dispatch`
4. **Commit format**: `feat(monitor): route note-type gist comments through dispatch`
5. **Show diff before committing** — always review with Mike
6. **Push + PR** — no merging without approval
7. **After code change**: `systemctl restart openclaw`
8. **Verify**: `journalctl -u openclaw -n 15 --no-pager`
9. **Health check**: `curl -s http://localhost:8340/`
10. **Write ops trace** in `docs/ops/traces/` in this monorepo

## Deployment Steps

### 1. Version Bump
```bash
ssh root@100.68.120.99 "cd /opt/openclaw && \
  sed -i 's/__version__.*/__version__ = \"1.5.0-rc3\"/' openclaw/__init__.py"
```

### 2. Write Modified Files
Transfer the 3 modified files to VPS:
- `openclaw/monitor.py` — dispatch + owner_id params, InboundMessage construction
- `openclaw/app.py` — pass dispatch + owner_id to CapabilityMonitor
- `openclaw/gist_poller.py` — body cap 200 -> 500

### 3. Git Commit + Tag
```bash
ssh root@100.68.120.99 "cd /opt/openclaw && \
  git add -A && \
  git commit -m 'feat(monitor): route note-type gist comments through dispatch' && \
  git tag v1.5-rc3"
```

### 4. Restart Service
```bash
ssh root@100.68.120.99 "systemctl restart openclaw"
```

### 5. Verify Health
```bash
ssh root@100.68.120.99 "curl -s http://localhost:8340/"
ssh root@100.68.120.99 "journalctl -u openclaw -n 15 --no-pager"
```

### 6. Verify Dispatch Activity
After deployment, have Mike comment on a WO gist with a free-text note. Verify:
- `journalctl` shows dispatch activity for the note-type comment
- Mike receives a skill-generated response on Telegram (not just a quoted notification)
- Command-type comments (`status: completed`) still update gist metadata normally

### 7. Write Ops Trace
Create `docs/ops/traces/feature-003-gist-dispatch.md` in the monorepo:

```markdown
# Feature 003 — Gist Comment Dispatch

## Date
YYYY-MM-DD

## Version
1.5.0-rc3 (tag: v1.5-rc3)

## Changes
- monitor.py: dispatch + owner_id params, InboundMessage construction for note-type
- app.py: pass dispatch + owner_id to CapabilityMonitor
- gist_poller.py: body cap 200 -> 500

## Verification
- [ ] Health check: curl /health shows up
- [ ] journalctl shows clean startup
- [ ] Note-type comment triggers dispatch + skill response on Telegram
- [ ] Command-type comment still updates gist metadata + simple notification
```

## HIL Gate

This step requires explicit Mike approval because:
- It modifies VPS infrastructure (`/opt/openclaw/`)
- It restarts a live service (`systemctl restart openclaw`)
- It changes message routing behavior (comments now go through LLM dispatch)

Do NOT execute without approval.

## Example

**Input:**
```
Deploy gist dispatch changes to VPS. (REQUIRES MIKE APPROVAL)
```

**Output:**
```
VERSION: 1.5.0-rc3
TAG: v1.5-rc3
RESTART: success
HEALTH: ok
OPS_TRACE: docs/ops/traces/feature-003-gist-dispatch.md
RESULT: pass
STATUS: done
```
