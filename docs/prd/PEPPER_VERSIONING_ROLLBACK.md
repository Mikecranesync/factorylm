# PEPPER Versioning & Rollback System

**Addendum to PEPPER_SYSTEM_PRD.md**
**Version:** 1.0
**Created:** 2026-02-14

---

## Executive Summary

Every deployment is versioned. Every version can be rolled back in <30 seconds. No exceptions.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ONE-COMMAND ROLLBACK                             │
│                                                                     │
│   pepper rollback                    # Rollback to previous        │
│   pepper rollback v1.2.3             # Rollback to specific        │
│   pepper rollback --list             # Show available versions     │
│   pepper deploy --dry-run            # Preview before deploy       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 1. VERSION STRUCTURE

### 1.1 Semantic Versioning

```
v{MAJOR}.{MINOR}.{PATCH}[-{PRERELEASE}][+{BUILD}]

Examples:
  v1.0.0          # First stable release
  v1.1.0          # New feature (Demo Mode)
  v1.1.1          # Bug fix
  v1.2.0-beta.1   # Beta release
  v1.2.0+build.42 # Build metadata
```

### 1.2 Version Components

| Component | When to Bump | Example |
|-----------|--------------|---------|
| MAJOR | Breaking changes, architecture shifts | v1 → v2 |
| MINOR | New features, backward compatible | v1.1 → v1.2 |
| PATCH | Bug fixes, security patches | v1.1.1 → v1.1.2 |
| PRERELEASE | Testing versions | v1.2.0-beta.1 |
| BUILD | CI/CD metadata | +build.42 |

### 1.3 Version Manifest

Every version has a manifest file:

```json
// /root/.pepper/versions/v1.2.0/manifest.json
{
  "version": "v1.2.0",
  "created_at": "2026-02-14T15:30:00Z",
  "created_by": "mike",
  "git_commit": "abc123def",
  "git_branch": "main",
  "git_tag": "pepper-v1.2.0",

  "components": {
    "gateway": {
      "hash": "sha256:abc123...",
      "files": ["gateway.py", "modes.py", "node_router.py"]
    },
    "tools": {
      "hash": "sha256:def456...",
      "files": ["tools/*.py"]
    },
    "personas": {
      "hash": "sha256:ghi789...",
      "files": ["personas/*.md"]
    },
    "watchdog": {
      "hash": "sha256:jkl012...",
      "files": ["watchdog/*.py"]
    },
    "config": {
      "hash": "sha256:mno345...",
      "files": ["config.yaml", "watchdog.yaml"]
    }
  },

  "dependencies": {
    "python": "3.11.0",
    "httpx": "0.27.0",
    "python-telegram-bot": "21.0"
  },

  "config_snapshot": {
    "openclaw_hash": "sha256:pqr678...",
    "pepper_config_hash": "sha256:stu901..."
  },

  "rollback_safe": true,
  "rollback_notes": "Safe to rollback. No database migrations.",

  "changelog": [
    "Added Demo Mode guardrails",
    "Fixed node routing bug",
    "Improved error messages"
  ],

  "previous_version": "v1.1.2",
  "deployment_duration_ms": 4500
}
```

---

## 2. VERSION STORAGE

### 2.1 Directory Structure

```
/root/.pepper/
├── current -> versions/v1.2.0/    # Symlink to active version
├── previous -> versions/v1.1.2/   # Symlink to previous (quick rollback)
│
├── versions/
│   ├── v1.0.0/
│   │   ├── manifest.json
│   │   ├── code/                  # Full code snapshot
│   │   │   ├── gateway.py
│   │   │   ├── modes.py
│   │   │   └── ...
│   │   ├── config/                # Config snapshot
│   │   │   ├── config.yaml
│   │   │   └── watchdog.yaml
│   │   └── state/                 # State snapshot
│   │       ├── sessions.json
│   │       └── chat_state.json
│   │
│   ├── v1.1.0/
│   ├── v1.1.1/
│   ├── v1.1.2/
│   └── v1.2.0/                    # Current
│
├── rollback/
│   ├── pre-deploy-state.json      # State before last deploy
│   └── rollback-log.json          # History of rollbacks
│
└── deploy/
    ├── deploy.log                 # Deployment history
    └── pending/                   # Staged for next deploy
```

