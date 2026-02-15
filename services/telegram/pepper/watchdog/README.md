# PEPPER Watchdog Monitoring System

**Version:** 1.0.0
**Status:** Production Ready

## Overview

Comprehensive monitoring, drift detection, and auto-recovery system for PEPPER (FactoryLM).

## Features

### 1. Health Monitoring
- **Node Health**: PLC Laptop, Travel Laptop, VPS Gateway, Matrix API
- **Service Health**: systemd services (pepper, pepper-watchdog, clawdbot)
- **Response Time Tracking**: Latency measurement for all endpoints
- **Critical/Non-Critical Classification**: Priority-based alerting

### 2. Configuration Drift Detection
- **Hash-Based Monitoring**: SHA256 hashing of critical config files
- **Automatic Backups**: Timestamped backups on change detection
- **Severity Classification**: CRITICAL (tokens), WARNING (models), INFO (formatting)
- **Field-Level Analysis**: Track specific configuration fields

### 3. API Key Validation
- **Groq API**: Llama models for Layer 2 intelligence
- **Anthropic API**: Claude models for Layer 3 fallback
- **Telegram Bots**: Both Prime (god mode) and Demo bots
- **Minimal Quota Usage**: Lightweight test requests

### 4. System Fingerprinting
- **Structural Change Detection**: Track system topology changes
- **File Monitoring**: Hash critical system files
- **Environment Variables**: Track API key presence
- **Service/Node States**: Monitor infrastructure availability

### 5. Auto-Recovery
- **Service Restart**: Automatic systemd service restart
- **Cooldown Logic**: 5-minute cooldown with max 3 attempts
- **Attempt Tracking**: Persistent recovery attempt history
- **Configurable Actions**: Per-service auto-restart settings

### 6. Alert Routing
- **Multi-Channel**: Telegram, log files, Axiom (future)
- **Severity-Based Routing**: CRITICAL → Telegram + Log, INFO → Log only
- **Alert Deduplication**: 5-minute dedup window
- **Daily Digest**: Morning summary at 8 AM

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Watchdog Orchestrator                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Health     │  │    Drift     │  │   API Key    │ │
│  │   Checker    │  │   Detector   │  │  Validator   │ │
│  │  (5 min)     │  │  (5 min)     │  │  (15 min)    │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
│         │                 │                  │         │
│         └─────────────────┴──────────────────┘         │
│                           │                            │
│                  ┌────────▼────────┐                   │
│                  │ Alert Manager   │                   │
│                  │ (Multi-channel) │                   │
│                  └────────┬────────┘                   │
│                           │                            │
│         ┌─────────────────┼─────────────────┐          │
│         │                 │                 │          │
│    ┌────▼────┐      ┌─────▼─────┐    ┌─────▼─────┐   │
│    │Telegram │      │ Log File  │    │  Axiom    │   │
│    └─────────┘      └───────────┘    └───────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Installation

### 1. Install Dependencies

```bash
pip install httpx pyyaml
```

### 2. Configure

Edit `/root/pepper/watchdog.yaml`:

```yaml
version: "1.0.0"
state_dir: "/root/.pepper-watchdog"

health:
  interval_seconds: 300
  nodes:
    - id: plc
      name: "PLC Laptop"
      url: "http://100.72.2.99:8765/health"
      critical: true

alerts:
  telegram:
    enabled: true
    bot_token: ${PEPPER_PRIME_TOKEN}
    chat_id: "8445149012"
```

### 3. Install Systemd Service

```bash
# Copy service file
sudo cp pepper-watchdog.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable pepper-watchdog
sudo systemctl start pepper-watchdog

# Check status
sudo systemctl status pepper-watchdog
```

### 4. Verify

```bash
# Check logs
sudo journalctl -u pepper-watchdog -f

# Check state directory
ls -la /root/.pepper-watchdog/
```

## Usage

### Manual Invocation

```bash
# Run watchdog directly
python -m pepper.watchdog.main

# With custom config
WATCHDOG_CONFIG=/path/to/config.yaml python -m pepper.watchdog.main
```

### Service Management

```bash
# Start
sudo systemctl start pepper-watchdog

# Stop
sudo systemctl stop pepper-watchdog

# Restart
sudo systemctl restart pepper-watchdog

# View logs
sudo journalctl -u pepper-watchdog -f --lines=100
```

## Configuration

### Health Check Intervals

```yaml
health:
  interval_seconds: 300  # 5 minutes

api_validation:
  interval_seconds: 900  # 15 minutes

fingerprint:
  interval_seconds: 300  # 5 minutes
```

### Alert Routing

```yaml
alerts:
  severity_routing:
    critical:
      - telegram
      - log
    warning:
      - telegram
      - log
    info:
      - log
```

