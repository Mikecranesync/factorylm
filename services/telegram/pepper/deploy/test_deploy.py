#!/usr/bin/env python3
"""
Test Suite for PEPPER Deploy System

Tests versioning, deployment, rollback, and state management.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
import json

from versioning import Version, VersionManager
from state import StateManager
from rollback import RollbackManager


class TestVersion(unittest.TestCase):
    """Test Version class"""

    def test_version_string(self):
        """Test version string representation"""
        v = Version(1, 2, 3)
        self.assertEqual(str(v), 'v1.2.3')

    def test_version_parse(self):
        """Test version parsing"""
        v1 = Version.parse('v1.2.3')
        self.assertEqual(v1.major, 1)
        self.assertEqual(v1.minor, 2)
        self.assertEqual(v1.patch, 3)

        v2 = Version.parse('1.2.3')
        self.assertEqual(v2.major, 1)
        self.assertEqual(v2.minor, 2)
        self.assertEqual(v2.patch, 3)

    def test_version_parse_invalid(self):
        """Test invalid version parsing"""
        with self.assertRaises(ValueError):
            Version.parse('1.2')

        with self.assertRaises(ValueError):
            Version.parse('invalid')

    def test_version_bump_patch(self):
        """Test patch version bump"""
        v = Version(1, 2, 3)
        v_new = v.bump('patch')
        self.assertEqual(str(v_new), 'v1.2.4')

    def test_version_bump_minor(self):
        """Test minor version bump"""
        v = Version(1, 2, 3)
        v_new = v.bump('minor')
        self.assertEqual(str(v_new), 'v1.3.0')

    def test_version_bump_major(self):
        """Test major version bump"""
        v = Version(1, 2, 3)
        v_new = v.bump('major')
        self.assertEqual(str(v_new), 'v2.0.0')

    def test_version_comparison(self):
        """Test version comparison"""
        v1 = Version(1, 2, 3)
        v2 = Version(1, 2, 4)
        v3 = Version(1, 3, 0)
        v4 = Version(2, 0, 0)

        self.assertTrue(v1 < v2)
        self.assertTrue(v2 < v3)
        self.assertTrue(v3 < v4)
        self.assertTrue(v1 == Version(1, 2, 3))


class TestVersionManager(unittest.TestCase):
    """Test VersionManager class"""

    def setUp(self):
        """Create temporary PEPPER home"""
        self.temp_dir = tempfile.mkdtemp()
        self.pepper_home = Path(self.temp_dir)
        self.version_manager = VersionManager(self.pepper_home)

    def tearDown(self):
        """Cleanup temporary directory"""
        shutil.rmtree(self.temp_dir)

    def test_create_version_directory(self):
        """Test version directory creation"""
        version = Version(1, 0, 0)
        version_dir = self.version_manager.create_version_directory(version)

        self.assertTrue(version_dir.exists())
        self.assertTrue((version_dir / 'code').exists())
        self.assertTrue((version_dir / 'config').exists())
        self.assertTrue((version_dir / 'state').exists())

    def test_version_exists(self):
        """Test version existence check"""
        version = Version(1, 0, 0)
        self.assertFalse(self.version_manager.version_exists(version))

        self.version_manager.create_version_directory(version)
        self.assertTrue(self.version_manager.version_exists(version))

    def test_list_versions(self):
        """Test listing versions"""
        # Create multiple versions
        v1 = Version(1, 0, 0)
        v2 = Version(1, 1, 0)
        v3 = Version(1, 2, 0)

        self.version_manager.create_version_directory(v1)
        self.version_manager.create_version_directory(v2)
        self.version_manager.create_version_directory(v3)

        versions = self.version_manager.list_versions()

        self.assertEqual(len(versions), 3)
        # Should be sorted newest first
        self.assertEqual(versions[0], v3)
        self.assertEqual(versions[1], v2)
        self.assertEqual(versions[2], v1)

    def test_save_load_manifest(self):
        """Test manifest save and load"""
        version = Version(1, 0, 0)
        self.version_manager.create_version_directory(version)

        manifest = {
            'git_commit': 'abc123',
            'git_branch': 'main',
            'changelog': ['Initial version'],
        }

        self.version_manager.save_manifest(version, manifest)

        loaded = self.version_manager.load_manifest(version)

        self.assertEqual(loaded['git_commit'], 'abc123')
        self.assertEqual(loaded['git_branch'], 'main')
        self.assertEqual(loaded['version'], 'v1.0.0')
        self.assertIn('created_at', loaded)

    def test_calculate_next_version(self):
        """Test next version calculation"""
        # First version
        next_version = self.version_manager.calculate_next_version('patch')
        self.assertEqual(str(next_version), 'v1.0.0')

        # Create current version
        current = Version(1, 2, 3)
        version_dir = self.version_manager.create_version_directory(current)

        # Create symlink for current
        current_link = self.pepper_home / 'current'
        current_link.symlink_to(version_dir, target_is_directory=True)

        # Calculate next versions
        next_patch = self.version_manager.calculate_next_version('patch')
        self.assertEqual(str(next_patch), 'v1.2.4')

        next_minor = self.version_manager.calculate_next_version('minor')
        self.assertEqual(str(next_minor), 'v1.3.0')

        next_major = self.version_manager.calculate_next_version('major')
        self.assertEqual(str(next_major), 'v2.0.0')


class TestStateManager(unittest.TestCase):
    """Test StateManager class"""

    def setUp(self):
        """Create temporary PEPPER home"""
        self.temp_dir = tempfile.mkdtemp()
        self.pepper_home = Path(self.temp_dir)
        self.state_manager = StateManager(self.pepper_home)

        # Create state files
        (self.pepper_home / 'state').mkdir(parents=True, exist_ok=True)

        with open(self.pepper_home / 'state' / 'sessions.json', 'w') as f:
            json.dump({'active_sessions': {'user1': {}}, 'session_count': 1}, f)

    def tearDown(self):
        """Cleanup temporary directory"""
        shutil.rmtree(self.temp_dir)

    def test_snapshot_state(self):
        """Test state snapshot creation"""
        version_dir = self.pepper_home / 'versions' / 'v1.0.0'
        version_dir.mkdir(parents=True)

        snapshot = self.state_manager.snapshot_state(version_dir)

        self.assertIn('timestamp', snapshot)
        self.assertIn('sessions', snapshot)
        self.assertIn('routing', snapshot)
        self.assertIn('config', snapshot)
        self.assertIn('metrics', snapshot)

        # Check snapshot file created
        snapshot_file = version_dir / 'state' / 'snapshot.json'
        self.assertTrue(snapshot_file.exists())

    def test_validate_state(self):
        """Test state validation"""
        version_dir = self.pepper_home / 'versions' / 'v1.0.0'
        version_dir.mkdir(parents=True)

        # Create snapshot
        self.state_manager.snapshot_state(version_dir)

        # Validate
        is_valid = self.state_manager.validate_state(version_dir)
        self.assertTrue(is_valid)

    def test_export_import_state(self):
        """Test state export and import"""
        export_path = self.pepper_home / 'export.json'

        # Export
        self.state_manager.export_state(export_path)
        self.assertTrue(export_path.exists())

        # Modify state
        with open(self.pepper_home / 'state' / 'sessions.json', 'w') as f:
            json.dump({'active_sessions': {}, 'session_count': 0}, f)

        # Import
        success = self.state_manager.import_state(export_path)
        self.assertTrue(success)

        # Verify restored
        with open(self.pepper_home / 'state' / 'sessions.json', 'r') as f:
            sessions = json.load(f)
        self.assertEqual(sessions['session_count'], 1)


class TestRollbackManager(unittest.TestCase):
    """Test RollbackManager class"""

    def setUp(self):
        """Create temporary PEPPER home"""
        self.temp_dir = tempfile.mkdtemp()
        self.pepper_home = Path(self.temp_dir)
        self.rollback_manager = RollbackManager(self.pepper_home)
        self.version_manager = VersionManager(self.pepper_home)

    def tearDown(self):
        """Cleanup temporary directory"""
        shutil.rmtree(self.temp_dir)

    def test_list_rollbacks_empty(self):
        """Test listing rollbacks when none exist"""
        rollbacks = self.rollback_manager.list_rollbacks()
        self.assertEqual(len(rollbacks), 0)

    def test_rollback_stats_empty(self):
        """Test rollback stats when none exist"""
        stats = self.rollback_manager.get_rollback_stats()
        self.assertEqual(stats['total_rollbacks'], 0)
        self.assertEqual(stats['successful'], 0)
        self.assertEqual(stats['failed'], 0)

    def test_can_rollback_no_versions(self):
        """Test rollback check with no versions"""
        can_rollback = self.rollback_manager.can_rollback()
        self.assertFalse(can_rollback)

    def test_get_rollback_candidate(self):
        """Test getting rollback candidate"""
        candidate = self.rollback_manager.get_rollback_candidate()
        self.assertIsNone(candidate)


def run_tests():
    """Run all tests"""
    unittest.main(verbosity=2)


if __name__ == '__main__':
    run_tests()
