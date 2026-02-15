"""
Version Management for PEPPER

Semantic versioning with automatic version bumping and validation.
"""

import re
from dataclasses import dataclass
from typing import Optional, List
from pathlib import Path
import json
from datetime import datetime


@dataclass
class Version:
    """Semantic version representation"""
    major: int
    minor: int
    patch: int

    def __str__(self) -> str:
        return f"v{self.major}.{self.minor}.{self.patch}"

    def __lt__(self, other: 'Version') -> bool:
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return False
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)

    def bump(self, level: str) -> 'Version':
        """
        Bump version according to semantic versioning rules

        Args:
            level: 'major', 'minor', or 'patch'

        Returns:
            New Version object
        """
        if level == 'major':
            return Version(self.major + 1, 0, 0)
        elif level == 'minor':
            return Version(self.major, self.minor + 1, 0)
        elif level == 'patch':
            return Version(self.major, self.minor, self.patch + 1)
        else:
            raise ValueError(f"Invalid bump level: {level}. Use 'major', 'minor', or 'patch'")

    @classmethod
    def parse(cls, version_str: str) -> 'Version':
        """
        Parse version string (e.g., 'v1.2.3' or '1.2.3')

        Args:
            version_str: Version string to parse

        Returns:
            Version object

        Raises:
            ValueError: If version string is invalid
        """
        # Remove 'v' prefix if present
        version_str = version_str.lstrip('v')

        # Match semantic version pattern
        pattern = r'^(\d+)\.(\d+)\.(\d+)$'
        match = re.match(pattern, version_str)

        if not match:
            raise ValueError(f"Invalid version format: {version_str}. Expected format: X.Y.Z")

        major, minor, patch = map(int, match.groups())
        return cls(major, minor, patch)


class VersionManager:
    """Manage versions and version history for PEPPER"""

    def __init__(self, pepper_home: Path):
        """
        Initialize version manager

        Args:
            pepper_home: Path to PEPPER home directory (e.g., /root/.pepper)
        """
        self.pepper_home = Path(pepper_home)
        self.versions_dir = self.pepper_home / "versions"
        self.versions_dir.mkdir(parents=True, exist_ok=True)

    def get_current_version(self) -> Optional[Version]:
        """
        Get currently deployed version

        Returns:
            Current Version or None if no version deployed
        """
        current_link = self.pepper_home / "current"
        if not current_link.exists():
            return None

        # Read symlink target
        target = current_link.resolve()
        version_str = target.name

        try:
            return Version.parse(version_str)
        except ValueError:
            return None

    def get_previous_version(self) -> Optional[Version]:
        """
        Get previous version (for quick rollback)

        Returns:
            Previous Version or None
        """
        previous_link = self.pepper_home / "previous"
        if not previous_link.exists():
            return None

        target = previous_link.resolve()
        version_str = target.name

        try:
            return Version.parse(version_str)
        except ValueError:
            return None

    def list_versions(self) -> List[Version]:
        """
        List all deployed versions

        Returns:
            List of Version objects, sorted newest first
        """
        versions = []

        for version_dir in self.versions_dir.iterdir():
            if version_dir.is_dir():
                try:
                    version = Version.parse(version_dir.name)
                    versions.append(version)
                except ValueError:
                    # Skip invalid version directories
                    continue

        # Sort newest first
        return sorted(versions, reverse=True)

    def version_exists(self, version: Version) -> bool:
        """Check if a version exists"""
        version_dir = self.versions_dir / str(version)
        return version_dir.exists()

    def get_version_path(self, version: Version) -> Path:
        """Get path to version directory"""
        return self.versions_dir / str(version)

    def create_version_directory(self, version: Version) -> Path:
        """
        Create directory structure for new version

        Returns:
            Path to version directory
        """
        version_dir = self.get_version_path(version)

        if version_dir.exists():
            raise FileExistsError(f"Version {version} already exists")

        # Create version directory structure
        version_dir.mkdir(parents=True)
        (version_dir / "code").mkdir()
        (version_dir / "config").mkdir()
        (version_dir / "state").mkdir()

        return version_dir

    def save_manifest(self, version: Version, manifest: dict):
        """
        Save version manifest

        Args:
            version: Version to save manifest for
            manifest: Manifest dictionary
        """
        version_dir = self.get_version_path(version)
        manifest_path = version_dir / "manifest.json"

        # Add metadata
        manifest['version'] = str(version)
        manifest['created_at'] = datetime.utcnow().isoformat() + 'Z'

        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

    def load_manifest(self, version: Version) -> dict:
        """
        Load version manifest

        Args:
            version: Version to load manifest for

        Returns:
            Manifest dictionary
        """
        version_dir = self.get_version_path(version)
        manifest_path = version_dir / "manifest.json"

        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found for version {version}")

        with open(manifest_path, 'r') as f:
            return json.load(f)

    def calculate_next_version(self, bump_level: str = 'patch') -> Version:
        """
        Calculate next version based on current version

        Args:
            bump_level: 'major', 'minor', or 'patch'

        Returns:
            Next Version
        """
        current = self.get_current_version()

        if current is None:
            # First version
            return Version(1, 0, 0)

        return current.bump(bump_level)

    def cleanup_old_versions(self, keep_count: int = 5):
        """
        Remove old versions, keeping only the most recent ones

        Args:
            keep_count: Number of versions to keep
        """
        versions = self.list_versions()

        if len(versions) <= keep_count:
            return

        # Get current and previous versions to protect them
        current = self.get_current_version()
        previous = self.get_previous_version()
        protected = {current, previous}

        # Remove old versions beyond keep_count
        for version in versions[keep_count:]:
            if version not in protected:
                version_dir = self.get_version_path(version)

                # Remove directory recursively
                import shutil
                shutil.rmtree(version_dir)
                print(f"Removed old version: {version}")
