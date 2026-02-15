# PEPPER Watchdog Installation Guide

**Quick Start Guide for VPS Deployment**

## Prerequisites

- Python 3.9+
- Root access
- Active PEPPER installation at `/root/pepper`
- Environment variables configured in `/root/.pepper/.env`

## Installation Steps

### 1. Copy Files to VPS

From your development machine:

```bash
# Using rsync
rsync -avz watchdog/ root@100.68.120.99:/root/pepper/watchdog/

# Or using scp
scp -r watchdog/ root@100.68.120.99:/root/pepper/
```

### 2. SSH to VPS

```bash
ssh root@100.68.120.99
```

### 3. Run Deployment Script

```bash
cd /root/pepper/watchdog
chmod +x deploy.sh
./deploy.sh
```

The script will:
- Install Python dependencies (httpx, PyYAML)
- Create state directory `/root/.pepper-watchdog`
- Validate configuration
- Install systemd service
- Start the watchdog

### 4. Verify Installation

```bash
# Check service status
systemctl status pepper-watchdog

# View live logs
journalctl -u pepper-watchdog -f

# Check state directory
ls -la /root/.pepper-watchdog/
```

## Expected Output

```
==========================================
PEPPER Watchdog Deployment
==========================================
✓ Python 3.11.2
✓ Dependencies installed
✓ State directory created: /root/.pepper-watchdog
✓ Configuration found
✓ Configuration valid
✓ PEPPER_PRIME_TOKEN configured
✓ GROQ_API_KEY configured
✓ Service installed
✓ Service enabled
✓ Watchdog started successfully
==========================================
Deployment Complete!
==========================================
```

## Verify Watchdog is Working

### 1. Check Health Monitoring

```bash
# Should show health check cycles every 5 minutes
journalctl -u pepper-watchdog -f | grep "health check"
```

Expected output:
```
Feb 14 20:00:00 vps pepper-watchdog: INFO Starting health check cycle
Feb 14 20:00:01 vps pepper-watchdog: INFO Health check complete: healthy (3 nodes, 3 services)
```

### 2. Test Telegram Alerts

Manually trigger an alert:

```bash
# Restart pepper to trigger recovery
systemctl stop pepper

# Watch watchdog logs
journalctl -u pepper-watchdog -f
```

You should receive a Telegram message:
```
🚨 CRITICAL

System Health Critical
Service 'pepper' is unhealthy

Source: watchdog
Time: 2026-02-14 20:05:30
```

### 3. Check State Files

```bash
ls -lR /root/.pepper-watchdog/
```

Expected structure:
```
/root/.pepper-watchdog/
├── baselines/
│   ├── openclaw.json.hash
│   └── config.yaml.hash
├── config_backups/
├── recovery_attempts.json
├── system_fingerprint.json
├── daily_alerts.json
└── alerts.log
```

## Manual Testing

### Test Individual Components

```bash
cd /root/pepper

# Test health checker
python3 -c "
import asyncio
from watchdog.health import HealthChecker
import yaml

config = yaml.safe_load(open('watchdog.yaml'))
checker = HealthChecker(config)
report = asyncio.run(checker.check_all())
print(f'Status: {report.overall_status.value}')
print(f'Nodes: {len(report.nodes)}')
print(f'Services: {len(report.services)}')
"

# Test API validator
python3 -c "
import asyncio
from watchdog.api_validator import APIValidator
import yaml

config = yaml.safe_load(open('watchdog.yaml'))
validator = APIValidator(config)
results = asyncio.run(validator.validate_all())
for provider, status in results.items():
    print(f'{provider}: {'valid' if status.is_valid else 'INVALID'}')
"
```

## Troubleshooting

### Service Won't Start

```bash
# Check detailed logs
journalctl -u pepper-watchdog -n 100 --no-pager

# Validate config manually
python3 -c "import yaml; yaml.safe_load(open('/root/pepper/watchdog.yaml'))"

# Check environment variables
grep -E "(PEPPER|GROQ|ANTHROPIC)" /root/.pepper/.env
```

