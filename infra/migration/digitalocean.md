# DigitalOcean VPS Extraction Runbook (ultron)

**Last Updated:** 2026-02-13  
**Status:** Pre-decommission

---

## Connection

```bash
ssh root@100.68.120.99  # via Tailscale
# or:
ssh vps
```

---

## What Lives There

| Path | Description |
|------|-------------|
| `/root/.openclaw/openclaw.json` | OpenClaw config |
| `/root/.openclaw/agents/main/agent/` | Agent data (including models.json) |
| `/root/jarvis-workspace/` | Workspace |
| `/root/jarvis-workspace/SOUL.md` | SOUL.md |
| `/root/jarvis-workspace/IDENTITY.md` | IDENTITY.md |
| `/etc/vector/vector.yaml` | Vector config |
| `/etc/systemd/system/openclaw.service` | Systemd unit (bot) |
| `/etc/systemd/system/vector.service` | Systemd unit (logs) |
| `/root/.ollama/` | Ollama models (qwen2.5:0.5b, tinyllama) |
| `/tmp/openclaw/` | Logs |

---

## Extraction Commands

```bash
# 1. Create a dated backup tarball on the VPS
ssh vps "tar czf /tmp/do-backup-$(date +%Y%m%d).tar.gz \
  /root/.openclaw/ \
  /root/jarvis-workspace/ \
  /etc/vector/vector.yaml \
  /etc/systemd/system/openclaw.service \
  /etc/systemd/system/vector.service \
  2>/dev/null"

# 2. Copy to local machine
scp vps:/tmp/do-backup-*.tar.gz C:\Users\hharp\OneDrive\Desktop\backups\

# 3. Or use rsync for incremental sync
rsync -avz vps:/root/.openclaw/ C:\Users\hharp\OneDrive\Desktop\backups\do\openclaw\
rsync -avz vps:/root/jarvis-workspace/ C:\Users\hharp\OneDrive\Desktop\backups\do\workspace\

# 4. Export Ollama model list (not the models themselves — re-pull locally)
ssh vps "ollama list" > C:\Users\hharp\OneDrive\Desktop\backups\do\ollama-models.txt
```

---

## Pre-Decommission Checklist

- [ ] Backup tarball downloaded and verified
- [ ] SOUL.md + IDENTITY.md content reviewed
- [ ] openclaw.json config captured (model configs, provider keys reference)
- [ ] Vector/Axiom config captured
- [ ] Systemd unit files captured
- [ ] Ollama model list captured (re-pull locally, don't transfer weights)
- [ ] Hetzner is confirmed working as replacement
- [ ] Bot migrated to Hetzner (or running locally)
- [ ] Bot stopped: `ssh vps "systemctl stop openclaw"`
- [ ] Mike confirms OK to shut down

---

## After Decommission

- Destroy DigitalOcean droplet
- Remove Tailscale device from network
- Update `docs/OPENCLAW_INSTANCES.md` to mark as decommissioned
- Update `MEMORY.md` VPS Connection section
