# PEPPER Watchdog & Drift Detection System

**Addendum to PEPPER_SYSTEM_PRD.md**
**Version:** 1.0
**Created:** 2026-02-14

---

## Overview

The Watchdog system provides:
1. **Health Checks** — Regular pings to all services/nodes
2. **Config Drift Detection** — Alert when configs change unexpectedly
3. **API Key Validation** — Verify keys still work before they fail
4. **Route Verification** — Test endpoints respond correctly
5. **Structural Fingerprinting** — Detect file/code changes
6. **Auto-Recovery** — Restart failed services automatically

---

## 1. ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────────┐
│                       WATCHDOG SERVICE                              │
│                      (runs on VPS every 5m)                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Health       │  │ Config       │  │ API Key      │              │
│  │ Checker      │  │ Drift        │  │ Validator    │              │
│  │              │  │ Detector     │  │              │              │
│  │ • Node pings │  │ • Hash check │  │ • Test calls │              │
│  │ • Service    │  │ • Diff alert │  │ • Expiry     │              │
│  │   status     │  │ • Backup     │  │   warning    │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                 │                       │
│         └─────────────────┼─────────────────┘                       │
│                           │                                         │
│                           ▼                                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    STATE STORE                               │   │
│  │                                                              │   │
│  │  /root/.pepper-watchdog/                                     │   │
│  │  ├── state.json         # Current state snapshot             │   │
│  │  ├── baseline.json      # Known-good baseline                │   │
│  │  ├── history/           # Historical snapshots               │   │
│  │  │   └── 2026-02-14_1200.json                               │   │
│  │  ├── backups/           # Config backups                     │   │
│  │  │   └── openclaw.json.2026-02-14                           │   │
│  │  └── alerts.log         # Alert history                      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                           │                                         │
│                           ▼                                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    ALERT ENGINE                              │   │
│  │                                                              │   │
│  │  Severity Levels:                                            │   │
│  │  🔴 CRITICAL — Node down, API key invalid, service crash     │   │
│  │  🟠 WARNING  — Config drift, key expiring, high latency      │   │
│  │  🟢 INFO     — Backup completed, baseline updated            │   │
│  │                                                              │   │
│  │  Channels:                                                   │   │
│  │  • Telegram → Mike (CRITICAL + WARNING)                      │   │
│  │  • Log file → All events                                     │   │
│  │  • Axiom → Structured logs                                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. HEALTH CHECK MATRIX

### 2.1 Node Health

| Check | Endpoint | Frequency | Timeout | Recovery |
|-------|----------|-----------|---------|----------|
| PLC Laptop | `http://100.72.2.99:8765/health` | 5m | 10s | Alert only |
| Travel Laptop | `http://100.83.251.23:8765/health` | 5m | 10s | Alert only |
| VPS Gateway | `http://localhost:18789/health` | 1m | 5s | Auto-restart |
| Matrix API | `http://100.72.2.99:8000/health` | 5m | 10s | Alert only |
| Clawdbot | `systemctl is-active clawdbot` | 1m | 5s | Auto-restart |
| PEPPER | `systemctl is-active pepper` | 1m | 5s | Auto-restart |

### 2.2 Service Dependencies

| Service | Dependency | Test | Frequency |
|---------|------------|------|-----------|
| Groq API | API Key | `POST /chat/completions` with 1 token | 15m |
| Claude API | API Key | `POST /messages` with 1 token | 15m |
| Telegram API | Bot Token | `getMe` endpoint | 5m |
| Google API | API Key | Test endpoint | 15m |

### 2.3 Health Response Schema