### No Telegram Alerts

```bash
# Test bot token
export TOKEN=$(grep PEPPER_PRIME_TOKEN /root/.pepper/.env | cut -d= -f2)
curl "https://api.telegram.org/bot$TOKEN/getMe"

# Should return:
# {"ok":true,"result":{"id":...,"is_bot":true,"first_name":"Pepper Prime",...}}
```

### Health Checks Failing

```bash
# Test node reachability
curl http://100.72.2.99:8765/health
curl http://100.83.251.23:8765/health
curl http://localhost:18789/health

# Test service status
systemctl status pepper
systemctl status clawdbot
```

### Permissions Issues

```bash
# Fix state directory permissions
chown -R root:root /root/.pepper-watchdog
chmod 700 /root/.pepper-watchdog

# Fix service permissions
chmod 644 /etc/systemd/system/pepper-watchdog.service
```

## Post-Installation

### 1. Configure Log Rotation

Create `/etc/logrotate.d/pepper-watchdog`:

```bash
cat > /etc/logrotate.d/pepper-watchdog << 'EOF'
/root/.pepper-watchdog/alerts.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0600 root root
}
EOF
```

### 2. Monitor Resource Usage

```bash
# Check memory usage
ps aux | grep pepper-watchdog

# Check CPU usage
top -p $(pgrep -f pepper-watchdog)

# Expected: ~50-100 MB RAM, <1% CPU
```

### 3. Test Auto-Recovery

```bash
# Stop pepper service
systemctl stop pepper

# Wait 5 minutes for health check

# Watchdog should:
# 1. Detect pepper is down
# 2. Attempt restart (up to 3 times)
# 3. Send Telegram alert
# 4. Log recovery attempt

# Check recovery logs
journalctl -u pepper-watchdog | grep -i recovery
```

## Maintenance

### View Logs

```bash
# Live logs
journalctl -u pepper-watchdog -f

# Last 100 lines
journalctl -u pepper-watchdog -n 100

# Today's logs
journalctl -u pepper-watchdog --since today

# Filter by severity
journalctl -u pepper-watchdog -p err
```

### Reset Recovery Attempts

If you want to reset the recovery cooldown:

```bash
rm /root/.pepper-watchdog/recovery_attempts.json
systemctl restart pepper-watchdog
```

### Reset All Baselines

If you intentionally changed configs and want to suppress drift alerts:

```bash
rm -rf /root/.pepper-watchdog/baselines/
systemctl restart pepper-watchdog
```

## Integration with PEPPER

The watchdog runs independently but monitors PEPPER. If you update PEPPER:

```bash
# 1. Stop watchdog temporarily (optional)
systemctl stop pepper-watchdog

# 2. Update PEPPER
cd /root/pepper
git pull
systemctl restart pepper

# 3. Restart watchdog
systemctl start pepper-watchdog
```

## Production Checklist

Before relying on watchdog in production:

- [ ] Verify all health endpoints are accessible
- [ ] Test Telegram alerts (send test critical alert)
- [ ] Test service recovery (stop pepper, verify auto-restart)
- [ ] Configure log rotation
- [ ] Document escalation procedures
- [ ] Set up monitoring for watchdog itself (use Axiom)
- [ ] Schedule manual review of daily digests
- [ ] Test drift detection (modify config, verify backup)
- [ ] Verify API key validation (invalidate key temporarily)

## Next Steps

1. **Monitor for 24 hours**: Watch logs to ensure stable operation
2. **Tune intervals**: Adjust check intervals if needed
3. **Add Axiom**: Configure Axiom log shipping
4. **Document incidents**: Create runbook for alert responses
5. **Expand monitoring**: Add custom health endpoints

---

**Deployment Date**: 2026-02-14
**Target Environment**: VPS (100.68.120.99)
**Demo Date**: February 10, 2026 @ 12:00-1:30 PM