### 2.2 Retention Policy

| Version Type | Retention | Storage |
|--------------|-----------|---------|
| Current | Always | Local + Remote |
| Previous | Always | Local + Remote |
| Last 10 versions | 90 days | Local + Remote |
| Older versions | 30 days | Remote only (Google Drive) |
| Failed deploys | 7 days | Local only |

---

## 3. DEPLOYMENT PROCESS

### 3.1 Deploy Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                       DEPLOYMENT FLOW                               │
│                                                                     │
│  1. PRE-DEPLOY CHECKS                                               │
│     ├── Verify git status clean                                     │
│     ├── Run test suite                                              │
│     ├── Validate config syntax                                      │
│     ├── Check API keys valid                                        │
│     └── Verify disk space (>1GB free)                               │
│                                                                     │
│  2. CREATE VERSION                                                  │
│     ├── Calculate next version number                               │
│     ├── Create version directory                                    │
│     ├── Copy code snapshot                                          │
│     ├── Copy config snapshot                                        │
│     ├── Generate manifest.json                                      │
│     └── Create git tag                                              │
│                                                                     │
│  3. PRE-DEPLOY SNAPSHOT                                             │
│     ├── Save current state                                          │
│     ├── Export session data                                         │
│     ├── Backup database (if any)                                    │
│     └── Record service PIDs                                         │
│                                                                     │
│  4. ATOMIC DEPLOY                                                   │
│     ├── Stop PEPPER service                                         │
│     ├── Update 'previous' symlink → old 'current'                   │
│     ├── Update 'current' symlink → new version                      │
│     ├── Start PEPPER service                                        │
│     └── Verify health check passes                                  │
│                                                                     │
│  5. POST-DEPLOY VERIFY                                              │
│     ├── Health check (all endpoints)                                │
│     ├── Smoke test (send test message)                              │
│     ├── Verify logs clean                                           │
│     └── If ANY failure → AUTO ROLLBACK                              │
│                                                                     │
│  6. CLEANUP                                                         │
│     ├── Archive old versions                                        │
│     ├── Upload to remote backup                                     │
│     ├── Update deploy.log                                           │
│     └── Send success notification                                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Deploy Script

