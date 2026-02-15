# PEPPER Watchdog System Architecture

**Version:** 1.0.0
**Total Code:** ~3,000 lines of Python
**Components:** 8 modules + orchestrator
**Status:** Production Ready

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    PEPPER WATCHDOG SYSTEM                       │
│                  Comprehensive Monitoring Platform              │
└─────────────────────────────────────────────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │   Main Orchestrator     │
                    │  (main.py - 442 lines)  │
                    └────────────┬────────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          │                      │                      │
    ┌─────▼─────┐          ┌─────▼─────┐        ┌─────▼─────┐
    │  Health   │          │   Drift   │        │    API    │
    │  Checker  │          │ Detector  │        │ Validator │
    │ (336 ln)  │          │ (372 ln)  │        │ (421 ln)  │
    └─────┬─────┘          └─────┬─────┘        └─────┬─────┘
          │                      │                      │
          │      ┌───────────────┴──────────────┐      │
          │      │                              │      │
    ┌─────▼──────▼─────┐                  ┌─────▼──────▼─────┐
    │   Fingerprint    │                  │ Recovery Manager │
    │   (383 lines)    │                  │   (400 lines)    │
    └──────────────────┘                  └──────────────────┘
                                                      │
                    ┌─────────────────────────────────┘
                    │
            ┌───────▼────────┐
            │ Alert Manager  │
            │  (403 lines)   │
            └───────┬────────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
   ┌────▼────┐ ┌────▼────┐ ┌───▼─────┐
   │Telegram │ │Log File │ │  Axiom  │
   │ Alerts  │ │Logging  │ │(Future) │
   └─────────┘ └─────────┘ └─────────┘
```

## Component Architecture

### 1. Health Checker (`health.py` - 336 lines)

**Responsibility:** Monitor node and service health across infrastructure

**Key Classes:**
- `HealthChecker`: Main health monitoring coordinator
- `NodeHealth`: Node health status dataclass
- `ServiceHealth`: Service health status dataclass
- `HealthReport`: Comprehensive health report
- `HealthStatus`: Enum (HEALTHY, DEGRADED, UNHEALTHY, UNKNOWN)

**Monitoring Targets:**
- **Nodes**: PLC Laptop, Travel Laptop, VPS Gateway, Matrix API
- **Services**: pepper, pepper-watchdog, clawdbot (systemd)

**Features:**
- Concurrent node health checks (async)
- HTTP endpoint monitoring with latency tracking
- Systemd service status checking
- Critical/non-critical component classification
- Overall system health computation

**Check Interval:** 5 minutes (configurable)

---

### 2. Configuration Drift Detector (`drift.py` - 372 lines)

**Responsibility:** Detect and track configuration file changes

**Key Classes:**
- `DriftDetector`: Configuration change monitor
- `DriftReport`: Drift detection report
- `FileChange`: Individual file change record
- `DriftSeverity`: Enum (CRITICAL, WARNING, INFO, NONE)

**Monitored Files:**
- `/root/.openclaw/openclaw.json` (OpenClaw config)
- `/root/pepper/config.yaml` (PEPPER config)
- Systemd service files

**Features:**
- SHA256 hash-based change detection
- Automatic timestamped backups on change
- Field-level severity analysis
- Baseline establishment and comparison
- Configurable retention policies

**Detection Logic:**
- **CRITICAL**: API tokens, credentials changed
- **WARNING**: Model configs, URLs changed
- **INFO**: Formatting, comments changed

---

### 3. API Key Validator (`api_validator.py` - 421 lines)

**Responsibility:** Validate external service API keys

**Key Classes:**
- `APIValidator`: API key testing coordinator
- `KeyStatus`: Validation status dataclass

**Validated APIs:**
- **Groq**: Llama models (Layer 2 intelligence)
- **Anthropic**: Claude models (Layer 3 fallback)
- **Telegram**: Prime and Demo bot tokens

**Features:**
- Minimal test requests to avoid quota consumption
- Concurrent validation of all providers
- Response time tracking
- Detailed error reporting
- Environment variable configuration

**Test Strategies:**
- **Groq**: Minimal completion request (5 tokens)
- **Anthropic**: Minimal message request (5 tokens)
- **Telegram**: `getMe` endpoint (free)

**Check Interval:** 15 minutes (configurable)

---

### 4. System Fingerprint (`fingerprint.py` - 383 lines)

**Responsibility:** Track structural system changes

**Key Classes:**
- `SystemFingerprint`: Structural change detector
- `FingerprintReport`: Fingerprint comparison report

**Monitored Elements:**
- Configuration file hashes
- Service availability states
- Node reachability status
- Environment variable presence

**Features:**
- Composite system fingerprinting
- Baseline establishment
- Change identification and classification
- JSON-based state persistence
- Automatic state retention

**Use Cases:**
- Detect unauthorized config changes
- Track infrastructure topology changes
- Identify missing environment variables
- Monitor service deployment changes

**Check Interval:** 5 minutes (configurable)

---

### 5. Recovery Manager (`recovery.py` - 400 lines)

**Responsibility:** Automatic service recovery actions

**Key Classes:**
- `RecoveryManager`: Auto-recovery coordinator
- `RecoveryResult`: Recovery action outcome
- `RecoveryAttempt`: Recovery attempt record
- `RecoveryAction`: Enum (RESTART_SERVICE, ALERT_ONLY, NONE)

**Features:**
- Systemd service restart capability
- Intelligent cooldown logic (5 minutes)
- Maximum attempt limiting (3 attempts)
- Persistent attempt history
- Per-service configuration

**Recovery Logic:**
```
Service Failure Detected
    ↓
