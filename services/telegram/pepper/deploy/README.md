# PEPPER Deploy and Versioning System

Atomic deployment, rollback, and state management for PEPPER.

## Features

- **Semantic Versioning**: Automatic version bumping (major, minor, patch)
- **Atomic Deployments**: All-or-nothing deployments with symlink switching
- **State Management**: Snapshot and restore session/routing state
- **Fast Rollback**: <30 second rollback to previous version
- **Auto-Rollback**: Automatic rollback on deployment failure
- **Pre-Flight Checks**: Git status, config validation, test execution
- **Health Checks**: Post-deployment validation
- **Deployment History**: Complete audit trail

## Directory Structure

```
/root/.pepper/
├── current -> versions/v1.2.0/    # Symlink to active version
├── previous -> versions/v1.1.2/   # Quick rollback target
├── versions/
│   ├── v1.0.0/
│   ├── v1.1.0/
│   └── v1.2.0/
│       ├── manifest.json          # Version metadata
│       ├── code/                  # Application code
│       ├── config/                # Configuration files
│       └── state/                 # State snapshot
├── state/                         # Current runtime state
│   ├── sessions.json
│   ├── routing.json
│   ├── runtime_config.json
│   └── metrics.json
└── rollback/
    └── rollback-log.json          # Rollback history
```

## Installation

### 1. Install CLI Tool

```bash
# Copy CLI to /usr/local/bin
sudo cp cli.py /usr/local/bin/pepper
sudo chmod +x /usr/local/bin/pepper

# Or create symlink
sudo ln -s /path/to/factorylm/services/telegram/pepper/deploy/cli.py /usr/local/bin/pepper
```

### 2. Initialize PEPPER Home

```bash
mkdir -p /root/.pepper/{versions,state,rollback}
```

### 3. Configure Paths

Edit `/usr/local/bin/pepper` if your paths differ from defaults:

```python
DEFAULT_PEPPER_HOME = Path("/root/.pepper")
DEFAULT_PROJECT_ROOT = Path("/root/factorylm/services/telegram/pepper")
```

Or use CLI flags:

```bash
pepper --pepper-home /custom/path --project-root /custom/project status
```

## Usage

### Deploy New Version

```bash
# Deploy with patch version bump (1.2.0 → 1.2.1)
pepper deploy

# Deploy with minor version bump (1.2.0 → 1.3.0)
pepper deploy --bump minor

# Deploy with major version bump (1.2.0 → 2.0.0)
pepper deploy --bump major

# Dry run (simulate without changes)
pepper deploy --dry-run

# Skip tests (not recommended)
pepper deploy --skip-tests

# Add changelog
pepper deploy --changelog "Fix routing bug,Add new persona,Improve performance"
```

### Rollback

```bash
# Rollback to previous version
pepper rollback

# Rollback to specific version
pepper rollback v1.1.2

# List rollback history
pepper rollback --list
```

### Check Status

```bash
pepper status
```

Output:
```
============================================================
PEPPER DEPLOYMENT STATUS
============================================================

Current version: v1.2.0
Git commit: abc123...
Git branch: main
Deployed at: 2026-02-14T10:30:00Z

Previous version: v1.1.2

Available versions: 3
  - v1.2.0
  - v1.1.2
  - v1.1.0

Rollback available: Yes
Rollback target: v1.1.2

Rollback Statistics:
  Total rollbacks: 2
  Successful: 2
  Failed: 0
  Automatic: 1
  Success rate: 100.0%
```

### Version Information

```bash
pepper version v1.2.0
```

Output:
```
============================================================
VERSION v1.2.0
============================================================

Created: 2026-02-14T10:30:00Z
Git commit: abc123...
Git branch: main
Previous version: v1.1.2
Rollback safe: True

Changelog:
  - Fix routing bug
  - Add new persona
  - Improve performance

State Snapshot: Available
State valid: True
```

### Cleanup Old Versions

```bash
# Keep 5 most recent versions (default)
pepper cleanup

# Keep 10 most recent versions
pepper cleanup --keep 10
```

## Deployment Flow

1. **Pre-Deployment Checks**
   - Verify git working directory is clean
   - Validate configuration files
   - Run test suite (unless `--skip-tests`)

2. **Version Creation**
   - Calculate next version (patch/minor/major)
   - Create version directory structure
   - Get git commit and branch information

3. **Code and Config Snapshot**
   - Copy application code to version directory
   - Copy configuration files
   - Create deployment manifest

4. **State Snapshot**
   - Snapshot active sessions
   - Snapshot routing table
   - Snapshot runtime configuration
   - Snapshot metrics

5. **Atomic Deployment**
   - Stop current service
   - Update symlinks atomically (`current`, `previous`)
   - Start new service

6. **Health Check**
   - Verify service is responding
   - Validate critical functionality

7. **Auto-Rollback on Failure**
   - If health check fails, automatically rollback
   - Restore previous state
   - Update symlinks back

## Version Manifest

Each version has a `manifest.json`:

```json
{
  "version": "v1.2.0",
  "created_at": "2026-02-14T10:30:00Z",
  "git_commit": "abc123def456",
  "git_branch": "main",
  "components": {
    "gateway": {"hash": "sha256:..."}
  },
  "previous_version": "v1.1.2",
  "changelog": [
    "Fix routing bug",
    "Add new persona"
  ],
  "rollback_safe": true
}
```

## State Management

### State Snapshot Contents

- **sessions.json**: Active user sessions
- **routing.json**: Routing table and twin mappings
- **runtime_config.json**: Runtime configuration
- **metrics.json**: Counters and statistics