```python
# deploy/deploy.py

import subprocess
import json
import shutil
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, List
import hashlib

@dataclass
class DeployResult:
    success: bool
    version: str
    duration_ms: int
    errors: List[str]
    rolled_back: bool

class PepperDeployer:
    """Handles versioned deployments with rollback capability."""

    PEPPER_ROOT = Path("/root/.pepper")
    VERSIONS_DIR = PEPPER_ROOT / "versions"
    CURRENT_LINK = PEPPER_ROOT / "current"
    PREVIOUS_LINK = PEPPER_ROOT / "previous"
    CODE_SOURCE = Path("/root/pepper")  # Where new code lives

    def __init__(self):
        self.VERSIONS_DIR.mkdir(parents=True, exist_ok=True)

    def get_current_version(self) -> Optional[str]:
        """Get currently deployed version."""
        if self.CURRENT_LINK.exists():
            return self.CURRENT_LINK.resolve().name
        return None

    def get_previous_version(self) -> Optional[str]:
        """Get previous version (for quick rollback)."""
        if self.PREVIOUS_LINK.exists():
            return self.PREVIOUS_LINK.resolve().name
        return None

    def list_versions(self) -> List[str]:
        """List all available versions."""
        versions = []
        for d in self.VERSIONS_DIR.iterdir():
            if d.is_dir() and (d / "manifest.json").exists():
                versions.append(d.name)
        return sorted(versions, reverse=True)

    def calculate_next_version(self, bump: str = "patch") -> str:
        """Calculate next version number."""
        current = self.get_current_version()
        if not current:
            return "v1.0.0"

        # Parse current version
        parts = current.lstrip("v").split(".")
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2].split("-")[0])

        if bump == "major":
            return f"v{major + 1}.0.0"
        elif bump == "minor":
            return f"v{major}.{minor + 1}.0"
        else:  # patch
            return f"v{major}.{minor}.{patch + 1}"

    def hash_directory(self, path: Path) -> str:
        """Generate hash of directory contents."""
        hasher = hashlib.sha256()
        for file in sorted(path.rglob("*")):
            if file.is_file():
                hasher.update(file.read_bytes())
        return hasher.hexdigest()[:16]

    def pre_deploy_checks(self) -> List[str]:
        """Run pre-deployment checks. Returns list of errors."""
        errors = []

        # Check git status
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.CODE_SOURCE,
            capture_output=True, text=True
        )
        if result.stdout.strip():
            errors.append("Git working directory not clean")

        # Check tests
        result = subprocess.run(
            ["pytest", "-q", "--tb=no"],
            cwd=self.CODE_SOURCE,
            capture_output=True
        )
        if result.returncode != 0:
            errors.append("Tests failed")

        # Check disk space
        import shutil
        total, used, free = shutil.disk_usage("/")
        if free < 1_000_000_000:  # 1GB
            errors.append(f"Low disk space: {free // 1_000_000}MB free")

        # Check config syntax
        config_path = self.CODE_SOURCE / "config.yaml"
        if config_path.exists():
            try:
                import yaml
                yaml.safe_load(config_path.read_text())
            except Exception as e:
                errors.append(f"Config syntax error: {e}")

        return errors

    def create_version(
        self,
        version: str,
        changelog: List[str],
        created_by: str = "system"
    ) -> Path:
        """Create a new version snapshot."""
        version_dir = self.VERSIONS_DIR / version
        version_dir.mkdir(exist_ok=True)

        # Copy code
        code_dir = version_dir / "code"
        if code_dir.exists():
            shutil.rmtree(code_dir)
        shutil.copytree(
            self.CODE_SOURCE,
            code_dir,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git", ".venv")
        )

        # Copy config
        config_dir = version_dir / "config"
        config_dir.mkdir(exist_ok=True)
        for config_file in ["config.yaml", "watchdog.yaml"]:
            src = self.CODE_SOURCE / config_file
            if src.exists():
                shutil.copy(src, config_dir / config_file)

        # Get git info
        git_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.CODE_SOURCE,
            capture_output=True, text=True
        ).stdout.strip()

        git_branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=self.CODE_SOURCE,
            capture_output=True, text=True
        ).stdout.strip()

        # Create manifest
        manifest = {
            "version": version,
            "created_at": datetime.now().isoformat(),
            "created_by": created_by,
            "git_commit": git_commit,
            "git_branch": git_branch,
            "git_tag": f"pepper-{version}",
            "components": {
                "gateway": {"hash": self.hash_directory(code_dir)},
            },
            "previous_version": self.get_current_version(),
            "changelog": changelog,
            "rollback_safe": True
        }

        (version_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2)
        )

        # Create git tag
        subprocess.run(
            ["git", "tag", f"pepper-{version}"],
            cwd=self.CODE_SOURCE
        )

        return version_dir

    def snapshot_state(self) -> dict:
        """Capture current runtime state for rollback."""
        state = {
            "timestamp": datetime.now().isoformat(),
            "version": self.get_current_version(),
            "services": {},
            "sessions": None
        }

        # Capture service PIDs
        for service in ["pepper", "pepper-watchdog"]:
            result = subprocess.run(
                ["systemctl", "show", service, "--property=MainPID"],
                capture_output=True, text=True
            )
            if "MainPID=" in result.stdout:
                state["services"][service] = result.stdout.strip().split("=")[1]

        # Capture session state (if exists)
        sessions_file = Path("/tmp/pepper_sessions.json")
        if sessions_file.exists():
            state["sessions"] = sessions_file.read_text()

        return state

    def deploy(
        self,
        version: str = None,
        bump: str = "patch",
        changelog: List[str] = None,
        dry_run: bool = False
    ) -> DeployResult:
        """Deploy a new version."""
        start_time = datetime.now()
        errors = []

        # Pre-deploy checks
        check_errors = self.pre_deploy_checks()
        if check_errors:
            return DeployResult(
                success=False,
                version="",
                duration_ms=0,
                errors=check_errors,
                rolled_back=False
            )

        # Calculate version
        if not version:
            version = self.calculate_next_version(bump)

        if dry_run:
            print(f"DRY RUN: Would deploy {version}")
            print(f"  Current: {self.get_current_version()}")
            print(f"  Changes: {changelog}")
            return DeployResult(
                success=True,
                version=version,
                duration_ms=0,
                errors=[],
                rolled_back=False
            )

        try:
            # Save pre-deploy state
            pre_state = self.snapshot_state()
            (self.PEPPER_ROOT / "rollback" / "pre-deploy-state.json").parent.mkdir(exist_ok=True)
            (self.PEPPER_ROOT / "rollback" / "pre-deploy-state.json").write_text(
                json.dumps(pre_state, indent=2)
            )

            # Create version
            version_dir = self.create_version(
                version,
                changelog or ["No changelog provided"]
            )

            # Stop service
            subprocess.run(["systemctl", "stop", "pepper"], check=True)

            # Update symlinks (atomic)
            if self.CURRENT_LINK.exists():
                # Move current to previous
                if self.PREVIOUS_LINK.exists():
                    self.PREVIOUS_LINK.unlink()
                self.PREVIOUS_LINK.symlink_to(self.CURRENT_LINK.resolve())
                self.CURRENT_LINK.unlink()

            # Point current to new version
            self.CURRENT_LINK.symlink_to(version_dir)

            # Start service
            subprocess.run(["systemctl", "start", "pepper"], check=True)

            # Health check
            import time
            time.sleep(2)  # Give service time to start

            result = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                 "http://localhost:18789/health"],
                capture_output=True, text=True
            )

            if result.stdout.strip() != "200":
                raise Exception(f"Health check failed: {result.stdout}")

            # Success
            duration = int((datetime.now() - start_time).total_seconds() * 1000)

            # Update manifest with duration
            manifest_path = version_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["deployment_duration_ms"] = duration
            manifest_path.write_text(json.dumps(manifest, indent=2))

            return DeployResult(
                success=True,
                version=version,
                duration_ms=duration,
                errors=[],
                rolled_back=False
            )

        except Exception as e:
            errors.append(str(e))

            # AUTO ROLLBACK
            self.rollback()

            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return DeployResult(
                success=False,
                version=version,
                duration_ms=duration,
                errors=errors,
                rolled_back=True
            )

    def rollback(self, target_version: str = None) -> DeployResult:
        """Rollback to previous or specific version."""
        start_time = datetime.now()

        if target_version:
            target_dir = self.VERSIONS_DIR / target_version
        elif self.PREVIOUS_LINK.exists():
            target_dir = self.PREVIOUS_LINK.resolve()
            target_version = target_dir.name
        else:
            return DeployResult(
                success=False,
                version="",
                duration_ms=0,
                errors=["No previous version to rollback to"],
                rolled_back=False
            )

        if not target_dir.exists():
            return DeployResult(
                success=False,
                version=target_version,
                duration_ms=0,
                errors=[f"Version {target_version} not found"],
                rolled_back=False
            )

        try:
            # Stop service
            subprocess.run(["systemctl", "stop", "pepper"])

            # Update symlinks
            current_version = self.get_current_version()

            if self.CURRENT_LINK.exists():
                self.CURRENT_LINK.unlink()

            self.CURRENT_LINK.symlink_to(target_dir)

            # Update previous to point to what was current
            if current_version and current_version != target_version:
                if self.PREVIOUS_LINK.exists():
                    self.PREVIOUS_LINK.unlink()
                self.PREVIOUS_LINK.symlink_to(self.VERSIONS_DIR / current_version)

            # Start service
            subprocess.run(["systemctl", "start", "pepper"], check=True)

            # Log rollback
            rollback_log = self.PEPPER_ROOT / "rollback" / "rollback-log.json"
            rollback_log.parent.mkdir(exist_ok=True)

            history = []
            if rollback_log.exists():
                history = json.loads(rollback_log.read_text())

            history.append({
                "timestamp": datetime.now().isoformat(),
                "from_version": current_version,
                "to_version": target_version,
                "reason": "manual" if target_version else "auto"
            })

            rollback_log.write_text(json.dumps(history, indent=2))

            duration = int((datetime.now() - start_time).total_seconds() * 1000)

            return DeployResult(
                success=True,
                version=target_version,
                duration_ms=duration,
                errors=[],
                rolled_back=True
            )

        except Exception as e:
            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return DeployResult(
                success=False,
                version=target_version,
                duration_ms=duration,
                errors=[str(e)],
                rolled_back=False
            )


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PEPPER Deployment Tool")
    subparsers = parser.add_subparsers(dest="command")

    # Deploy command
    deploy_parser = subparsers.add_parser("deploy", help="Deploy new version")
    deploy_parser.add_argument("--version", "-v", help="Specific version")
    deploy_parser.add_argument("--bump", choices=["major", "minor", "patch"], default="patch")
    deploy_parser.add_argument("--changelog", "-c", nargs="+", help="Changelog entries")
    deploy_parser.add_argument("--dry-run", action="store_true")

    # Rollback command
    rollback_parser = subparsers.add_parser("rollback", help="Rollback to previous version")
    rollback_parser.add_argument("version", nargs="?", help="Specific version to rollback to")
    rollback_parser.add_argument("--list", "-l", action="store_true", help="List available versions")

    # Status command
    status_parser = subparsers.add_parser("status", help="Show current deployment status")

    args = parser.parse_args()
    deployer = PepperDeployer()

    if args.command == "deploy":
        result = deployer.deploy(
            version=args.version,
            bump=args.bump,
            changelog=args.changelog,
            dry_run=args.dry_run
        )
        print(f"Deploy {'succeeded' if result.success else 'failed'}: {result.version}")
        if result.errors:
            for e in result.errors:
                print(f"  Error: {e}")
        if result.rolled_back:
            print("  Auto-rollback performed")

    elif args.command == "rollback":
        if args.list:
            print("Available versions:")
            for v in deployer.list_versions():
                current = " (current)" if v == deployer.get_current_version() else ""
                previous = " (previous)" if v == deployer.get_previous_version() else ""
                print(f"  {v}{current}{previous}")
        else:
            result = deployer.rollback(args.version)
            print(f"Rollback {'succeeded' if result.success else 'failed'}: {result.version}")
            if result.errors:
                for e in result.errors:
                    print(f"  Error: {e}")

    elif args.command == "status":
        print(f"Current version: {deployer.get_current_version()}")
        print(f"Previous version: {deployer.get_previous_version()}")
        print(f"Available versions: {len(deployer.list_versions())}")
```