```json
{
  "timestamp": "2026-02-14T12:00:00Z",
  "checks": {
    "nodes": {
      "plc": {"status": "up", "latency_ms": 45, "last_seen": "2026-02-14T11:59:55Z"},
      "travel": {"status": "down", "latency_ms": null, "last_seen": "2026-02-14T10:30:00Z"},
      "vps": {"status": "up", "latency_ms": 2, "last_seen": "2026-02-14T11:59:59Z"}
    },
    "services": {
      "pepper": {"status": "running", "pid": 12345, "uptime": "2h 15m"},
      "clawdbot": {"status": "running", "pid": 12346, "uptime": "5d 3h"}
    },
    "apis": {
      "groq": {"status": "valid", "tested": "2026-02-14T11:45:00Z"},
      "claude": {"status": "valid", "tested": "2026-02-14T11:45:00Z"},
      "telegram": {"status": "valid", "tested": "2026-02-14T11:55:00Z"}
    }
  },
  "alerts": [],
  "overall": "healthy"
}
```

---

## 3. CONFIG DRIFT DETECTION

### 3.1 Monitored Files

| File | Location | Hash Algorithm | Backup On Change |
|------|----------|----------------|------------------|
| OpenClaw config | `/root/.openclaw/openclaw.json` | SHA-256 | Yes |
| PEPPER config | `/root/pepper/config.yaml` | SHA-256 | Yes |
| Jarvis Node config | `~/.jarvis/config.json` | SHA-256 | Yes |
| Bot tokens | Doppler (via API) | Compare values | N/A |
| Node URLs | In configs | Compare values | Yes |
| Model settings | In configs | Compare values | Yes |

### 3.2 Drift Detection Logic

```python
# watchdog/drift_detector.py

import hashlib
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class DriftAlert:
    file: str
    field: Optional[str]
    old_value: str
    new_value: str
    severity: str  # "critical", "warning", "info"
    timestamp: str

class DriftDetector:
    """Detects configuration drift from baseline."""

    CRITICAL_FIELDS = [
        "channels.telegram.botToken",
        "env.GROQ_API_KEY",
        "env.SENDGRID_API_KEY",
        "gateway.auth.token",
    ]

    WARNING_FIELDS = [
        "agents.defaults.model.primary",
        "channels.telegram.allowFrom",
        "gateway.port",
        "nodes.*.url",
    ]

    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.baseline_file = state_dir / "baseline.json"
        self.state_file = state_dir / "state.json"
        self.backup_dir = state_dir / "backups"
        self.backup_dir.mkdir(exist_ok=True)

    def hash_file(self, path: Path) -> str:
        """Generate SHA-256 hash of file."""
        if not path.exists():
            return "FILE_NOT_FOUND"
        content = path.read_bytes()
        return hashlib.sha256(content).hexdigest()

    def hash_config(self, config: dict) -> str:
        """Generate hash of config dict (sorted for consistency)."""
        content = json.dumps(config, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def get_nested_value(self, d: dict, path: str):
        """Get value at nested path like 'a.b.c'."""
        keys = path.split(".")
        for key in keys:
            if key == "*":
                return d  # Wildcard, return whole dict
            if isinstance(d, dict) and key in d:
                d = d[key]
            else:
                return None
        return d

    def compare_configs(
        self,
        baseline: dict,
        current: dict,
        path: str = ""
    ) -> List[DriftAlert]:
        """Recursively compare two configs and return differences."""
        alerts = []

        all_keys = set(baseline.keys()) | set(current.keys())

        for key in all_keys:
            current_path = f"{path}.{key}" if path else key

            old_val = baseline.get(key)
            new_val = current.get(key)

            if old_val == new_val:
                continue

            # Determine severity
            severity = "info"
            for pattern in self.CRITICAL_FIELDS:
                if self._matches_pattern(current_path, pattern):
                    severity = "critical"
                    break
            if severity == "info":
                for pattern in self.WARNING_FIELDS:
                    if self._matches_pattern(current_path, pattern):
                        severity = "warning"
                        break

            if isinstance(old_val, dict) and isinstance(new_val, dict):
                # Recurse into nested dicts
                alerts.extend(self.compare_configs(old_val, new_val, current_path))
            else:
                # Value changed
                alerts.append(DriftAlert(
                    file="config",
                    field=current_path,
                    old_value=self._safe_str(old_val),
                    new_value=self._safe_str(new_val),
                    severity=severity,
                    timestamp=datetime.now().isoformat()
                ))

        return alerts

    def _matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if path matches pattern (supports * wildcard)."""
        pattern_parts = pattern.split(".")
        path_parts = path.split(".")

        if len(pattern_parts) != len(path_parts):
            return False

        for p, v in zip(pattern_parts, path_parts):
            if p != "*" and p != v:
                return False
        return True

    def _safe_str(self, val) -> str:
        """Convert value to string, masking sensitive data."""
        s = str(val)
        # Mask anything that looks like a token/key
        if len(s) > 20 and any(c in s for c in ["-", "_"]):
            return s[:8] + "..." + s[-4:]
        return s

    def backup_config(self, path: Path):
        """Backup config file before changes."""
        if not path.exists():
            return

        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        backup_path = self.backup_dir / f"{path.name}.{timestamp}"
        backup_path.write_bytes(path.read_bytes())

        # Keep only last 10 backups
        backups = sorted(self.backup_dir.glob(f"{path.name}.*"))
        for old_backup in backups[:-10]:
            old_backup.unlink()

    def set_baseline(self, config: dict):
        """Set current config as the known-good baseline."""
        self.baseline_file.write_text(json.dumps(config, indent=2))

    def check_drift(self, current_config: dict) -> List[DriftAlert]:
        """Check current config against baseline."""
        if not self.baseline_file.exists():
            # First run, set baseline
            self.set_baseline(current_config)
            return []

        baseline = json.loads(self.baseline_file.read_text())
        return self.compare_configs(baseline, current_config)
```