Check if auto-restart enabled
    ↓
Check attempt count < max (3)
    ↓
Check cooldown period (5 min)
    ↓
Execute: systemctl restart <service>
    ↓
Verify: systemctl is-active <service>
    ↓
Record attempt + Send alert
```

**Cooldown Strategy:**
- Track last 3 attempts within 5-minute window
- Reset counter after cooldown expires
- Prevent restart loops
- Manual reset available

---

### 6. Alert Manager (`alerts.py` - 403 lines)

**Responsibility:** Multi-channel alert routing and delivery

**Key Classes:**
- `AlertManager`: Alert routing coordinator
- `Alert`: Alert message dataclass
- `AlertSeverity`: Enum (CRITICAL, WARNING, INFO)

**Alert Channels:**
1. **Telegram**: Real-time critical/warning alerts
2. **Log File**: All alerts with structured format
3. **Axiom**: (Future) Centralized log aggregation

**Features:**
- Severity-based routing
- Alert deduplication (5-minute window)
- Daily digest compilation (8 AM)
- Rate limiting protection
- Markdown formatting for Telegram

**Routing Logic:**
- **CRITICAL**: Telegram + Log
- **WARNING**: Telegram + Log
- **INFO**: Log only

**Daily Digest:**
- Compiled at 8 AM daily
- Summary statistics (critical/warning/info counts)
- Top 5 issues per severity
- Sent via Telegram and logged

---

### 7. Main Orchestrator (`main.py` - 442 lines)

**Responsibility:** Coordinate all subsystems

**Key Components:**
- `WatchdogOrchestrator`: Main coordinator class
- 5 concurrent monitoring loops:
  1. Health check loop (5 min)
  2. Drift detection loop (5 min)
  3. API validation loop (15 min)
  4. Fingerprint loop (5 min)
  5. Daily digest loop (scheduled)

**Startup Sequence:**
1. Load configuration from `watchdog.yaml`
2. Initialize all subsystems
3. Create state directories
4. Start monitoring loops
5. Send startup notification
6. Enter continuous monitoring mode

**Shutdown Sequence:**
1. Receive SIGTERM/SIGINT
2. Set `running = False`
3. Cancel all async tasks
4. Wait for task completion
5. Send shutdown notification
6. Clean exit

**Error Handling:**
- Individual loop failures isolated
- Automatic retry with backoff
- Comprehensive error logging
- Graceful degradation

---

## Data Flow

### Health Check Flow
```
Timer (5 min)
    ↓
HealthChecker.check_all()
    ↓
Concurrent HTTP requests to nodes
Systemctl checks for services
    ↓
HealthReport generated
    ↓
If UNHEALTHY:
    ↓
RecoveryManager.handle_service_failure()
    ↓
AlertManager.send_critical()
    ↓
Telegram + Log
```

### Drift Detection Flow
```
Timer (5 min)
    ↓
DriftDetector.check_drift()
    ↓
Compute file hashes
Compare to baselines
    ↓
If changed:
    ↓
Create backup
Analyze severity
Update baseline
    ↓
DriftReport generated
    ↓
AlertManager.send_alert()
    ↓
Routed by severity
```

### API Validation Flow
```
Timer (15 min)
    ↓
APIValidator.validate_all()
    ↓
Concurrent API test requests
    ↓
KeyStatus results
    ↓
If any invalid:
    ↓
AlertManager.send_critical()
    ↓
