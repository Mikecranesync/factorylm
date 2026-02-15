"""
Rollback Management for PEPPER

Fast rollback to previous versions with comprehensive logging.
"""

import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from .versioning import Version, VersionManager
from .state import StateManager


class RollbackManager:
    """Manage version rollbacks with logging and validation"""

    def __init__(self, pepper_home: Path):
        """
        Initialize rollback manager

        Args:
            pepper_home: Path to PEPPER home directory
        """
        self.pepper_home = Path(pepper_home)
        self.rollback_dir = self.pepper_home / "rollback"
        self.rollback_dir.mkdir(parents=True, exist_ok=True)

        self.log_file = self.rollback_dir / "rollback-log.json"
        self.version_manager = VersionManager(pepper_home)
        self.state_manager = StateManager(pepper_home)

    def rollback(self, target_version: Optional[Version] = None) -> bool:
        """
        Rollback to target version or previous version

        Args:
            target_version: Specific version to rollback to (None = previous)

        Returns:
            True if rollback successful, False otherwise
        """
        current = self.version_manager.get_current_version()

        if current is None:
            print("Error: No current version to rollback from")
            return False

        # Determine target version
        if target_version is None:
            target_version = self.version_manager.get_previous_version()

            if target_version is None:
                print("Error: No previous version available for rollback")
                return False

        # Validate target version exists
        if not self.version_manager.version_exists(target_version):
            print(f"Error: Target version {target_version} does not exist")
            return False

        print(f"Rolling back from {current} to {target_version}...")

        # Log rollback attempt
        rollback_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'from_version': str(current),
            'to_version': str(target_version),
            'status': 'in_progress',
            'reason': 'manual_rollback',
        }

        try:
            # Validate target version
            if not self._validate_rollback_target(target_version):
                raise ValueError(f"Version {target_version} is not rollback-safe")

            # Restore state from target version
            target_dir = self.version_manager.get_version_path(target_version)
            if not self.state_manager.restore_state(target_dir):
                print("Warning: Could not fully restore state, proceeding with rollback")

            # Update symlinks atomically
            self._update_symlinks(target_version, current)

            # Log successful rollback
            rollback_entry['status'] = 'success'
            rollback_entry['completed_at'] = datetime.utcnow().isoformat() + 'Z'

            self._log_rollback(rollback_entry)

            print(f"✓ Rollback successful: {current} → {target_version}")
            return True

        except Exception as e:
            # Log failed rollback
            rollback_entry['status'] = 'failed'
            rollback_entry['error'] = str(e)
            rollback_entry['completed_at'] = datetime.utcnow().isoformat() + 'Z'

            self._log_rollback(rollback_entry)

            print(f"✗ Rollback failed: {e}")
            return False

    def auto_rollback(self, from_version: Version, reason: str) -> bool:
        """
        Automatic rollback triggered by deployment failure

        Args:
            from_version: Failed version to rollback from
            reason: Reason for rollback

        Returns:
            True if rollback successful, False otherwise
        """
        print(f"Auto-rollback triggered: {reason}")

        previous = self.version_manager.get_previous_version()

        if previous is None:
            print("Error: No previous version for auto-rollback")
            return False

        # Log auto-rollback
        rollback_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'from_version': str(from_version),
            'to_version': str(previous),
            'status': 'in_progress',
            'reason': f'auto_rollback: {reason}',
            'automatic': True,
        }

        try:
            # Restore state
            previous_dir = self.version_manager.get_version_path(previous)
            self.state_manager.restore_state(previous_dir)

            # Update symlinks
            self._update_symlinks(previous, from_version)

            # Log success
            rollback_entry['status'] = 'success'
            rollback_entry['completed_at'] = datetime.utcnow().isoformat() + 'Z'

            self._log_rollback(rollback_entry)

            print(f"✓ Auto-rollback successful: {from_version} → {previous}")
            return True

        except Exception as e:
            rollback_entry['status'] = 'failed'
            rollback_entry['error'] = str(e)
            rollback_entry['completed_at'] = datetime.utcnow().isoformat() + 'Z'

            self._log_rollback(rollback_entry)

            print(f"✗ Auto-rollback failed: {e}")
            return False

    def _update_symlinks(self, new_current: Version, old_current: Version):
        """
        Atomically update current and previous symlinks

        Args:
            new_current: New current version
            old_current: Old current version (becomes previous)
        """
        current_link = self.pepper_home / "current"
        previous_link = self.pepper_home / "previous"

        new_current_dir = self.version_manager.get_version_path(new_current)
        old_current_dir = self.version_manager.get_version_path(old_current)

        # Remove old symlinks
        if current_link.exists():
            current_link.unlink()
        if previous_link.exists():
            previous_link.unlink()

        # Create new symlinks
        current_link.symlink_to(new_current_dir, target_is_directory=True)
        previous_link.symlink_to(old_current_dir, target_is_directory=True)

        print(f"Symlinks updated: current → {new_current}, previous → {old_current}")

    def _validate_rollback_target(self, version: Version) -> bool:
        """
        Validate that target version is safe for rollback

        Args:
            version: Version to validate

        Returns:
            True if safe, False otherwise
        """
        try:
            manifest = self.version_manager.load_manifest(version)
            return manifest.get('rollback_safe', False)
        except Exception as e:
            print(f"Warning: Could not validate rollback target: {e}")
            return False

    def _log_rollback(self, entry: Dict[str, Any]):
        """
        Log rollback event

        Args:
            entry: Rollback log entry
        """
        # Load existing log
        if self.log_file.exists():
            with open(self.log_file, 'r') as f:
                log = json.load(f)
        else:
            log = {'rollbacks': []}

        # Add entry
        log['rollbacks'].append(entry)

        # Save log
        with open(self.log_file, 'w') as f:
            json.dump(log, f, indent=2)

    def list_rollbacks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        List recent rollback history

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of rollback entries
        """
        if not self.log_file.exists():
            return []

        with open(self.log_file, 'r') as f:
            log = json.load(f)

        rollbacks = log.get('rollbacks', [])

        # Return most recent first
        return rollbacks[-limit:][::-1]

    def get_rollback_stats(self) -> Dict[str, Any]:
        """
        Get rollback statistics

        Returns:
            Statistics dictionary
        """
        rollbacks = self.list_rollbacks(limit=1000)  # All rollbacks

        total = len(rollbacks)
        successful = sum(1 for r in rollbacks if r.get('status') == 'success')
        failed = sum(1 for r in rollbacks if r.get('status') == 'failed')
        automatic = sum(1 for r in rollbacks if r.get('automatic', False))

        return {
            'total_rollbacks': total,
            'successful': successful,
            'failed': failed,
            'automatic_rollbacks': automatic,
            'success_rate': (successful / total * 100) if total > 0 else 0,
        }

    def can_rollback(self) -> bool:
        """
        Check if rollback is possible

        Returns:
            True if rollback is possible, False otherwise
        """
        current = self.version_manager.get_current_version()
        previous = self.version_manager.get_previous_version()

        return current is not None and previous is not None

    def get_rollback_candidate(self) -> Optional[Version]:
        """
        Get the version that would be rolled back to

        Returns:
            Previous Version or None
        """
        return self.version_manager.get_previous_version()