### 3.3 What Triggers Alerts

| Change Type | Severity | Example | Action |
|-------------|----------|---------|--------|
| Bot token changed | 🔴 CRITICAL | `botToken` modified | Immediate alert + backup |
| API key changed | 🔴 CRITICAL | `GROQ_API_KEY` modified | Immediate alert + backup |
| Allowlist changed | 🟠 WARNING | User added/removed | Alert + log |
| Model changed | 🟠 WARNING | `claude-sonnet` → `claude-opus` | Alert + log |
| Port changed | 🟠 WARNING | `18789` → `18790` | Alert + log |
| Node URL changed | 🟠 WARNING | IP address changed | Alert + log |
| New field added | 🟢 INFO | New config option | Log only |
| Formatting change | 🟢 INFO | Whitespace | Ignore |

---

## 4. API KEY VALIDATION

### 4.1 Key Test Matrix

```python
# watchdog/api_validator.py

from dataclasses import dataclass
from typing import Optional
import httpx
from datetime import datetime

@dataclass
class KeyStatus:
    provider: str
    valid: bool
    error: Optional[str]
    tested_at: str
    expires_at: Optional[str]  # If known

class APIValidator:
    """Validates API keys are still working."""

    async def validate_groq(self, api_key: str) -> KeyStatus:
        """Test Groq API key with minimal request."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "llama-3.1-8b-instant",
                        "messages": [{"role": "user", "content": "1"}],
                        "max_tokens": 1
                    },
                    timeout=10
                )

                if response.status_code == 200:
                    return KeyStatus("groq", True, None, datetime.now().isoformat(), None)
                elif response.status_code == 401:
                    return KeyStatus("groq", False, "Invalid API key", datetime.now().isoformat(), None)
                elif response.status_code == 429:
                    return KeyStatus("groq", True, "Rate limited but valid", datetime.now().isoformat(), None)
                else:
                    return KeyStatus("groq", False, f"HTTP {response.status_code}", datetime.now().isoformat(), None)
        except Exception as e:
            return KeyStatus("groq", False, str(e), datetime.now().isoformat(), None)

    async def validate_anthropic(self, api_key: str) -> KeyStatus:
        """Test Anthropic API key with minimal request."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "1"}]
                    },
                    timeout=10
                )

                if response.status_code == 200:
                    return KeyStatus("anthropic", True, None, datetime.now().isoformat(), None)
                elif response.status_code == 401:
                    return KeyStatus("anthropic", False, "Invalid API key", datetime.now().isoformat(), None)
                else:
                    return KeyStatus("anthropic", False, f"HTTP {response.status_code}", datetime.now().isoformat(), None)
        except Exception as e:
            return KeyStatus("anthropic", False, str(e), datetime.now().isoformat(), None)

    async def validate_telegram(self, bot_token: str) -> KeyStatus:
        """Test Telegram bot token."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.telegram.org/bot{bot_token}/getMe",
                    timeout=10
                )

                data = response.json()
                if data.get("ok"):
                    return KeyStatus("telegram", True, None, datetime.now().isoformat(), None)
                else:
                    return KeyStatus("telegram", False, data.get("description", "Unknown error"), datetime.now().isoformat(), None)
        except Exception as e:
            return KeyStatus("telegram", False, str(e), datetime.now().isoformat(), None)

    async def validate_all(self, keys: dict) -> dict:
        """Validate all configured API keys."""
        results = {}

        if "groq" in keys:
            results["groq"] = await self.validate_groq(keys["groq"])

        if "anthropic" in keys:
            results["anthropic"] = await self.validate_anthropic(keys["anthropic"])

        if "telegram" in keys:
            results["telegram"] = await self.validate_telegram(keys["telegram"])

        return results
```