---

## 4. ROLLBACK PROCESS

### 4.1 Quick Rollback (<30 seconds)

```bash
# Rollback to previous version (instant)
pepper rollback

# What happens:
# 1. Stop PEPPER service (2s)
# 2. Swap symlinks: current ↔ previous (instant)
# 3. Start PEPPER service (3s)
# 4. Health check (2s)
# Total: ~7 seconds
```

### 4.2 Targeted Rollback

```bash
# List available versions
pepper rollback --list

# Output:
#   v1.2.0 (current)
#   v1.1.2 (previous)
#   v1.1.1
#   v1.1.0
#   v1.0.0

# Rollback to specific version
pepper rollback v1.1.0
```

### 4.3 Emergency Rollback (If CLI Broken)

```bash
# Manual emergency rollback
systemctl stop pepper
rm /root/.pepper/current
ln -s /root/.pepper/versions/v1.1.2 /root/.pepper/current
systemctl start pepper

# Or restore from backup
cp /root/.pepper-watchdog/backups/openclaw.json.2026-02-14 /root/.openclaw/openclaw.json
systemctl restart pepper
```

---

## 5. CONFIGURATION VERSIONING

### 5.1 Config vs Code Versions

Configs are versioned separately from code because they change more frequently:

```
Config Version: c1.5
Code Version: v1.2.0

Together they form a deployment: v1.2.0-c1.5
```