### Recovery Settings

```yaml
recovery:
  enabled: true
  max_attempts: 3
  cooldown_minutes: 5

  actions:
    service_down:
      - type: restart
        max_attempts: 3
```

## Monitoring

### Health Check Output

```json
{
  "timestamp": "2026-02-14T20:30:00",
  "overall_status": "healthy",
  "nodes": {
    "plc": {
      "status": "healthy",
      "latency_ms": 45.2,
      "last_seen": "2026-02-14T20:29:55"
    }
  },
  "services": {
    "pepper": {
      "status": "healthy",
      "active": true,
      "running": true,
      "pid": 12345
    }
  }
}
```

### Alert Format (Telegram)

```
🚨 **CRITICAL**

**System Health Critical**
Node 'PLC Laptop' is unhealthy

_Source: watchdog_
_Time: 2026-02-14 20:30:15_
```

## State Files

All state stored in `/root/.pepper-watchdog/`:

- `baselines/`: Configuration file hashes
- `config_backups/`: Timestamped config backups
- `recovery_attempts.json`: Recovery attempt history
- `system_fingerprint.json`: Current system fingerprint
- `daily_alerts.json`: Today's alerts for digest
- `alerts.log`: Alert log file

## Troubleshooting

### Watchdog Not Starting

```bash
# Check service status
sudo systemctl status pepper-watchdog

# Check logs
sudo journalctl -u pepper-watchdog -n 50

# Verify config
python -c "import yaml; yaml.safe_load(open('/root/pepper/watchdog.yaml'))"
```

### No Telegram Alerts

1. Verify `PEPPER_PRIME_TOKEN` environment variable
2. Check Telegram chat ID is correct
3. Test bot token: `curl https://api.telegram.org/bot$TOKEN/getMe`

### Health Checks Failing

1. Verify nodes are reachable: `curl http://100.72.2.99:8765/health`
2. Check firewall rules
3. Verify systemd services are running

## Integration

### With PEPPER Main Bot

The watchdog runs independently but monitors PEPPER's health. If PEPPER fails:

1. Watchdog detects service down
2. Attempts automatic restart (up to 3 times)
3. Sends Telegram alert to Mike
4. Logs recovery attempts

### With Digital Twin Nodes

Watchdog monitors all nodes in the FactoryLM network:

- **PLC Laptop** (100.72.2.99:8765) - CRITICAL
- **Travel Laptop** (100.83.251.23:8765) - Non-critical
- **VPS Gateway** (localhost:18789) - CRITICAL

## API Reference

### Health Checker

```python
from pepper.watchdog import HealthChecker

checker = HealthChecker(config)
report = await checker.check_all()

if report.overall_status == HealthStatus.UNHEALTHY:
    print(report.get_critical_issues())
```

### Alert Manager

```python
from pepper.watchdog import AlertManager

alerts = AlertManager(config, state_dir)

# Send critical alert
await alerts.send_critical(
    title="System Failure",
    message="Critical component down"
)

# Send daily digest
await alerts.send_daily_digest()
```

### Recovery Manager

```python
from pepper.watchdog import RecoveryManager

recovery = RecoveryManager(config, state_dir)

# Restart service
result = await recovery.restart_service("pepper")

if result.success:
    print(f"Service restarted (attempt {result.attempt_number})")
```

## Production Checklist

- [ ] Configure all environment variables
- [ ] Test Telegram bot token
- [ ] Verify node health endpoints
- [ ] Set up systemd service
- [ ] Configure log rotation
- [ ] Test recovery actions
- [ ] Verify alert routing
- [ ] Schedule daily digest
- [ ] Monitor state directory disk usage
- [ ] Document escalation procedures

## Security

- API keys stored in environment variables (not config files)
- State directory restricted to root user
- Telegram alerts only to authorized chat ID
- No sensitive data in logs
- Recovery actions rate-limited

## Performance

- **Memory Usage**: ~50-100 MB
- **CPU Usage**: <1% (idle), ~5% (during checks)
- **Network**: Minimal (~1 KB/s average)
- **Disk**: ~10-50 MB for state files

## Future Enhancements

- [ ] Axiom log shipping integration
- [ ] Webhook alert endpoint
- [ ] Custom recovery scripts
- [ ] Performance trend analysis
- [ ] Predictive failure detection
- [ ] Multi-region support
- [ ] Web dashboard

## Support

For issues or questions:
- Check logs: `sudo journalctl -u pepper-watchdog -f`
- Review state files: `/root/.pepper-watchdog/`
- Test individual components: `python -m pepper.watchdog.health`

---

**Built for FactoryLM Catapult Lakeland Demo**
**Demo Date:** February 10, 2026
**Mission:** "Text your factory from your phone, AI tells you what's wrong."
