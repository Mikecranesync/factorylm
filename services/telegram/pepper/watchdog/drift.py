"""
Configuration Drift Detector
=============================

Detects and tracks configuration changes across critical system files.

Features:
- Hash-based change detection
- Critical vs. warning field classification
- Automatic backup on change
- Drift severity assessment
"""

import hashlib
import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class DriftSeverity(str, Enum):
    """Drift detection severity levels."""
    CRITICAL = "critical"      # API keys, tokens changed
    WARNING = "warning"        # Model config, URLs changed
    INFO = "info"              # Formatting, comments changed
    NONE = "none"              # No changes detected


@dataclass
class FileChange:
    """Details about a changed file."""
    path: str
    old_hash: str
    new_hash: str
    severity: DriftSeverity
    changed_fields: List[str] = field(default_factory=list)
    backup_path: Optional[str] = None


@dataclass
class DriftReport:
    """Configuration drift detection report."""
    timestamp: datetime
    changes: List[FileChange] = field(default_factory=list)
    overall_severity: DriftSeverity = DriftSeverity.NONE

    @property
    def has_changes(self) -> bool:
        """Check if any changes detected."""
        return len(self.changes) > 0

    @property
    def critical_changes(self) -> List[FileChange]:
        """Get only critical changes."""
        return [c for c in self.changes if c.severity == DriftSeverity.CRITICAL]

    def compute_overall_severity(self) -> DriftSeverity:
        """Compute overall drift severity."""
        if any(c.severity == DriftSeverity.CRITICAL for c in self.changes):
            return DriftSeverity.CRITICAL
        elif any(c.severity == DriftSeverity.WARNING for c in self.changes):
            return DriftSeverity.WARNING
        elif self.has_changes:
            return DriftSeverity.INFO
        else:
            return DriftSeverity.NONE