### 4.2 Key Expiry Warnings

Some APIs have usage limits or expiring keys. Track:

| Provider | Expiry Type | Warning Threshold | Check Method |
|----------|-------------|-------------------|--------------|
| Groq | Monthly credits | <10% remaining | API response headers |
| Anthropic | Monthly credits | <10% remaining | API response headers |
| Telegram | Never expires | N/A | Just validate |
| SendGrid | Monthly sends | <1000 remaining | Dashboard API |

---

## 5. STRUCTURAL FINGERPRINTING

### 5.1 What to Fingerprint

```python
# watchdog/fingerprint.py

from dataclasses import dataclass
from typing import Dict, List
import hashlib
import json
from pathlib import Path

@dataclass
class Fingerprint:
    """Structural fingerprint of the system."""
    timestamp: str

    # File hashes
    config_hashes: Dict[str, str]

    # Service states
    services: Dict[str, str]  # service -> status

    # Network topology
    nodes: Dict[str, bool]    # node -> reachable

    # API endpoints
    endpoints: Dict[str, int] # endpoint -> status_code

    # Environment
    env_vars: List[str]       # List of defined env vars (not values)

class SystemFingerprint:
    """Generate and compare system fingerprints."""

    MONITORED_FILES = [
        "/root/.openclaw/openclaw.json",
        "/root/pepper/config.yaml",
        "/root/.jarvis/config.json",
        "/etc/systemd/system/pepper.service",
        "/etc/systemd/system/clawdbot.service",
    ]

    MONITORED_SERVICES = [
        "pepper",
        "clawdbot",
        "nginx",
        "docker",
    ]

    MONITORED_ENDPOINTS = [
        ("http://100.72.2.99:8765/health", "plc"),
        ("http://100.83.251.23:8765/health", "travel"),
        ("http://localhost:18789/health", "gateway"),
        ("http://100.72.2.99:8000/health", "matrix"),
    ]

    ENV_VARS_TO_CHECK = [
        "GROQ_API_KEY",
        "ANTHROPIC_API_KEY",
        "TELEGRAM_BOT_TOKEN",
        "PEPPER_PRIME_TOKEN",
        "FACTORYLM_BOT_TOKEN",
        "GOOGLE_API_KEY",
        "SENDGRID_API_KEY",
    ]

    def generate(self) -> Fingerprint:
        """Generate current system fingerprint."""
        from datetime import datetime
        import subprocess
        import httpx
        import os

        # Hash monitored files
        config_hashes = {}
        for file_path in self.MONITORED_FILES:
            path = Path(file_path)
            if path.exists():
                content = path.read_bytes()
                config_hashes[file_path] = hashlib.sha256(content).hexdigest()[:16]
            else:
                config_hashes[file_path] = "NOT_FOUND"

        # Check service states
        services = {}
        for service in self.MONITORED_SERVICES:
            result = subprocess.run(
                ["systemctl", "is-active", service],
                capture_output=True, text=True
            )
            services[service] = result.stdout.strip()

        # Check node reachability
        nodes = {}
        for url, name in self.MONITORED_ENDPOINTS:
            try:
                response = httpx.get(url, timeout=5)
                nodes[name] = response.status_code == 200
            except:
                nodes[name] = False

        # Check endpoint responses
        endpoints = {}
        for url, name in self.MONITORED_ENDPOINTS:
            try:
                response = httpx.get(url, timeout=5)
                endpoints[name] = response.status_code
            except:
                endpoints[name] = 0

        # Check which env vars are defined
        env_vars = [v for v in self.ENV_VARS_TO_CHECK if os.getenv(v)]

        return Fingerprint(
            timestamp=datetime.now().isoformat(),
            config_hashes=config_hashes,
            services=services,
            nodes=nodes,
            endpoints=endpoints,
            env_vars=env_vars
        )

    def compare(self, baseline: Fingerprint, current: Fingerprint) -> List[str]:
        """Compare two fingerprints and return differences."""
        diffs = []

        # Config hash changes
        for file, old_hash in baseline.config_hashes.items():
            new_hash = current.config_hashes.get(file, "REMOVED")
            if old_hash != new_hash:
                diffs.append(f"CONFIG_CHANGED: {file} ({old_hash} -> {new_hash})")

        # Service state changes
        for service, old_state in baseline.services.items():
            new_state = current.services.get(service, "unknown")
            if old_state != new_state:
                diffs.append(f"SERVICE_CHANGED: {service} ({old_state} -> {new_state})")

        # Node reachability changes
        for node, was_up in baseline.nodes.items():
            is_up = current.nodes.get(node, False)
            if was_up and not is_up:
                diffs.append(f"NODE_DOWN: {node}")
            elif not was_up and is_up:
                diffs.append(f"NODE_UP: {node}")

        # Endpoint response changes
        for endpoint, old_code in baseline.endpoints.items():
            new_code = current.endpoints.get(endpoint, 0)
            if old_code != new_code:
                diffs.append(f"ENDPOINT_CHANGED: {endpoint} ({old_code} -> {new_code})")

        # Env var changes
        old_vars = set(baseline.env_vars)
        new_vars = set(current.env_vars)
        for added in new_vars - old_vars:
            diffs.append(f"ENV_ADDED: {added}")
        for removed in old_vars - new_vars:
            diffs.append(f"ENV_REMOVED: {removed}")

        return diffs
```

