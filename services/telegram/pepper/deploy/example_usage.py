#!/usr/bin/env python3
"""
Example Usage of PEPPER Deploy System

Demonstrates programmatic deployment, rollback, and state management.
"""

from pathlib import Path
from versioning import Version, VersionManager
from deployer import PepperDeployer
from rollback import RollbackManager
from state import StateManager


def example_deployment():
    """Example: Deploy new version programmatically"""
    print("=" * 60)
    print("EXAMPLE: DEPLOYMENT")
    print("=" * 60)
    print()

    pepper_home = Path('/root/.pepper')
    project_root = Path('/root/factorylm/services/telegram/pepper')

    deployer = PepperDeployer(pepper_home, project_root)

    # Deploy with patch version bump
    success = deployer.deploy(
        bump_level='patch',
        dry_run=False,
        skip_tests=False,
        changelog=['Fix routing bug', 'Improve performance']
    )

    if success:
        print("\n✓ Deployment successful")
    else:
        print("\n✗ Deployment failed (auto-rollback attempted)")


def example_version_management():
    """Example: Version management operations"""
    print("=" * 60)
    print("EXAMPLE: VERSION MANAGEMENT")
    print("=" * 60)
    print()

    pepper_home = Path('/root/.pepper')
    version_mgr = VersionManager(pepper_home)

    # Get current version
    current = version_mgr.get_current_version()
    print(f"Current version: {current}")

    # Get previous version
    previous = version_mgr.get_previous_version()
    print(f"Previous version: {previous}")

    # List all versions
    versions = version_mgr.list_versions()
    print(f"\nAll versions ({len(versions)}):")
    for v in versions:
        print(f"  - {v}")

    # Calculate next versions
    if current:
        next_patch = current.bump('patch')
        next_minor = current.bump('minor')
        next_major = current.bump('major')

        print(f"\nNext versions from {current}:")
        print(f"  Patch: {next_patch}")
        print(f"  Minor: {next_minor}")
        print(f"  Major: {next_major}")

    # Load manifest for current version
    if current:
        manifest = version_mgr.load_manifest(current)
        print(f"\nCurrent version manifest:")
        print(f"  Git commit: {manifest.get('git_commit', 'unknown')}")
        print(f"  Git branch: {manifest.get('git_branch', 'unknown')}")
        print(f"  Created at: {manifest.get('created_at', 'unknown')}")


def example_rollback():
    """Example: Rollback operations"""
    print("=" * 60)
    print("EXAMPLE: ROLLBACK")
    print("=" * 60)
    print()

    pepper_home = Path('/root/.pepper')
    rollback_mgr = RollbackManager(pepper_home)

    # Check if rollback is possible
    can_rollback = rollback_mgr.can_rollback()
    print(f"Rollback available: {can_rollback}")

    if can_rollback:
        # Get rollback candidate
        candidate = rollback_mgr.get_rollback_candidate()
        print(f"Rollback target: {candidate}")

        # Perform rollback (commented out for safety)
        # success = rollback_mgr.rollback()
        # print(f"Rollback result: {'success' if success else 'failed'}")

    # List rollback history
    rollbacks = rollback_mgr.list_rollbacks(limit=5)
    print(f"\nRecent rollbacks ({len(rollbacks)}):")
    for rb in rollbacks:
        status_symbol = '✓' if rb.get('status') == 'success' else '✗'
        print(f"  {status_symbol} {rb['from_version']} → {rb['to_version']}")
        print(f"     Reason: {rb.get('reason', 'unknown')}")

    # Get rollback statistics
    stats = rollback_mgr.get_rollback_stats()
    print(f"\nRollback statistics:")
    print(f"  Total: {stats['total_rollbacks']}")
    print(f"  Successful: {stats['successful']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Automatic: {stats['automatic_rollbacks']}")
    if stats['total_rollbacks'] > 0:
        print(f"  Success rate: {stats['success_rate']:.1f}%")


def example_state_management():
    """Example: State management operations"""
    print("=" * 60)
    print("EXAMPLE: STATE MANAGEMENT")
    print("=" * 60)
    print()

    pepper_home = Path('/root/.pepper')
    state_mgr = StateManager(pepper_home)

    # Export state for backup
    backup_path = pepper_home / 'state-backup.json'
    state_mgr.export_state(backup_path)
    print(f"✓ State exported to {backup_path}")

    # Validate state for current version
    version_mgr = VersionManager(pepper_home)
    current = version_mgr.get_current_version()

    if current:
        version_dir = version_mgr.get_version_path(current)
        is_valid = state_mgr.validate_state(version_dir)
        print(f"State valid for {current}: {is_valid}")

    # Example: Snapshot state for version (normally done during deploy)
    # state_snapshot = state_mgr.snapshot_state(version_dir)
    # print(f"State snapshot created with hash: {state_snapshot.get('hash')}")


def example_version_parsing():
    """Example: Version parsing and comparison"""
    print("=" * 60)
    print("EXAMPLE: VERSION PARSING")
    print("=" * 60)
    print()

    # Parse versions
    v1 = Version.parse('v1.2.3')
    v2 = Version.parse('1.2.4')
    v3 = Version.parse('v1.3.0')

    print(f"Parsed versions:")
    print(f"  v1: {v1}")
    print(f"  v2: {v2}")
    print(f"  v3: {v3}")

    # Compare versions
    print(f"\nComparisons:")
    print(f"  {v1} < {v2}: {v1 < v2}")
    print(f"  {v2} < {v3}: {v2 < v3}")
    print(f"  {v1} == Version(1, 2, 3): {v1 == Version(1, 2, 3)}")

    # Bump versions
    print(f"\nVersion bumps from {v1}:")
    print(f"  Patch: {v1.bump('patch')}")
    print(f"  Minor: {v1.bump('minor')}")
    print(f"  Major: {v1.bump('major')}")


def main():
    """Run all examples"""
    examples = [
        ("Version Parsing", example_version_parsing),
        ("Version Management", example_version_management),
        ("State Management", example_state_management),
        ("Rollback", example_rollback),
        # ("Deployment", example_deployment),  # Commented out - requires full setup
    ]

    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "PEPPER DEPLOY SYSTEM EXAMPLES" + " " * 18 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    for name, example_func in examples:
        try:
            example_func()
            print()
        except Exception as e:
            print(f"\n✗ Example '{name}' failed: {e}")
            print()

    print("=" * 60)
    print("EXAMPLES COMPLETE")
    print("=" * 60)
    print()
    print("For more information:")
    print("  - See README.md for full documentation")
    print("  - See QUICKSTART.md for quick reference")
    print("  - Run 'pepper --help' for CLI usage")
    print()


if __name__ == '__main__':
    main()