class DriftDetector:
    """
    Configuration drift detector.

    Monitors critical config files and detects structural changes.
    """

    def __init__(self, config: dict, state_dir: str):
        """
        Initialize drift detector.

        Args:
            config: Watchdog configuration from watchdog.yaml
            state_dir: Directory to store state and baselines
        """
        self.config = config
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.baseline_dir = self.state_dir / "baselines"
        self.baseline_dir.mkdir(exist_ok=True)

        self.backup_dir = self.state_dir / "config_backups"
        self.backup_dir.mkdir(exist_ok=True)

        self.drift_config = config.get("drift", {})
        self.monitored_files = self.drift_config.get("monitored_files", [])
        self.backup_on_change = self.drift_config.get("backup_on_change", True)

    def _compute_file_hash(self, file_path: str) -> Optional[str]:
        """
        Compute SHA256 hash of a file.

        Args:
            file_path: Path to file

        Returns:
            Hex digest of file hash, or None if file doesn't exist
        """
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        try:
            hasher = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            logger.error(f"Error hashing file {file_path}: {e}")
            return None

    def _load_baseline(self, file_path: str) -> Optional[str]:
        """
        Load baseline hash for a file.

        Args:
            file_path: Path to monitored file

        Returns:
            Baseline hash or None if no baseline exists
        """
        baseline_file = self.baseline_dir / f"{Path(file_path).name}.hash"
        if baseline_file.exists():
            try:
                return baseline_file.read_text().strip()
            except Exception as e:
                logger.error(f"Error reading baseline for {file_path}: {e}")
        return None

    def _save_baseline(self, file_path: str, file_hash: str):
        """
        Save baseline hash for a file.

        Args:
            file_path: Path to monitored file
            file_hash: Current file hash
        """
        baseline_file = self.baseline_dir / f"{Path(file_path).name}.hash"
        try:
            baseline_file.write_text(file_hash)
            logger.debug(f"Saved baseline for {file_path}")
        except Exception as e:
            logger.error(f"Error saving baseline for {file_path}: {e}")

    def _backup_file(self, file_path: str) -> Optional[str]:
        """
        Create timestamped backup of a file.

        Args:
            file_path: Path to file to backup

        Returns:
            Path to backup file, or None on error
        """
        if not self.backup_on_change:
            return None

        path = Path(file_path)
        if not path.exists():
            return None

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{path.name}.{timestamp}.bak"
            backup_path = self.backup_dir / backup_name

            shutil.copy2(path, backup_path)
            logger.info(f"Backed up {file_path} to {backup_path}")

            # Cleanup old backups (keep last 10)
            self._cleanup_old_backups(path.name)

            return str(backup_path)

        except Exception as e:
            logger.error(f"Error backing up {file_path}: {e}")
            return None

    def _cleanup_old_backups(self, filename: str):
        """
        Remove old backup files, keeping the most recent 10.

        Args:
            filename: Base filename to clean up
        """
        try:
            backups = sorted(
                self.backup_dir.glob(f"{filename}.*.bak"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            max_backups = self.config.get("backup", {}).get("max_config_backups", 10)

            for old_backup in backups[max_backups:]:
                old_backup.unlink()
                logger.debug(f"Removed old backup: {old_backup}")

        except Exception as e:
            logger.error(f"Error cleaning up backups for {filename}: {e}")

    def _analyze_changes(self, file_path: str, file_config: dict) -> DriftSeverity:
        """
        Analyze file changes to determine severity.

        Args:
            file_path: Path to changed file
            file_config: File configuration with critical/warning fields

        Returns:
            Drift severity level
        """
        critical_fields = file_config.get("critical_fields", [])
        warning_fields = file_config.get("warning_fields", [])

        if not (critical_fields or warning_fields):
            # No field-level analysis, just report change
            return DriftSeverity.INFO

        try:
            path = Path(file_path)
            if path.suffix == ".json":
                with open(path) as f:
                    data = json.load(f)
            elif path.suffix in (".yaml", ".yml"):
                with open(path) as f:
                    data = yaml.safe_load(f)
            else:
                return DriftSeverity.INFO

            # Check if critical fields exist (simplified check)
            # In production, would compare old vs. new values
            for field_path in critical_fields:
                if self._field_exists(data, field_path):
                    # Assume critical field changed if file hash changed
                    return DriftSeverity.CRITICAL

            for field_path in warning_fields:
                if self._field_exists(data, field_path):
                    return DriftSeverity.WARNING

            return DriftSeverity.INFO

        except Exception as e:
            logger.error(f"Error analyzing changes in {file_path}: {e}")
            return DriftSeverity.WARNING

    def _field_exists(self, data: dict, field_path: str) -> bool:
        """
        Check if a field path exists in nested dict.

        Args:
            data: Configuration data
            field_path: Dot-notation path (e.g., "nodes.*.url")

        Returns:
            True if field exists
        """
        parts = field_path.split(".")
        current = data

        for part in parts:
            if part == "*":
                # Wildcard - check any key
                if isinstance(current, dict):
                    return len(current) > 0
                return False

            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return False

        return True

    async def check_drift(self) -> DriftReport:
        """
        Check all monitored files for configuration drift.

        Returns:
            Drift detection report
        """
        logger.info("Starting drift detection check")
        report = DriftReport(timestamp=datetime.now())

        for file_config in self.monitored_files:
            file_path = file_config["path"]
            current_hash = self._compute_file_hash(file_path)

            if current_hash is None:
                # File doesn't exist or can't be read
                continue

            baseline_hash = self._load_baseline(file_path)

            if baseline_hash is None:
                # First run - establish baseline
                self._save_baseline(file_path, current_hash)
                logger.info(f"Established baseline for {file_path}")
                continue

            if current_hash != baseline_hash:
                # Drift detected!
                logger.warning(f"Configuration drift detected in {file_path}")

                severity = self._analyze_changes(file_path, file_config)
                backup_path = self._backup_file(file_path)

                change = FileChange(
                    path=file_path,
                    old_hash=baseline_hash,
                    new_hash=current_hash,
                    severity=severity,
                    backup_path=backup_path,
                )

                report.changes.append(change)

                # Update baseline
                self._save_baseline(file_path, current_hash)

        report.overall_severity = report.compute_overall_severity()

        if report.has_changes:
            logger.warning(
                f"Drift detection complete: {len(report.changes)} files changed "
                f"(severity: {report.overall_severity.value})"
            )
        else:
            logger.info("Drift detection complete: No changes detected")

        return report

    def reset_baselines(self):
        """Reset all baselines (use when intentionally updating configs)."""
        try:
            for file_config in self.monitored_files:
                file_path = file_config["path"]
                current_hash = self._compute_file_hash(file_path)
                if current_hash:
                    self._save_baseline(file_path, current_hash)
            logger.info("All baselines reset")
        except Exception as e:
            logger.error(f"Error resetting baselines: {e}")
