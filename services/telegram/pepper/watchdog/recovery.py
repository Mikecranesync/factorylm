"""
Auto-Recovery Manager
=====================

Automatic recovery actions for service failures.

Features:
- Service restart with cooldown
- Attempt tracking and limits
- Recovery action logging
- Integration with health checks
"""

import asyncio
import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class RecoveryAction(str, Enum):
    """Types of recovery actions."""
    RESTART_SERVICE = "restart_service"
    ALERT_ONLY = "alert_only"
    NONE = "none"


@dataclass
class RecoveryAttempt:
    """Record of a recovery attempt."""
    timestamp: datetime
    action: RecoveryAction
    target: str
    success: bool
    error: Optional[str] = None


@dataclass
class RecoveryResult:
    """Result of a recovery operation."""
    action: RecoveryAction
    target: str
    success: bool
    message: str
    attempt_number: int
    error: Optional[str] = None


class RecoveryManager:
    """
    Automatic recovery manager.

    Handles service restarts with intelligent cooldown and retry logic.
    """

    def __init__(self, config: dict, state_dir: str):
        """
        Initialize recovery manager.

        Args:
            config: Watchdog configuration
            state_dir: Directory to store recovery state
        """
        self.config = config
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.recovery_config = config.get("recovery", {})
        self.enabled = self.recovery_config.get("enabled", True)
        self.max_attempts = self.recovery_config.get("max_attempts", 3)
        self.cooldown_minutes = self.recovery_config.get("cooldown_minutes", 5)

        self.attempts_file = self.state_dir / "recovery_attempts.json"
        self.attempts: Dict[str, list] = self._load_attempts()

    def _load_attempts(self) -> Dict[str, list]:
        """
        Load recovery attempt history from disk.

        Returns:
            Dictionary mapping target to list of attempt timestamps
        """
        if not self.attempts_file.exists():
            return {}

        try:
            with open(self.attempts_file) as f:
                data = json.load(f)

            # Convert ISO timestamps back to datetime
            attempts = {}
            for target, timestamps in data.items():
                attempts[target] = [
                    datetime.fromisoformat(ts) for ts in timestamps
                ]

            return attempts

        except Exception as e:
            logger.error(f"Error loading recovery attempts: {e}")
            return {}

    def _save_attempts(self):
        """Save recovery attempt history to disk."""
        try:
            # Convert datetime to ISO format
            data = {}
            for target, timestamps in self.attempts.items():
                data[target] = [ts.isoformat() for ts in timestamps]

            with open(self.attempts_file, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Error saving recovery attempts: {e}")

    def _cleanup_old_attempts(self, target: str):
        """
        Remove attempt records older than cooldown period.

        Args:
            target: Recovery target (e.g., service name)
        """
        if target not in self.attempts:
            return

        cutoff = datetime.now() - timedelta(minutes=self.cooldown_minutes)
        self.attempts[target] = [
            ts for ts in self.attempts[target] if ts > cutoff
        ]

    def _can_attempt_recovery(self, target: str) -> tuple[bool, Optional[str]]:
        """
        Check if recovery can be attempted for target.

        Args:
            target: Recovery target

        Returns:
            Tuple of (can_attempt, reason_if_not)
        """
        if not self.enabled:
            return False, "Recovery is disabled"

        self._cleanup_old_attempts(target)

        if target not in self.attempts:
            return True, None

        recent_attempts = len(self.attempts[target])

        if recent_attempts >= self.max_attempts:
            return False, (
                f"Max attempts ({self.max_attempts}) reached within "
                f"{self.cooldown_minutes} minute cooldown"
            )

        return True, None

    def _record_attempt(self, target: str, success: bool):
        """
        Record a recovery attempt.

        Args:
            target: Recovery target
            success: Whether attempt succeeded
        """
        if target not in self.attempts:
            self.attempts[target] = []

        self.attempts[target].append(datetime.now())
        self._save_attempts()

        logger.info(
            f"Recorded recovery attempt for {target}: "
            f"{'success' if success else 'failed'} "
            f"({len(self.attempts[target])}/{self.max_attempts})"
        )

    async def restart_service(self, service_name: str) -> RecoveryResult:
        """
        Restart a systemd service.

        Args:
            service_name: Name of service to restart

        Returns:
            RecoveryResult with outcome
        """
        logger.info(f"Attempting to restart service: {service_name}")

        # Check if we can attempt recovery
        can_attempt, reason = self._can_attempt_recovery(service_name)

        if not can_attempt:
            logger.warning(f"Cannot restart {service_name}: {reason}")
            return RecoveryResult(
                action=RecoveryAction.ALERT_ONLY,
                target=service_name,
                success=False,
                message=reason or "Recovery not allowed",
                attempt_number=len(self.attempts.get(service_name, [])),
            )

        # Get current attempt number
        attempt_number = len(self.attempts.get(service_name, [])) + 1

        try:
            # Execute systemctl restart
            result = subprocess.run(
                ["systemctl", "restart", service_name],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                logger.info(f"Successfully restarted service: {service_name}")
                self._record_attempt(service_name, success=True)

                # Wait a moment for service to stabilize
                await asyncio.sleep(2)

                # Verify service is running
                verify_result = subprocess.run(
                    ["systemctl", "is-active", service_name],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                is_active = verify_result.stdout.strip() == "active"

                if is_active:
                    return RecoveryResult(
                        action=RecoveryAction.RESTART_SERVICE,
                        target=service_name,
                        success=True,
                        message=f"Service restarted successfully (attempt {attempt_number})",
                        attempt_number=attempt_number,
                    )
                else:
                    self._record_attempt(service_name, success=False)
                    return RecoveryResult(
                        action=RecoveryAction.RESTART_SERVICE,
                        target=service_name,
                        success=False,
                        message=f"Service restart command succeeded but service not active",
                        attempt_number=attempt_number,
                        error=verify_result.stdout.strip(),
                    )

            else:
                logger.error(
                    f"Failed to restart {service_name}: {result.stderr}"
                )
                self._record_attempt(service_name, success=False)

                return RecoveryResult(
                    action=RecoveryAction.RESTART_SERVICE,
                    target=service_name,
                    success=False,
                    message=f"systemctl restart failed (attempt {attempt_number})",
                    attempt_number=attempt_number,
                    error=result.stderr.strip(),
                )

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout restarting service: {service_name}")
            self._record_attempt(service_name, success=False)

            return RecoveryResult(
                action=RecoveryAction.RESTART_SERVICE,
                target=service_name,
                success=False,
                message=f"Restart command timed out (attempt {attempt_number})",
                attempt_number=attempt_number,
                error="Command timeout",
            )

        except Exception as e:
            logger.error(f"Error restarting service {service_name}: {e}")
            self._record_attempt(service_name, success=False)

            return RecoveryResult(
                action=RecoveryAction.RESTART_SERVICE,
                target=service_name,
                success=False,
                message=f"Unexpected error during restart (attempt {attempt_number})",
                attempt_number=attempt_number,
                error=str(e),
            )

    async def handle_service_failure(self, service_name: str) -> RecoveryResult:
        """
        Handle a service failure with appropriate recovery action.

        Args:
            service_name: Name of failed service

        Returns:
            RecoveryResult
        """
        # Check if service is configured for auto-restart
        service_configs = self.config.get("health", {}).get("services", [])
        service_config = next(
            (s for s in service_configs if s["name"] == service_name),
            None,
        )

        if not service_config:
            logger.warning(f"Unknown service: {service_name}")
            return RecoveryResult(
                action=RecoveryAction.ALERT_ONLY,
                target=service_name,
                success=False,
                message="Service not in configuration",
                attempt_number=0,
            )

        auto_restart = service_config.get("auto_restart", False)

        if not auto_restart:
            logger.info(f"Service {service_name} not configured for auto-restart")
            return RecoveryResult(
                action=RecoveryAction.ALERT_ONLY,
                target=service_name,
                success=False,
                message="Auto-restart disabled for this service",
                attempt_number=0,
            )

        # Attempt restart
        return await self.restart_service(service_name)

    def reset_attempts(self, target: Optional[str] = None):
        """
        Reset recovery attempt counters.

        Args:
            target: Specific target to reset, or None for all
        """
        if target is None:
            self.attempts.clear()
            logger.info("Reset all recovery attempt counters")
        elif target in self.attempts:
            del self.attempts[target]
            logger.info(f"Reset recovery attempts for {target}")

        self._save_attempts()

    def get_attempt_count(self, target: str) -> int:
        """
        Get recent attempt count for a target.

        Args:
            target: Recovery target

        Returns:
            Number of recent attempts
        """
        self._cleanup_old_attempts(target)
        return len(self.attempts.get(target, []))

    def get_all_attempts(self) -> Dict[str, int]:
        """
        Get recent attempt counts for all targets.

        Returns:
            Dictionary mapping target to attempt count
        """
        counts = {}
        for target in list(self.attempts.keys()):
            self._cleanup_old_attempts(target)
            if self.attempts[target]:  # Only include if has recent attempts
                counts[target] = len(self.attempts[target])
        return counts