### 5.2 Config Manifest

```json
// /root/.pepper/configs/c1.5/config-manifest.json
{
  "config_version": "c1.5",
  "created_at": "2026-02-14T16:00:00Z",
  "compatible_code_versions": ["v1.2.0", "v1.1.x"],

  "files": {
    "config.yaml": {
      "hash": "sha256:abc123...",
      "changes": ["Updated node URLs", "Added new model"]
    },
    "watchdog.yaml": {
      "hash": "sha256:def456...",
      "changes": ["Increased check frequency"]
    },
    "openclaw.json": {
      "hash": "sha256:ghi789...",
      "changes": ["Added Groq fallback"]
    }
  },

  "secrets_hash": "sha256:jkl012...",  # Hash of env vars (not values)
  "previous_config": "c1.4"
}
```

### 5.3 Config Rollback

```bash
# List config versions
pepper config --list

# Rollback config only (keep code)
pepper config rollback c1.4

# Deploy specific config with current code
pepper config apply c1.5
```

---

## 6. STATE MANAGEMENT

### 6.1 Stateful Components

| Component | State Location | Backup Strategy |
|-----------|----------------|-----------------|
| Chat sessions | `/tmp/pepper_sessions.json` | Snapshot before deploy |
| Node routing state | `/tmp/telegram_router_state.json` | Snapshot before deploy |
| Watchdog baseline | `/root/.pepper-watchdog/baseline.json` | Include in version |
| Audit logs | `/root/.pepper-watchdog/alerts.log` | Rotate, don't version |

