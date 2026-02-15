#!/usr/bin/env python3
"""
PEPPER Deploy CLI

Command-line interface for deploying, rolling back, and managing PEPPER versions.

Usage:
    pepper deploy [--bump patch|minor|major] [--dry-run] [--skip-tests]
    pepper rollback [version] [--list]
    pepper status
    pepper version <version>
    pepper cleanup [--keep N]
"""

import sys
import argparse
from pathlib import Path
from typing import Optional
import json

from .versioning import Version, VersionManager
from .deployer import PepperDeployer
from .rollback import RollbackManager
from .state import StateManager


# Default paths - can be overridden with environment variables
DEFAULT_PEPPER_HOME = Path("/root/.pepper")
DEFAULT_PROJECT_ROOT = Path("/root/factorylm/services/telegram/pepper")


class PepperCLI:
    """Command-line interface for PEPPER deployment"""

    def __init__(self, pepper_home: Path, project_root: Path):
        self.pepper_home = pepper_home
        self.project_root = project_root

        self.version_manager = VersionManager(pepper_home)
        self.deployer = PepperDeployer(pepper_home, project_root)
        self.rollback_manager = RollbackManager(pepper_home)
        self.state_manager = StateManager(pepper_home)

    def deploy(self, args):
        """Deploy new version"""
        bump_level = args.bump or 'patch'
        dry_run = args.dry_run
        skip_tests = args.skip_tests

        # Parse changelog if provided
        changelog = []
        if args.changelog:
            changelog = args.changelog.split(',')

        success = self.deployer.deploy(
            bump_level=bump_level,
            dry_run=dry_run,
            skip_tests=skip_tests,
            changelog=changelog
        )

        sys.exit(0 if success else 1)

    def rollback(self, args):
        """Rollback to previous or specific version"""
        if args.list:
            # List rollback history
            self._list_rollbacks()
            return

        # Parse target version if specified
        target_version = None
        if args.version:
            try:
                target_version = Version.parse(args.version)
            except ValueError as e:
                print(f"Error: {e}")
                sys.exit(1)

        # Perform rollback
        success = self.rollback_manager.rollback(target_version)

        if success:
            print("\n✓ Rollback completed successfully")
            print("  Restart PEPPER service to apply changes")
        else:
            print("\n✗ Rollback failed")

        sys.exit(0 if success else 1)

    def status(self, args):
        """Display deployment status"""
        print("=" * 60)
        print("PEPPER DEPLOYMENT STATUS")
        print("=" * 60)

        # Current version
        current = self.version_manager.get_current_version()
        print(f"\nCurrent version: {current or 'None'}")

        if current:
            # Load current manifest
            try:
                manifest = self.version_manager.load_manifest(current)
                print(f"Git commit: {manifest.get('git_commit', 'unknown')}")
                print(f"Git branch: {manifest.get('git_branch', 'unknown')}")
                print(f"Deployed at: {manifest.get('created_at', 'unknown')}")
            except Exception as e:
                print(f"Warning: Could not load manifest: {e}")

        # Previous version
        previous = self.version_manager.get_previous_version()
        print(f"\nPrevious version: {previous or 'None'}")

        # Available versions
        versions = self.version_manager.list_versions()
        print(f"\nAvailable versions: {len(versions)}")
        for version in versions[:5]:  # Show 5 most recent
            print(f"  - {version}")

        # Rollback capability
        can_rollback = self.rollback_manager.can_rollback()
        print(f"\nRollback available: {'Yes' if can_rollback else 'No'}")

        if can_rollback:
            candidate = self.rollback_manager.get_rollback_candidate()
            print(f"Rollback target: {candidate}")

        # Rollback statistics
        stats = self.rollback_manager.get_rollback_stats()
        print("\nRollback Statistics:")
        print(f"  Total rollbacks: {stats['total_rollbacks']}")
        print(f"  Successful: {stats['successful']}")
        print(f"  Failed: {stats['failed']}")
        print(f"  Automatic: {stats['automatic_rollbacks']}")
        if stats['total_rollbacks'] > 0:
            print(f"  Success rate: {stats['success_rate']:.1f}%")

        print()

    def version_info(self, args):
        """Display information about specific version"""
        try:
            version = Version.parse(args.version)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

        if not self.version_manager.version_exists(version):
            print(f"Error: Version {version} does not exist")
            sys.exit(1)

        print("=" * 60)
        print(f"VERSION {version}")
        print("=" * 60)

        # Load manifest
        try:
            manifest = self.version_manager.load_manifest(version)

            print(f"\nCreated: {manifest.get('created_at', 'unknown')}")
            print(f"Git commit: {manifest.get('git_commit', 'unknown')}")
            print(f"Git branch: {manifest.get('git_branch', 'unknown')}")
            print(f"Previous version: {manifest.get('previous_version', 'None')}")
            print(f"Rollback safe: {manifest.get('rollback_safe', False)}")

            # Changelog
            changelog = manifest.get('changelog', [])
            if changelog:
                print("\nChangelog:")
                for change in changelog:
                    print(f"  - {change}")

            # Components
            components = manifest.get('components', {})
            if components:
                print("\nComponents:")
                for name, info in components.items():
                    print(f"  - {name}: {info.get('hash', 'unknown')[:12]}")

        except Exception as e:
            print(f"Error loading manifest: {e}")
            sys.exit(1)

        # State snapshot
        version_dir = self.version_manager.get_version_path(version)
        snapshot_path = version_dir / "state" / "snapshot.json"

        if snapshot_path.exists():
            print("\nState Snapshot: Available")
            is_valid = self.state_manager.validate_state(version_dir)
            print(f"State valid: {is_valid}")
        else:
            print("\nState Snapshot: Not available")

        print()

    def cleanup(self, args):
        """Cleanup old versions"""
        keep_count = args.keep or 5

        print(f"Cleaning up old versions (keeping {keep_count} most recent)...")

        versions_before = len(self.version_manager.list_versions())

        self.version_manager.cleanup_old_versions(keep_count=keep_count)

        versions_after = len(self.version_manager.list_versions())
        removed = versions_before - versions_after

        print(f"✓ Removed {removed} old version(s)")

    def _list_rollbacks(self):
        """List rollback history"""
        print("=" * 60)
        print("ROLLBACK HISTORY")
        print("=" * 60)

        rollbacks = self.rollback_manager.list_rollbacks(limit=20)

        if not rollbacks:
            print("\nNo rollbacks recorded")
            return

        for rollback in rollbacks:
            timestamp = rollback.get('timestamp', 'unknown')
            from_ver = rollback.get('from_version', '?')
            to_ver = rollback.get('to_version', '?')
            status = rollback.get('status', 'unknown')
            reason = rollback.get('reason', 'unknown')
            automatic = rollback.get('automatic', False)

            status_symbol = '✓' if status == 'success' else '✗'
            auto_label = '[AUTO]' if automatic else '[MANUAL]'

            print(f"\n{status_symbol} {timestamp}")
            print(f"  {from_ver} → {to_ver}")
            print(f"  Reason: {reason} {auto_label}")
            print(f"  Status: {status}")

            if status == 'failed':
                error = rollback.get('error', 'unknown')
                print(f"  Error: {error}")

        print()


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='PEPPER Deploy CLI - Manage PEPPER deployments',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Global options
    parser.add_argument(
        '--pepper-home',
        type=Path,
        default=DEFAULT_PEPPER_HOME,
        help=f'PEPPER home directory (default: {DEFAULT_PEPPER_HOME})'
    )

    parser.add_argument(
        '--project-root',
        type=Path,
        default=DEFAULT_PROJECT_ROOT,
        help=f'PEPPER project root (default: {DEFAULT_PROJECT_ROOT})'
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Deploy command
    deploy_parser = subparsers.add_parser('deploy', help='Deploy new version')
    deploy_parser.add_argument(
        '--bump',
        choices=['major', 'minor', 'patch'],
        default='patch',
        help='Version bump level (default: patch)'
    )
    deploy_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulate deployment without making changes'
    )
    deploy_parser.add_argument(
        '--skip-tests',
        action='store_true',
        help='Skip test execution (not recommended)'
    )
    deploy_parser.add_argument(
        '--changelog',
        type=str,
        help='Comma-separated list of changes'
    )

    # Rollback command
    rollback_parser = subparsers.add_parser('rollback', help='Rollback to previous version')
    rollback_parser.add_argument(
        'version',
        nargs='?',
        help='Specific version to rollback to (default: previous)'
    )
    rollback_parser.add_argument(
        '--list',
        action='store_true',
        help='List rollback history'
    )

    # Status command
    status_parser = subparsers.add_parser('status', help='Display deployment status')

    # Version command
    version_parser = subparsers.add_parser('version', help='Display version information')
    version_parser.add_argument(
        'version',
        help='Version to display information for'
    )

    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Cleanup old versions')
    cleanup_parser.add_argument(
        '--keep',
        type=int,
        default=5,
        help='Number of versions to keep (default: 5)'
    )

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize CLI
    cli = PepperCLI(args.pepper_home, args.project_root)

    # Execute command
    if args.command == 'deploy':
        cli.deploy(args)
    elif args.command == 'rollback':
        cli.rollback(args)
    elif args.command == 'status':
        cli.status(args)
    elif args.command == 'version':
        cli.version_info(args)
    elif args.command == 'cleanup':
        cli.cleanup(args)


if __name__ == '__main__':
    main()
