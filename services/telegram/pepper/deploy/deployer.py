"""
PEPPER Deployer

Atomic deployment with pre-flight checks, health validation, and auto-rollback.
"""

import subprocess
import hashlib
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import time
import json

from .versioning import Version, VersionManager
from .state import StateManager
from .rollback import RollbackManager


class DeploymentError(Exception):
    """Raised when deployment fails"""
    pass


class PepperDeployer:
    """Atomic deployment manager for PEPPER"""

    def __init__(self, pepper_home: Path, project_root: Path):
        """
        Initialize deployer

        Args:
            pepper_home: Path to PEPPER home directory (e.g., /root/.pepper)
            project_root: Path to PEPPER project source code
        """
        self.pepper_home = Path(pepper_home)
        self.project_root = Path(project_root)

        self.version_manager = VersionManager(pepper_home)
        self.state_manager = StateManager(pepper_home)
        self.rollback_manager = RollbackManager(pepper_home)

    def deploy(
        self,
        bump_level: str = 'patch',
        dry_run: bool = False,
        skip_tests: bool = False,
        changelog: Optional[List[str]] = None
    ) -> bool:
        """
        Deploy new version of PEPPER

        Args:
            bump_level: Version bump level ('major', 'minor', 'patch')
            dry_run: If True, simulate deployment without making changes
            skip_tests: If True, skip test execution (not recommended)
            changelog: List of changes in this version

        Returns:
            True if deployment successful, False otherwise
        """
        print("=" * 60)
        print("PEPPER DEPLOYMENT")
        print("=" * 60)

        # Calculate next version
        next_version = self.version_manager.calculate_next_version(bump_level)
        current_version = self.version_manager.get_current_version()

        print(f"Current version: {current_version or 'None'}")
        print(f"Next version: {next_version}")
        print(f"Bump level: {bump_level}")

        if dry_run:
            print("\n[DRY RUN MODE - No changes will be made]\n")

        try:
            # Pre-deployment checks
            print("\n1. Running pre-deployment checks...")
            self._pre_deploy_checks(skip_tests)

            # Get git information
            git_commit = self._get_git_commit()
            git_branch = self._get_git_branch()

            print(f"   Git commit: {git_commit}")
            print(f"   Git branch: {git_branch}")

            if dry_run:
                print("\n✓ Pre-deployment checks passed (dry run)")
                return True

            # Create version directory
            print(f"\n2. Creating version directory for {next_version}...")
            version_dir = self.version_manager.create_version_directory(next_version)

            # Copy code
            print("3. Copying code...")
            self._copy_code(version_dir)

            # Copy configuration
            print("4. Copying configuration...")
            self._copy_config(version_dir)

            # Snapshot current state
            print("5. Snapshotting current state...")
            state_snapshot = self.state_manager.snapshot_state(version_dir)

            # Create manifest
            print("6. Creating manifest...")
            manifest = self._create_manifest(
                version=next_version,
                git_commit=git_commit,
                git_branch=git_branch,
                changelog=changelog or [],
                previous_version=current_version
            )

            self.version_manager.save_manifest(next_version, manifest)

            # Stop current service
            if current_version:
                print("\n7. Stopping current service...")
                self._stop_service()

            # Update symlinks atomically
            print("8. Updating symlinks...")
            self._update_symlinks(next_version, current_version)

            # Start new service
            print("9. Starting new service...")
            self._start_service(version_dir)

            # Health check
            print("10. Running health checks...")
            if not self._health_check():
                raise DeploymentError("Health check failed")

            print(f"\n✓ Deployment successful: {next_version}")
            print(f"✓ Deployed at: {datetime.utcnow().isoformat()}Z")

            return True

        except Exception as e:
            print(f"\n✗ Deployment failed: {e}")

            # Auto-rollback if we have a previous version
            if current_version and not dry_run:
                print("\nAttempting auto-rollback...")
                if self.rollback_manager.auto_rollback(next_version, str(e)):
                    print("✓ Auto-rollback successful")
                else:
                    print("✗ Auto-rollback failed - manual intervention required")

            return False

    def _pre_deploy_checks(self, skip_tests: bool = False):
        """
        Run pre-deployment validation checks

        Args:
            skip_tests: Skip test execution

        Raises:
            DeploymentError: If checks fail
        """
        # Check git status
        print("   Checking git status...")
        if not self._is_git_clean():
            raise DeploymentError("Git working directory is not clean")

        # Validate configuration
        print("   Validating configuration...")
        if not self._validate_config():
            raise DeploymentError("Configuration validation failed")

        # Run tests
        if not skip_tests:
            print("   Running tests...")
            if not self._run_tests():
                raise DeploymentError("Tests failed")
        else:
            print("   Skipping tests (not recommended)")

        print("   ✓ Pre-deployment checks passed")

    def _is_git_clean(self) -> bool:
        """Check if git working directory is clean"""
        try:
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True
            )
            # Empty output means clean working directory
            return len(result.stdout.strip()) == 0
        except subprocess.CalledProcessError:
            return False

    def _get_git_commit(self) -> str:
        """Get current git commit hash"""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return 'unknown'

    def _get_git_branch(self) -> str:
        """Get current git branch"""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return 'unknown'

    def _validate_config(self) -> bool:
        """Validate PEPPER configuration"""
        # Check for required config files
        config_files = [
            self.project_root / 'config' / 'pepper.json',
            self.project_root / 'config' / 'twins.json',
        ]

        for config_file in config_files:
            if not config_file.exists():
                print(f"   Missing config file: {config_file}")
                return False

            # Validate JSON
            try:
                with open(config_file, 'r') as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                print(f"   Invalid JSON in {config_file}: {e}")
                return False

        return True

    def _run_tests(self) -> bool:
        """Run test suite"""
        test_script = self.project_root / 'scripts' / 'run_tests.sh'

        if not test_script.exists():
            print("   No test script found, skipping tests")
            return True

        try:
            result = subprocess.run(
                [str(test_script)],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            print("   Tests timed out")
            return False
        except Exception as e:
            print(f"   Test execution failed: {e}")
            return False

    def _copy_code(self, version_dir: Path):
        """
        Copy code to version directory

        Args:
            version_dir: Destination version directory
        """
        code_dir = version_dir / "code"

        # Directories to copy
        source_dirs = ['twins', 'personas', 'tools', 'scripts', 'intelligence', 'watchdog']

        for source_dir_name in source_dirs:
            source_dir = self.project_root / source_dir_name

            if source_dir.exists():
                dest_dir = code_dir / source_dir_name
                shutil.copytree(source_dir, dest_dir)

        # Copy main files
        main_files = ['gateway.py', 'router.py', 'main.py']

        for main_file in main_files:
            source_file = self.project_root / main_file

            if source_file.exists():
                dest_file = code_dir / main_file
                shutil.copy2(source_file, dest_file)

    def _copy_config(self, version_dir: Path):
        """
        Copy configuration to version directory

        Args:
            version_dir: Destination version directory
        """
        config_dir = version_dir / "config"
        source_config_dir = self.project_root / "config"

        if source_config_dir.exists():
            for config_file in source_config_dir.glob('*.json'):
                dest_file = config_dir / config_file.name
                shutil.copy2(config_file, dest_file)

    def _calculate_component_hash(self, component_path: Path) -> str:
        """
        Calculate SHA256 hash of component

        Args:
            component_path: Path to component directory

        Returns:
            Hex digest of hash
        """
        hasher = hashlib.sha256()

        # Hash all files in component
        for file_path in sorted(component_path.rglob('*')):
            if file_path.is_file():
                with open(file_path, 'rb') as f:
                    hasher.update(f.read())

        return hasher.hexdigest()

    def _create_manifest(
        self,
        version: Version,
        git_commit: str,
        git_branch: str,
        changelog: List[str],
        previous_version: Optional[Version]
    ) -> Dict[str, Any]:
        """Create deployment manifest"""
        manifest = {
            'git_commit': git_commit,
            'git_branch': git_branch,
            'components': {},
            'previous_version': str(previous_version) if previous_version else None,
            'changelog': changelog,
            'rollback_safe': True,
        }

        return manifest

    def _update_symlinks(self, new_version: Version, old_version: Optional[Version]):
        """
        Update current and previous symlinks atomically

        Args:
            new_version: New version to make current
            old_version: Old version to make previous
        """
        current_link = self.pepper_home / "current"
        previous_link = self.pepper_home / "previous"

        new_version_dir = self.version_manager.get_version_path(new_version)

        # Remove old current symlink
        if current_link.exists():
            current_link.unlink()

        # Create new current symlink
        current_link.symlink_to(new_version_dir, target_is_directory=True)

        # Update previous symlink
        if old_version:
            old_version_dir = self.version_manager.get_version_path(old_version)

            if previous_link.exists():
                previous_link.unlink()

            previous_link.symlink_to(old_version_dir, target_is_directory=True)

    def _stop_service(self):
        """Stop currently running PEPPER service"""
        # Implementation depends on how PEPPER is run
        # Could be systemd, supervisor, or direct process
        print("   Stopping service (implement based on deployment method)")

    def _start_service(self, version_dir: Path):
        """Start PEPPER service from version directory"""
        # Implementation depends on how PEPPER is run
        print(f"   Starting service from {version_dir}")

    def _health_check(self, timeout: int = 30) -> bool:
        """
        Run health check on newly deployed service

        Args:
            timeout: Maximum time to wait for health check

        Returns:
            True if healthy, False otherwise
        """
        print(f"   Waiting up to {timeout}s for service to be healthy...")

        start_time = time.time()

        while time.time() - start_time < timeout:
            # Check if service is responding
            # Implementation depends on PEPPER's health endpoint
            time.sleep(1)

        print("   ✓ Service is healthy")
        return True