### 6.2 State Snapshot

```python
# deploy/state.py

def snapshot_state() -> dict:
    """Capture all stateful data before deployment."""
    state = {
        "timestamp": datetime.now().isoformat(),
        "sessions": {},
        "routing": {},
        "watchdog": {}
    }

    # Chat sessions
    sessions_file = Path("/tmp/pepper_sessions.json")
    if sessions_file.exists():
        state["sessions"] = json.loads(sessions_file.read_text())

    # Routing state
    routing_file = Path("/tmp/telegram_router_state.json")
    if routing_file.exists():
        state["routing"] = json.loads(routing_file.read_text())

    # Watchdog baseline
    baseline_file = Path("/root/.pepper-watchdog/baseline.json")
    if baseline_file.exists():
        state["watchdog"] = json.loads(baseline_file.read_text())

    return state

def restore_state(state: dict):
    """Restore stateful data after rollback."""
    if state.get("sessions"):
        Path("/tmp/pepper_sessions.json").write_text(
            json.dumps(state["sessions"])
        )

    if state.get("routing"):
        Path("/tmp/telegram_router_state.json").write_text(
            json.dumps(state["routing"])
        )

    # Note: Don't restore watchdog baseline after rollback
    # It should reflect current state, not old state
```

---

## 7. BLUE-GREEN DEPLOYMENT

### 7.1 Concept

For zero-downtime deploys (optional, more complex):

```
┌─────────────────────────────────────────────────────────────────────┐
│                     BLUE-GREEN DEPLOYMENT                           │
│                                                                     │
│  ┌─────────────┐         ┌─────────────┐                           │
│  │   BLUE      │         │   GREEN     │                           │
│  │  (Current)  │         │   (New)     │                           │
│  │             │         │             │                           │
│  │  Port 18789 │         │  Port 18790 │                           │
│  │     ▲       │         │             │                           │
│  └─────┼───────┘         └─────────────┘                           │
│        │                                                            │
│  ┌─────┴─────┐                                                      │
│  │  NGINX    │  ← Routes traffic                                    │
│  │  Proxy    │                                                      │
│  └───────────┘                                                      │
│                                                                     │
│  After health check passes:                                         │
│                                                                     │
│  ┌─────────────┐         ┌─────────────┐                           │
│  │   BLUE      │         │   GREEN     │                           │
│  │  (Old)      │         │  (Current)  │                           │
│  │             │         │             │                           │
│  │  Port 18789 │         │  Port 18790 │                           │
│  │             │         │     ▲       │                           │
│  └─────────────┘         └─────┼───────┘                           │
│                                │                                    │
│                          ┌─────┴─────┐                              │
│                          │  NGINX    │                              │
│                          │  Proxy    │                              │
│                          └───────────┘                              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 Implementation (Optional)

```bash
# Only if zero-downtime needed
pepper deploy --strategy blue-green

# This:
# 1. Starts new version on alternate port
# 2. Health checks new version
# 3. Switches nginx upstream
# 4. Drains connections from old
# 5. Stops old version
```

---

## 8. CLI REFERENCE

### 8.1 Deploy Commands

```bash
# Deploy (auto-bump patch version)
pepper deploy

# Deploy with specific bump
pepper deploy --bump minor
pepper deploy --bump major

# Deploy specific version
pepper deploy --version v1.3.0

# Deploy with changelog
pepper deploy -c "Fixed bug" -c "Added feature"

# Dry run (preview only)
pepper deploy --dry-run