### State Validation

State snapshots include SHA256 hash for integrity validation:

```bash
# Validate state for specific version
python -c "
from deploy.state import StateManager
from pathlib import Path
sm = StateManager(Path('/root/.pepper'))
print(sm.validate_state(Path('/root/.pepper/versions/v1.2.0')))
"
```

## Rollback System

### Quick Rollback

Rollback to previous version in <30 seconds:

```bash
pepper rollback
```

This uses the `previous` symlink for instant target identification.

### Targeted Rollback

Rollback to any historical version:

```bash
pepper rollback v1.1.0
```

### Rollback Safety

Versions are marked `rollback_safe: true` in manifest. Rollback validates:
- Target version exists
- Target version is marked rollback-safe
- State snapshot is available and valid

### Rollback Logging

All rollbacks are logged to `/root/.pepper/rollback/rollback-log.json`:

```json
{
  "rollbacks": [
    {
      "timestamp": "2026-02-14T11:00:00Z",
      "from_version": "v1.2.0",
      "to_version": "v1.1.2",
      "status": "success",
      "reason": "manual_rollback",
      "automatic": false,
      "completed_at": "2026-02-14T11:00:15Z"
    }
  ]
}
```

## Python API

### Deploy Programmatically

```python
from pathlib import Path
from deploy import PepperDeployer

deployer = PepperDeployer(
    pepper_home=Path('/root/.pepper'),
    project_root=Path('/root/factorylm/services/telegram/pepper')
)

# Deploy new patch version
success = deployer.deploy(bump_level='patch', dry_run=False)

if success:
    print("Deployment successful")
else:
    print("Deployment failed (auto-rollback attempted)")
```

### Rollback Programmatically

```python
from pathlib import Path
from deploy import RollbackManager, Version

rollback_mgr = RollbackManager(Path('/root/.pepper'))

# Rollback to previous
rollback_mgr.rollback()

# Rollback to specific version
target = Version.parse('v1.1.2')
rollback_mgr.rollback(target)
```

### Version Management

```python
from pathlib import Path
from deploy import VersionManager, Version

version_mgr = VersionManager(Path('/root/.pepper'))

# Get current version
current = version_mgr.get_current_version()
print(f"Current: {current}")

# List all versions
versions = version_mgr.list_versions()
for v in versions:
    print(v)

# Calculate next version
next_patch = version_mgr.calculate_next_version('patch')
next_minor = version_mgr.calculate_next_version('minor')
next_major = version_mgr.calculate_next_version('major')
```

### State Management

```python
from pathlib import Path
from deploy import StateManager

state_mgr = StateManager(Path('/root/.pepper'))

# Snapshot state
version_dir = Path('/root/.pepper/versions/v1.2.0')
snapshot = state_mgr.snapshot_state(version_dir)

# Restore state
state_mgr.restore_state(version_dir)

# Export state for backup
state_mgr.export_state(Path('/backup/pepper-state.json'))

# Import state from backup
state_mgr.import_state(Path('/backup/pepper-state.json'))
```

## Best Practices

### 1. Always Run Tests Before Deploy

```bash
# Run tests in project
cd /root/factorylm/services/telegram/pepper
./scripts/run_tests.sh

# Then deploy
pepper deploy
```

### 2. Use Changelog

```bash
pepper deploy --changelog "$(git log --oneline v1.1.2..HEAD | cut -d' ' -f2-)"
```

### 3. Dry Run First

```bash
# Simulate deployment
pepper deploy --bump minor --dry-run

# Then deploy for real
pepper deploy --bump minor
```

### 4. Monitor After Deploy

```bash
# Deploy
pepper deploy

# Check status immediately
pepper status

# Monitor logs
tail -f /root/.pepper/current/logs/pepper.log
```

### 5. Regular Cleanup

```bash
# Weekly cleanup (keep 10 versions)
pepper cleanup --keep 10
```

### 6. Backup State

```bash
# Export state before risky operations
python -c "
from deploy.state import StateManager
from pathlib import Path
StateManager(Path('/root/.pepper')).export_state(Path('/backup/state-$(date +%Y%m%d).json'))
"
```

## Troubleshooting

### Deployment Fails Pre-Checks

```bash
# Check git status
git status

# Validate config
python -c "import json; json.load(open('config/pepper.json'))"

# Run tests
./scripts/run_tests.sh
```

### Rollback Fails

```bash
# Check rollback log
cat /root/.pepper/rollback/rollback-log.json

# Manually switch symlinks
cd /root/.pepper
ln -sfn versions/v1.1.2 current
```

### State Restore Issues

```bash
# Validate state snapshot
python -c "
from deploy.state import StateManager
from pathlib import Path
sm = StateManager(Path('/root/.pepper'))
print(sm.validate_state(Path('/root/.pepper/versions/v1.2.0')))
"
```

### Version Cleanup Issues

```bash
# List all versions
ls -la /root/.pepper/versions/

# Manually remove old version
rm -rf /root/.pepper/versions/v1.0.0
```

## Integration with Systemd

Create `/etc/systemd/system/pepper.service`:

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

Deploy script with service restart:

```bash
#!/bin/bash
set -e

# Deploy
pepper deploy

# Restart service
systemctl restart pepper

# Check status
sleep 5
systemctl status pepper
```

## Security Considerations

- Deployments require root access (uses `/root/.pepper`)
- Git working directory must be clean (prevents deploying uncommitted changes)
- Configuration files are validated before deployment
- State snapshots are integrity-checked with SHA256
- Rollback validates version safety before proceeding

## License

MIT