Immediate Telegram alert
```

## State Management

### Directory Structure
```
/root/.pepper-watchdog/
├── baselines/                    # Config file hashes
│   ├── openclaw.json.hash
│   └── config.yaml.hash
├── config_backups/               # Timestamped backups
│   ├── openclaw.json.20260214_120000.bak
│   └── config.yaml.20260214_120500.bak
├── recovery_attempts.json        # Recovery attempt history
├── system_fingerprint.json       # Current fingerprint
├── daily_alerts.json             # Today's alerts for digest
└── alerts.log                    # Alert log file
```

### State Persistence

**Baselines** (`baselines/`)
- SHA256 hashes of monitored files
- Updated after drift detected
- Persistent across restarts

**Backups** (`config_backups/`)
- Created before config changes
- Timestamped for tracking
- Retention: last 10 backups per file

**Recovery Attempts** (`recovery_attempts.json`)
```json
{
  "pepper": [
    "2026-02-14T20:15:00",
    "2026-02-14T20:20:00"
  ]
}
```

**Fingerprint** (`system_fingerprint.json`)
```json
{
  "timestamp": "2026-02-14T20:30:00",
  "fingerprint": "a1b2c3d4...",
  "details": {
    "files": {...},
    "env_vars": {...},
    "services": {...},
    "nodes": {...}
  }
}
```

## Configuration

### Primary Config (`watchdog.yaml`)
```yaml
version: "1.0.0"
state_dir: "/root/.pepper-watchdog"

health:
  interval_seconds: 300
  timeout_seconds: 10
  nodes: [...]
  services: [...]

drift:
  enabled: true
  backup_on_change: true
  monitored_files: [...]

api_validation:
  interval_seconds: 900
  providers: [...]

fingerprint:
  interval_seconds: 300
  monitored_files: [...]
  monitored_env_vars: [...]

recovery:
  enabled: true
  max_attempts: 3
  cooldown_minutes: 5

alerts:
  telegram:
    enabled: true
    bot_token: ${PEPPER_PRIME_TOKEN}
    chat_id: "8445149012"
  severity_routing: {...}
  daily_digest:
    enabled: true
    hour: 8
```

## Deployment

### Systemd Service
- **Service Name**: `pepper-watchdog.service`
- **User**: root
- **Restart Policy**: Always (with 10s delay)
- **Resource Limits**: 256 MB RAM, 10% CPU
- **Dependencies**: After network + pepper.service

### Installation
```bash
cd /root/pepper/watchdog
./deploy.sh
```

### Verification
```bash
systemctl status pepper-watchdog
journalctl -u pepper-watchdog -f
```

## Performance

### Resource Usage
- **Memory**: 50-100 MB (steady state)
- **CPU**: <1% (idle), ~5% (during checks)
- **Network**: ~1 KB/s average
- **Disk**: 10-50 MB (state files)

### Scalability
- Supports monitoring 10+ nodes
- Handles 20+ services
- Scales linearly with check count
- Concurrent health checks (async)

## Security

### Credentials
- API keys in environment variables (not config)
- State directory: 700 permissions (root only)
- Telegram chat ID whitelist
- No sensitive data in logs

### Attack Surface
- Read-only config file access
- Systemd service restart capability (contained)
- HTTP requests to known endpoints only
- No shell command injection vectors

## Future Enhancements

### Planned Features
- [ ] Axiom log shipping integration
- [ ] Webhook alert endpoint
- [ ] Custom recovery scripts
- [ ] Performance trend analysis
- [ ] Predictive failure detection
- [ ] Web dashboard (real-time)
- [ ] Multi-region support
- [ ] SMS alerts (Twilio)
- [ ] Email alerts (SMTP)
- [ ] Slack integration

### Extensibility Points
- New alert channels (add to `alerts.py`)
- Custom health checks (extend `health.py`)
- Additional API validators (add to `api_validator.py`)
- Custom recovery actions (extend `recovery.py`)

## Integration Points

### With PEPPER
- Monitors PEPPER service health
- Auto-restarts PEPPER on failure
- Alerts on PEPPER config changes
- Independent operation (no dependency)

### With Digital Twin Nodes
- Monitors PLC Laptop (100.72.2.99)
- Monitors Travel Laptop (100.83.251.23)
- Monitors VPS Gateway (localhost:18789)
- Monitors Matrix API (100.72.2.99:8000)

### With External Services
- Telegram (alerts)
- Groq (API validation)
- Anthropic (API validation)
- Axiom (future logging)

---

**Architecture Version:** 1.0.0
**Last Updated:** 2026-02-14
**Production Ready:** Yes
**Demo Ready:** Yes (Feb 10, 2026)