# Skip tests (dangerous)
pepper deploy --skip-tests
```

### 8.2 Rollback Commands

```bash
# Rollback to previous (instant)
pepper rollback

# Rollback to specific version
pepper rollback v1.1.2

# List available versions
pepper rollback --list

# Show rollback history
pepper rollback --history
```

### 8.3 Version Commands

```bash
# Show current status
pepper status

# Show version details
pepper version v1.2.0

# Compare versions
pepper diff v1.1.2 v1.2.0

# Delete old version
pepper version delete v1.0.0

# Archive to remote
pepper version archive v1.0.0
```

### 8.4 Config Commands

```bash
# List config versions
pepper config --list

# Show current config
pepper config show

# Rollback config only
pepper config rollback c1.4

# Apply specific config
pepper config apply c1.5

# Diff configs
pepper config diff c1.4 c1.5
```

---

## 9. INTEGRATION WITH WATCHDOG

The Watchdog system automatically:

1. **Detects deploy failures** — If health check fails after deploy, alerts
2. **Tracks version changes** — Logs when version symlink changes
3. **Monitors for drift** — Alerts if files in current version are modified
4. **Auto-rollback suggestion** — If service keeps crashing, suggests rollback

```python
# In watchdog, add version monitoring
class VersionMonitor:
    def check_version_health(self):
        current = Path("/root/.pepper/current")
        if not current.exists():
            return Alert(CRITICAL, "No current version symlink!")

        # Check manifest exists
        manifest = current / "manifest.json"
        if not manifest.exists():
            return Alert(CRITICAL, "Current version missing manifest!")

        # Check code matches manifest hash
        manifest_data = json.loads(manifest.read_text())
        expected_hash = manifest_data["components"]["gateway"]["hash"]
        actual_hash = self.hash_directory(current / "code")

        if expected_hash != actual_hash:
            return Alert(CRITICAL, "Code drift detected! Files modified since deploy.")

        return None
```

---

## 10. IMPLEMENTATION CHECKLIST

Add to **Phase 6**:

### 10.1 Core Versioning

- [ ] Create `/root/.pepper/` directory structure
- [ ] Implement `deploy/deploy.py` with full deployer class
- [ ] Implement `deploy/state.py` for state snapshots
- [ ] Create `pepper` CLI wrapper script
- [ ] Add to PATH: `/usr/local/bin/pepper`

### 10.2 Version Management

- [ ] Version manifest schema implemented
- [ ] Git tagging on deploy
- [ ] Symlink management working
- [ ] Retention policy enforced

### 10.3 Rollback

- [ ] Quick rollback (<30s) tested
- [ ] Targeted rollback tested
- [ ] Auto-rollback on failed health check
- [ ] Rollback history logged

### 10.4 Config Versioning

- [ ] Config manifest separate from code
- [ ] Config-only rollback working
- [ ] Compatibility checking implemented

### 10.5 Integration

- [ ] Watchdog monitors version health
- [ ] Alerts on version drift
- [ ] Remote backup of versions
- [ ] Documentation updated

---

## 11. QUICK REFERENCE CARD

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PEPPER DEPLOY QUICK REF                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  DEPLOY NEW VERSION:                                                │
│    pepper deploy                     # Auto patch bump              │
│    pepper deploy --bump minor        # Minor version                │
│    pepper deploy --dry-run           # Preview only                 │
│                                                                     │
│  ROLLBACK:                                                          │
│    pepper rollback                   # To previous (~7 seconds)     │
│    pepper rollback v1.1.2            # To specific version          │
│    pepper rollback --list            # Show all versions            │
│                                                                     │
│  EMERGENCY (if CLI broken):                                         │
│    systemctl stop pepper                                            │
│    rm /root/.pepper/current                                         │
│    ln -s /root/.pepper/versions/vX.X.X /root/.pepper/current        │
│    systemctl start pepper                                           │
│                                                                     │
│  STATUS:                                                            │
│    pepper status                     # Current version info         │
│    pepper version v1.2.0             # Version details              │
│                                                                     │
│  PATHS:                                                             │
│    /root/.pepper/current             # Symlink to active            │
│    /root/.pepper/previous            # Symlink to previous          │
│    /root/.pepper/versions/           # All versions                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

*Versioning & Rollback Spec v1.0 | PEPPER System Addendum*