---

## 6. AUTO-RECOVERY

### 6.1 Recovery Actions

| Condition | Action | Max Attempts | Cooldown |
|-----------|--------|--------------|----------|
| PEPPER service stopped | `systemctl restart pepper` | 3 | 5m |
| Clawdbot service stopped | `systemctl restart clawdbot` | 3 | 5m |
| Gateway not responding | Restart service | 3 | 5m |
| Node offline | Alert only (can't restart remote) | N/A | N/A |
| API key invalid | Alert + try backup key | 1 | N/A |

### 6.2 Recovery Script

```python
# watchdog/recovery.py

import subprocess
from datetime import datetime, timedelta
from typing import Dict, Optional
from dataclasses import dataclass

@dataclass
class RecoveryAttempt:
    service: str
    timestamp: datetime
    success: bool
    error: Optional[str]

class RecoveryEngine:
    """Automatically recover from common failures."""

    def __init__(self):
        self.attempts: Dict[str, list] = {}
        self.max_attempts = 3
        self.cooldown = timedelta(minutes=5)

    def can_attempt_recovery(self, service: str) -> bool:
        """Check if we should attempt recovery (respecting limits)."""
        if service not in self.attempts:
            return True

        recent = [a for a in self.attempts[service]
                  if a.timestamp > datetime.now() - self.cooldown]

        return len(recent) < self.max_attempts

    def restart_service(self, service: str) -> RecoveryAttempt:
        """Attempt to restart a systemd service."""
        attempt = RecoveryAttempt(
            service=service,
            timestamp=datetime.now(),
            success=False,
            error=None
        )

        if not self.can_attempt_recovery(service):
            attempt.error = "Max recovery attempts exceeded"
            return attempt

        try:
            # Stop first
            subprocess.run(
                ["systemctl", "stop", service],
                timeout=10, check=False
            )

            # Start
            result = subprocess.run(
                ["systemctl", "start", service],
                timeout=30, capture_output=True, text=True
            )

            if result.returncode == 0:
                attempt.success = True
            else:
                attempt.error = result.stderr

        except Exception as e:
            attempt.error = str(e)

        # Record attempt
        if service not in self.attempts:
            self.attempts[service] = []
        self.attempts[service].append(attempt)

        return attempt

    def try_backup_api_key(self, provider: str) -> bool:
        """Try to switch to backup API key."""
        # This would integrate with Doppler or a backup key store
        # For now, just return False
        return False
```

---

## 7. ALERT SYSTEM

### 7.1 Alert Routing

```python
# watchdog/alerts.py

from dataclasses import dataclass
from typing import List, Optional
from enum import Enum
import httpx
from datetime import datetime

class AlertSeverity(Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"

@dataclass
class Alert:
    severity: AlertSeverity
    title: str
    message: str
    timestamp: str
    source: str  # "health", "drift", "api", "recovery"

class AlertEngine:
    """Route alerts to appropriate channels."""

    def __init__(self, telegram_token: str, mike_chat_id: str):
        self.telegram_token = telegram_token
        self.mike_chat_id = mike_chat_id
        self.alert_log: List[Alert] = []

    def severity_emoji(self, severity: AlertSeverity) -> str:
        return {
            AlertSeverity.CRITICAL: "🔴",
            AlertSeverity.WARNING: "🟠",
            AlertSeverity.INFO: "🟢"
        }[severity]

    async def send_telegram(self, alert: Alert):
        """Send alert to Mike via Telegram."""
        emoji = self.severity_emoji(alert.severity)
        message = f"{emoji} **{alert.title}**\n\n{alert.message}\n\n_Source: {alert.source}_"

        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{self.telegram_token}/sendMessage",
                json={
                    "chat_id": self.mike_chat_id,
                    "text": message,
                    "parse_mode": "Markdown"
                }
            )

    def log_alert(self, alert: Alert):
        """Log alert to file."""
        self.alert_log.append(alert)

        # Also write to file
        with open("/root/.pepper-watchdog/alerts.log", "a") as f:
            f.write(f"{alert.timestamp} [{alert.severity.value}] {alert.title}: {alert.message}\n")

    async def dispatch(self, alert: Alert):
        """Route alert to appropriate channels."""
        # Always log
        self.log_alert(alert)

        # Send to Telegram for CRITICAL and WARNING
        if alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.WARNING]:
            await self.send_telegram(alert)

    async def send_digest(self):
        """Send daily digest of all alerts."""
        critical = [a for a in self.alert_log if a.severity == AlertSeverity.CRITICAL]
        warnings = [a for a in self.alert_log if a.severity == AlertSeverity.WARNING]

        message = f"📊 **Daily Watchdog Digest**\n\n"
        message += f"🔴 Critical: {len(critical)}\n"
        message += f"🟠 Warnings: {len(warnings)}\n"
        message += f"🟢 All Clear: {len(critical) == 0 and len(warnings) == 0}\n"

        if critical:
            message += f"\n**Critical Issues:**\n"
            for a in critical[:5]:
                message += f"• {a.title}\n"

        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{self.telegram_token}/sendMessage",
                json={
                    "chat_id": self.mike_chat_id,
                    "text": message,
                    "parse_mode": "Markdown"
                }
            )

        # Clear log after digest
        self.alert_log = []
```

---

## 8. MAIN WATCHDOG SERVICE

```python
# watchdog/main.py

import asyncio
import json
from pathlib import Path
from datetime import datetime

from .health_checker import HealthChecker
from .drift_detector import DriftDetector
from .api_validator import APIValidator
from .fingerprint import SystemFingerprint
from .recovery import RecoveryEngine
from .alerts import AlertEngine, Alert, AlertSeverity

class PepperWatchdog:
    """Main watchdog service orchestrating all checks."""

    def __init__(self, config_path: Path):
        self.config = json.loads(config_path.read_text())
        self.state_dir = Path("/root/.pepper-watchdog")
        self.state_dir.mkdir(exist_ok=True)

        self.health = HealthChecker()
        self.drift = DriftDetector(self.state_dir)
        self.api = APIValidator()
        self.fingerprint = SystemFingerprint()
        self.recovery = RecoveryEngine()
        self.alerts = AlertEngine(
            telegram_token=self.config["telegram"]["watchdog_token"],
            mike_chat_id=self.config["telegram"]["mike_chat_id"]
        )

    async def run_health_checks(self):
        """Run all health checks."""
        results = await self.health.check_all()

        for node, status in results["nodes"].items():
            if not status["up"]:
                await self.alerts.dispatch(Alert(
                    severity=AlertSeverity.CRITICAL,
                    title=f"Node Down: {node}",
                    message=f"{node} is not responding. Last seen: {status.get('last_seen', 'unknown')}",
                    timestamp=datetime.now().isoformat(),
                    source="health"
                ))

        for service, status in results["services"].items():
            if status != "active":
                # Try recovery
                attempt = self.recovery.restart_service(service)
                if attempt.success:
                    await self.alerts.dispatch(Alert(
                        severity=AlertSeverity.WARNING,
                        title=f"Service Recovered: {service}",
                        message=f"{service} was down but auto-restarted successfully.",
                        timestamp=datetime.now().isoformat(),
                        source="recovery"
                    ))
                else:
                    await self.alerts.dispatch(Alert(
                        severity=AlertSeverity.CRITICAL,
                        title=f"Service Down: {service}",
                        message=f"{service} is down and recovery failed: {attempt.error}",
                        timestamp=datetime.now().isoformat(),
                        source="health"
                    ))

    async def run_drift_check(self):
        """Check for config drift."""
        # Load current config
        config_path = Path("/root/.openclaw/openclaw.json")
        if not config_path.exists():
            return

        current = json.loads(config_path.read_text())
        alerts = self.drift.check_drift(current)

        for alert in alerts:
            if alert.severity == "critical":
                # Backup before alerting
                self.drift.backup_config(config_path)

                await self.alerts.dispatch(Alert(
                    severity=AlertSeverity.CRITICAL,
                    title=f"Config Changed: {alert.field}",
                    message=f"Critical config changed!\n{alert.old_value} -> {alert.new_value}",
                    timestamp=datetime.now().isoformat(),
                    source="drift"
                ))
            elif alert.severity == "warning":
                await self.alerts.dispatch(Alert(
                    severity=AlertSeverity.WARNING,
                    title=f"Config Changed: {alert.field}",
                    message=f"{alert.old_value} -> {alert.new_value}",
                    timestamp=datetime.now().isoformat(),
                    source="drift"
                ))

    async def run_api_validation(self):
        """Validate all API keys."""
        keys = {
            "groq": self.config["env"]["GROQ_API_KEY"],
            "telegram": self.config["channels"]["telegram"]["botToken"],
        }

        results = await self.api.validate_all(keys)

        for provider, status in results.items():
            if not status.valid:
                await self.alerts.dispatch(Alert(
                    severity=AlertSeverity.CRITICAL,
                    title=f"API Key Invalid: {provider}",
                    message=f"{provider} API key is no longer valid: {status.error}",
                    timestamp=datetime.now().isoformat(),
                    source="api"
                ))

    async def run_fingerprint_check(self):
        """Check system fingerprint for structural changes."""
        current = self.fingerprint.generate()

        baseline_path = self.state_dir / "fingerprint_baseline.json"
        if baseline_path.exists():
            baseline_data = json.loads(baseline_path.read_text())
            # Reconstruct Fingerprint from dict
            from dataclasses import fields
            baseline = self.fingerprint.__class__(**baseline_data)

            diffs = self.fingerprint.compare(baseline, current)

            for diff in diffs:
                severity = AlertSeverity.WARNING
                if "DOWN" in diff or "REMOVED" in diff:
                    severity = AlertSeverity.CRITICAL

                await self.alerts.dispatch(Alert(
                    severity=severity,
                    title="Structural Change Detected",
                    message=diff,
                    timestamp=datetime.now().isoformat(),
                    source="fingerprint"
                ))

        # Save current as baseline
        baseline_path.write_text(json.dumps(current.__dict__, indent=2))

    async def run_cycle(self):
        """Run one complete watchdog cycle."""
        await self.run_health_checks()
        await self.run_drift_check()
        await self.run_api_validation()
        await self.run_fingerprint_check()

    async def run_forever(self, interval: int = 300):
        """Run watchdog continuously."""
        while True:
            try:
                await self.run_cycle()
            except Exception as e:
                await self.alerts.dispatch(Alert(
                    severity=AlertSeverity.CRITICAL,
                    title="Watchdog Error",
                    message=f"Watchdog itself encountered an error: {e}",
                    timestamp=datetime.now().isoformat(),
                    source="watchdog"
                ))

            await asyncio.sleep(interval)

# Entry point
if __name__ == "__main__":
    import sys
    config_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/root/pepper/watchdog.yaml")
    watchdog = PepperWatchdog(config_path)
    asyncio.run(watchdog.run_forever())
```

---

## 9. BACKUP SCHEDULE

| Backup | Frequency | Retention | Location |
|--------|-----------|-----------|----------|
| OpenClaw config | On change + daily | 30 days | `/root/.pepper-watchdog/backups/` |
| PEPPER config | On change + daily | 30 days | `/root/.pepper-watchdog/backups/` |
| System fingerprint | Every 5m | 7 days | `/root/.pepper-watchdog/history/` |
| Alert log | Daily rotation | 90 days | `/root/.pepper-watchdog/alerts/` |
| Full state snapshot | Daily | 30 days | Google Drive (via rclone) |

---

## 10. SYSTEMD SERVICE

```ini
# /etc/systemd/system/pepper-watchdog.service

[Unit]
Description=PEPPER Watchdog Service
After=network.target pepper.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/pepper
ExecStart=/usr/bin/python3 -m watchdog.main /root/pepper/watchdog.yaml
Restart=always
RestartSec=30
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

---

## 11. QUICK COMMANDS

```bash
# Start watchdog
systemctl start pepper-watchdog

# View watchdog logs
journalctl -u pepper-watchdog -f

# Force run a check cycle
python3 -m watchdog.main --once

# View current fingerprint
cat /root/.pepper-watchdog/fingerprint_baseline.json | jq

# View drift history
cat /root/.pepper-watchdog/alerts.log | grep DRIFT

# Restore config from backup
cp /root/.pepper-watchdog/backups/openclaw.json.2026-02-14 /root/.openclaw/openclaw.json

# Set new baseline (after intentional changes)
python3 -m watchdog.main --set-baseline
```

---

## 12. IMPLEMENTATION PHASE

Add to **Phase 6: Polish & Deploy**:

- [ ] Create `services/telegram/pepper/watchdog/` directory
- [ ] Implement `health_checker.py`
- [ ] Implement `drift_detector.py`
- [ ] Implement `api_validator.py`
- [ ] Implement `fingerprint.py`
- [ ] Implement `recovery.py`
- [ ] Implement `alerts.py`
- [ ] Implement `main.py`
- [ ] Create `watchdog.yaml` config
- [ ] Create `pepper-watchdog.service`
- [ ] Test all alert paths
- [ ] Set initial baseline
- [ ] Enable and start service

---

*Watchdog Spec v1.0 | PEPPER System Addendum*
