# VPS Security Hardening Runbook

**VPS:** factorylm-prod (100.68.120.99)
**Last Updated:** 2026-02-18
**Status:** APPLIED

---

## Overview

This runbook documents the security hardening applied to the FactoryLM VPS to block public internet access to dev tools while maintaining full connectivity for Tailscale-connected agents.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     AFTER HARDENING                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   PUBLIC INTERNET ──────► BLOCKED (UFW deny)                    │
│                                                                  │
│   TAILSCALE MESH ──────────► All Services ◄── ALLOWED           │
│   (PLC, Travel, etc.)                                            │
│                                                                  │
│   Why it works: "Anywhere on tailscale0 ALLOW" rule             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Tailscale Peers (Full Access)

| Device | Tailscale IP | Type |
|--------|--------------|------|
| VPS (factorylm-prod) | 100.68.120.99 | Linux |
| PLC Laptop | 100.72.2.99 | Windows |
| Travel Laptop | 100.83.251.23 | Windows |
| Hetzner | 100.67.25.53 | Linux |
| Pixel 9A | 100.73.197.64 | Android |

All peers have full access to all VPS services via Tailscale.

---

## UFW Rules Applied

### Ports BLOCKED from Public Internet

| Port | Service | Risk | Rule Applied |
|------|---------|------|--------------|
| 8765 | Jarvis Hub WebSocket | CRITICAL | `ufw deny 8765/tcp` |
| 8000 | MkDocs | MEDIUM | `ufw deny 8000/tcp` |
| 8080 | Plane API | MEDIUM | `ufw deny 8080/tcp` |
| 3001 | Unknown | MEDIUM | `ufw deny 3001/tcp` |
| 5432 | PostgreSQL | HIGH | `ufw deny 5432/tcp` |
| 6379 | Redis | HIGH | `ufw deny 6379/tcp` |

### Ports ALLOWED from Public Internet

| Port | Service | Reason |
|------|---------|--------|
| 22 | SSH | Remote access |
| 80 | HTTP/nginx | Web traffic |
| 443 | HTTPS | Web traffic |
| 8070 | Langfuse | Intentionally public |

### Tailscale Rule (Critical)

```
Anywhere on tailscale0     ALLOW IN    Anywhere
Anywhere (v6) on tailscale0 ALLOW IN    Anywhere (v6)
```

This rule allows ALL traffic from Tailscale peers, bypassing the port-specific deny rules.

---

## File Permissions Tightened

| File | Before | After |
|------|--------|-------|
| `/root/.openclaw/openclaw.json` | 644 | 600 |
| `/root/.clawdbot/.env` | 644 | 600 |
| `/root/jarvis-workspace/.env.master` | 644 | 600 |

---

## Commands Reference

### View Current UFW Status
```bash
ssh root@100.68.120.99 "sudo ufw status verbose"
```

### Add New Deny Rule
```bash
ssh root@100.68.120.99 "sudo ufw deny <PORT>/tcp comment '<DESCRIPTION>'"
```

### Remove Deny Rule (Rollback)
```bash
ssh root@100.68.120.99 "sudo ufw delete deny <PORT>/tcp"
```

### Emergency: Disable Firewall
```bash
ssh root@100.68.120.99 "sudo ufw disable"
# Fix issue, then re-enable:
ssh root@100.68.120.99 "sudo ufw enable"
```

### Check Tailscale Status
```bash
ssh root@100.68.120.99 "sudo tailscale status"
```

### Verify Service Access via Tailscale
```bash
# From any Tailscale peer:
curl http://100.68.120.99:8765/health   # Jarvis Hub
curl http://100.68.120.99:3000/health   # Mission Control
curl http://100.68.120.99:8340/health   # OpenClaw
curl http://100.68.120.99:5555/         # Flower
```

---

## Troubleshooting

### Agent Can't Connect After Hardening

1. **Check Tailscale is running on the agent:**
   ```bash
   tailscale status
   ```

2. **Verify the agent appears in VPS Tailscale peers:**
   ```bash
   ssh root@100.68.120.99 "tailscale status"
   ```

3. **If agent is missing from Tailscale mesh:**
   - Restart Tailscale on the agent
   - Check Tailscale admin console for device approval

### Accidentally Blocked a Required Port

```bash
# Remove the deny rule
ssh root@100.68.120.99 "sudo ufw delete deny <PORT>/tcp"
```

### Need to Expose a Port Publicly

```bash
# Allow specific port from public internet
ssh root@100.68.120.99 "sudo ufw allow <PORT>/tcp comment '<DESCRIPTION>'"
```

---

## Security Audit Command

Run this to audit the VPS security posture:

```bash
ssh root@100.68.120.99 "
echo '=== UFW STATUS ==='
sudo ufw status verbose

echo ''
echo '=== TAILSCALE STATUS ==='
sudo tailscale status

echo ''
echo '=== LISTENING PORTS ==='
ss -tulpen | grep LISTEN

echo ''
echo '=== CONFIG FILE PERMISSIONS ==='
stat -c '%a %n' /root/.openclaw/openclaw.json /root/.clawdbot/.env /root/jarvis-workspace/.env.master 2>/dev/null
"
```

---

## Rollback Plan

To fully revert the hardening:

```bash
ssh root@100.68.120.99 "
sudo ufw delete deny 8765/tcp
sudo ufw delete deny 8000/tcp
sudo ufw delete deny 8080/tcp
sudo ufw delete deny 3001/tcp
sudo ufw delete deny 5432/tcp
sudo ufw delete deny 6379/tcp
chmod 644 /root/.openclaw/openclaw.json
chmod 644 /root/.clawdbot/.env
chmod 644 /root/jarvis-workspace/.env.master
echo 'Rollback complete'
"
```

---

## Changelog

| Date | Change | Applied By |
|------|--------|------------|
| 2026-02-18 | Initial hardening - blocked 6 ports, tightened 3 config files | Claude + Mike |
