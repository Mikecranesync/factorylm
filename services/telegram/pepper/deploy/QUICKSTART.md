# PEPPER Deploy - Quick Start Guide

## Installation (One-Time Setup)

```bash
# On your VPS (as root)
cd /root/factorylm/services/telegram/pepper/deploy
./install.sh
```

This creates:
- `/root/.pepper/` - PEPPER home directory
- `/usr/local/bin/pepper` - CLI command

## Basic Commands

### 1. Check Status

```bash
pepper status
```

Shows:
- Current version
- Previous version
- Available versions
- Rollback capability

### 2. Deploy New Version

```bash
# Patch version bump (1.2.0 → 1.2.1)
pepper deploy

# Minor version bump (1.2.0 → 1.3.0)
pepper deploy --bump minor

# Major version bump (1.2.0 → 2.0.0)
pepper deploy --bump major
```

Deployment process:
1. Pre-flight checks (git clean, config valid, tests pass)
2. Create new version directory
3. Copy code and config
4. Snapshot state
5. Stop service
6. Update symlinks
7. Start service
8. Health check
9. Auto-rollback on failure

### 3. Rollback

```bash
# Rollback to previous version (<30 seconds)
pepper rollback

# Rollback to specific version
pepper rollback v1.1.2

# List rollback history
pepper rollback --list
```

### 4. View Version Details

```bash
pepper version v1.2.0
```

Shows:
- Creation timestamp
- Git commit/branch
- Changelog
- Components
- State snapshot availability

### 5. Cleanup Old Versions

```bash
# Keep 5 most recent (default)
pepper cleanup

# Keep 10 most recent
pepper cleanup --keep 10
```

## Typical Workflows

### Standard Deployment

```bash
# 1. Check current status
pepper status

# 2. Dry run to verify
pepper deploy --dry-run

# 3. Deploy for real
pepper deploy --changelog "Fix routing bug,Improve performance"

# 4. Verify deployment
pepper status
systemctl status pepper
```

### Emergency Rollback

```bash
# 1. Rollback immediately
pepper rollback

# 2. Restart service
systemctl restart pepper

# 3. Verify rollback
pepper status
systemctl status pepper
```

### Major Version Update

```bash
# 1. Ensure tests pass
cd /root/factorylm/services/telegram/pepper
./scripts/run_tests.sh

# 2. Deploy with major bump
pepper deploy --bump major --changelog "Breaking: New routing system"

# 3. Monitor closely
tail -f /root/.pepper/current/logs/pepper.log
```

### Rollback to Specific Version

```bash
# 1. List available versions
pepper status

# 2. View version details
pepper version v1.1.2

# 3. Rollback to that version
pepper rollback v1.1.2
```

## Directory Structure Reference

```
/root/.pepper/
├── current -> versions/v1.2.0/    # Active version
├── previous -> versions/v1.1.2/   # Quick rollback
├── versions/
│   ├── v1.0.0/
│   ├── v1.1.0/
│   ├── v1.1.2/
│   └── v1.2.0/
│       ├── manifest.json
│       ├── code/
│       ├── config/
│       └── state/
├── state/                         # Current runtime state
│   ├── sessions.json
│   ├── routing.json
│   ├── runtime_config.json
│   └── metrics.json
└── rollback/
    └── rollback-log.json
```

## Common Issues

### Deployment fails pre-checks

**Problem:** `Git working directory is not clean`

**Solution:**
```bash
cd /root/factorylm/services/telegram/pepper
git status
git add .
git commit -m "Your commit message"
pepper deploy
```

**Problem:** `Tests failed`

**Solution:**
```bash
./scripts/run_tests.sh  # See what's failing
# Fix issues
pepper deploy
```

**Problem:** `Configuration validation failed`

**Solution:**
```bash
# Validate JSON
python -c "import json; json.load(open('config/pepper.json'))"
```

### Rollback fails

**Problem:** `No previous version available`

**Solution:**
```bash
# Check available versions
pepper status

# Rollback to specific version
pepper rollback v1.1.0
```

### Service won't start after deploy

**Problem:** Service fails health check

**Solution:**
- Auto-rollback should have triggered
- Check logs: `tail -f /root/.pepper/current/logs/pepper.log`
- Manual rollback: `pepper rollback`
- Restart service: `systemctl restart pepper`

## Best Practices

1. **Always dry run first**
   ```bash
   pepper deploy --dry-run
   ```

2. **Add changelogs**
   ```bash
   pepper deploy --changelog "Fix bug,Add feature"
   ```

3. **Monitor after deploy**
   ```bash
   pepper deploy
   tail -f /root/.pepper/current/logs/pepper.log
   ```

4. **Regular cleanup**
   ```bash
   # Weekly
   pepper cleanup --keep 10
   ```

5. **Test before deploy**
   ```bash
   ./scripts/run_tests.sh
   pepper deploy
   ```

6. **Check status frequently**
   ```bash
   pepper status
   ```

## Integration with Systemd

Service file at `/etc/systemd/system/pepper.service`:

```ini
[Unit]
Description=PEPPER Telegram Gateway
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/.pepper/current/code
ExecStart=/usr/bin/python3 gateway.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Commands:
```bash
systemctl start pepper
systemctl stop pepper
systemctl restart pepper
systemctl status pepper
systemctl enable pepper  # Start on boot
```

## Help

```bash
# General help
pepper --help

# Command-specific help
pepper deploy --help
pepper rollback --help
```

## Full Documentation

See `README.md` for complete documentation including:
- Python API usage
- State management details
- Security considerations
- Advanced features
