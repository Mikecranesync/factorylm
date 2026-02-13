# Hostinger VPS Extraction Runbook (jarvis-legacy)

**Last Updated:** 2026-02-13  
**Status:** Pre-decommission

---

## Connection

```bash
ssh root@72.60.175.144
# or via SSH alias:
ssh hostinger
```

---

## What Lives There

| Path | Description |
|------|-------------|
| `/root/.clawdbot/clawdbot.json` | ClawdBot config |
| `/root/jarvis-workspace/` | Workspace |
| `/root/jarvis-workspace/SOUL.md` | SOUL.md |
| `/root/.clawdbot/agents/main/agent/` | Agent data |
| `/root/Rivet-PRO/` | Rivet-PRO |
| `/etc/vector/vector.yaml` | Vector config |
| `/etc/systemd/system/clawdbot.service` | Systemd unit (bot) |
| `/etc/systemd/system/vector.service` | Systemd unit (logs) |

---

## Extraction Commands

```bash
# 1. Create a dated backup tarball on the VPS
ssh hostinger "tar czf /tmp/hostinger-backup-$(date +%Y%m%d).tar.gz \
  /root/.clawdbot/ \
  /root/jarvis-workspace/ \
  /root/Rivet-PRO/ \
  /etc/vector/vector.yaml \
  /etc/systemd/system/clawdbot.service \
  /etc/systemd/system/vector.service \
  2>/dev/null"

# 2. Copy to local machine
scp hostinger:/tmp/hostinger-backup-*.tar.gz C:\Users\hharp\OneDrive\Desktop\backups\

# 3. Or use rsync for incremental sync
rsync -avz hostinger:/root/.clawdbot/ C:\Users\hharp\OneDrive\Desktop\backups\hostinger\clawdbot\
rsync -avz hostinger:/root/jarvis-workspace/ C:\Users\hharp\OneDrive\Desktop\backups\hostinger\workspace\
rsync -avz hostinger:/root/Rivet-PRO/ C:\Users\hharp\OneDrive\Desktop\backups\hostinger\rivet-pro\
```

---

## Pre-Decommission Checklist

- [ ] Backup tarball downloaded and verified
- [ ] SOUL.md content reviewed (any unique content to preserve?)
- [ ] clawdbot.json config captured (model configs, provider keys reference)
- [ ] Vector/Axiom config captured
- [ ] Rivet-PRO data pulled (already in GitHub?)
- [ ] No unique databases to export
- [ ] Bot stopped: `ssh hostinger "systemctl stop clawdbot"`
- [ ] Mike confirms OK to shut down

---

## After Decommission

- Cancel Hostinger subscription
- Remove `ssh hostinger` alias from `~/.ssh/config`
- Update `docs/OPENCLAW_INSTANCES.md` to mark as decommissioned
