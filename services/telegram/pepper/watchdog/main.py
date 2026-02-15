"""
PEPPER Watchdog Main Orchestrator
==================================

Coordinates all watchdog subsystems:
- Health monitoring
- Configuration drift detection
- API key validation
- System fingerprinting
- Auto-recovery
- Alert routing

Runs continuous monitoring loops with configurable intervals.
"""

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, time
from pathlib import Path
from typing import Optional

import yaml

from .alerts import AlertManager, AlertSeverity
from .api_validator import APIValidator
from .drift import DriftDetector, DriftSeverity
from .fingerprint import SystemFingerprint
from .health import HealthChecker, HealthStatus
from .recovery import RecoveryManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


class WatchdogOrchestrator:
    """
    Main watchdog orchestrator.

    Coordinates all monitoring and recovery subsystems.
    """

    def __init__(self, config_path: str):
        """
        Initialize watchdog orchestrator.

        Args:
            config_path: Path to watchdog.yaml configuration
        """
        self.config_path = Path(config_path)
        self.config = self._load_config()

        # State directory
        state_dir = self.config.get("state_dir", "/root/.pepper-watchdog")
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # Initialize subsystems
        logger.info("Initializing watchdog subsystems")

        self.health_checker = HealthChecker(self.config)
        self.drift_detector = DriftDetector(self.config, state_dir)
        self.api_validator = APIValidator(self.config)
        self.fingerprint = SystemFingerprint(self.config, state_dir)
        self.recovery_manager = RecoveryManager(self.config, state_dir)
        self.alert_manager = AlertManager(self.config, state_dir)

        # Monitoring intervals
        self.health_interval = self.config.get("health", {}).get(
            "interval_seconds", 300
        )
        self.api_interval = self.config.get("api_validation", {}).get(
            "interval_seconds", 900
        )
        self.fingerprint_interval = self.config.get("fingerprint", {}).get(
            "interval_seconds", 300
        )

        # Control flags
        self.running = False
        self.tasks = []

        # Graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info("Watchdog orchestrator initialized")

    def _load_config(self) -> dict:
        """
        Load watchdog configuration.

        Returns:
            Configuration dictionary
        """
        try:
            with open(self.config_path) as f:
                config = yaml.safe_load(f)
            logger.info(f"Loaded configuration from {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        asyncio.create_task(self.stop())

    async def _health_check_loop(self):
        """Continuous health checking loop."""
        logger.info(
            f"Starting health check loop (interval: {self.health_interval}s)"
        )

        while self.running:
            try:
                # Run health checks
                report = await self.health_checker.check_all()

                # Handle unhealthy components
                if report.overall_status == HealthStatus.UNHEALTHY:
                    critical_issues = report.get_critical_issues()

                    await self.alert_manager.send_critical(
                        title="System Health Critical",
                        message="\n".join(critical_issues),
                        node_count=len(report.nodes),
                        service_count=len(report.services),
                    )

                    # Attempt recovery for failed services
                    for svc_name, svc_health in report.services.items():
                        if svc_health.critical and not svc_health.is_healthy:
                            logger.warning(
                                f"Critical service {svc_name} unhealthy, "
                                "attempting recovery"
                            )

                            recovery_result = await self.recovery_manager.handle_service_failure(
                                svc_name
                            )

                            if recovery_result.success:
                                await self.alert_manager.send_info(
                                    title=f"Service Recovered: {svc_name}",
                                    message=recovery_result.message,
                                )
                            else:
                                await self.alert_manager.send_warning(
                                    title=f"Recovery Failed: {svc_name}",
                                    message=recovery_result.message,
                                    error=recovery_result.error,
                                )

                elif report.overall_status == HealthStatus.DEGRADED:
                    await self.alert_manager.send_warning(
                        title="System Health Degraded",
                        message="Some components are degraded",
                        node_count=len(report.nodes),
                        service_count=len(report.services),
                    )

                # Wait for next interval
                await asyncio.sleep(self.health_interval)

            except asyncio.CancelledError:
                logger.info("Health check loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait before retrying

    async def _drift_check_loop(self):
        """Continuous configuration drift monitoring."""
        logger.info("Starting drift detection loop")

        # Initial check
        await asyncio.sleep(10)  # Wait for system to stabilize

        while self.running:
            try:
                # Check for configuration drift
                report = await self.drift_detector.check_drift()

                if report.has_changes:
                    if report.overall_severity == DriftSeverity.CRITICAL:
                        await self.alert_manager.send_critical(
                            title="Critical Configuration Drift",
                            message=f"{len(report.changes)} critical config files changed",
                            changes=len(report.changes),
                        )

                        # Log details
                        for change in report.critical_changes:
                            logger.error(
                                f"CRITICAL CONFIG CHANGE: {change.path} "
                                f"(backed up to {change.backup_path})"
                            )

                    elif report.overall_severity == DriftSeverity.WARNING:
                        await self.alert_manager.send_warning(
                            title="Configuration Drift Detected",
                            message=f"{len(report.changes)} config files changed",
                            changes=len(report.changes),
                        )

                    else:
                        await self.alert_manager.send_info(
                            title="Configuration Updated",
                            message=f"{len(report.changes)} config files changed",
                        )

                # Check every 5 minutes
                await asyncio.sleep(300)

            except asyncio.CancelledError:
                logger.info("Drift check loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in drift check loop: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def _api_validation_loop(self):
        """Continuous API key validation."""
        logger.info(f"Starting API validation loop (interval: {self.api_interval}s)")

        while self.running:
            try:
                # Validate all API keys
                results = await self.api_validator.validate_all()

                # Check for invalid keys
                invalid_keys = [
                    provider for provider, status in results.items()
                    if not status.is_valid
                ]

                if invalid_keys:
                    await self.alert_manager.send_critical(
                        title="Invalid API Keys Detected",
                        message=f"The following API keys are invalid: {', '.join(invalid_keys)}",
                        invalid_count=len(invalid_keys),
                        total_count=len(results),
                    )

                    for provider in invalid_keys:
                        logger.error(
                            f"INVALID API KEY: {provider} - {results[provider].error}"
                        )

                # Wait for next interval
                await asyncio.sleep(self.api_interval)

            except asyncio.CancelledError:
                logger.info("API validation loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in API validation loop: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def _fingerprint_loop(self):
        """Continuous system fingerprinting."""
        logger.info(
            f"Starting fingerprint loop (interval: {self.fingerprint_interval}s)"
        )

        while self.running:
            try:
                # Check system fingerprint
                report = await self.fingerprint.check_fingerprint()

                if report.has_changes:
                    await self.alert_manager.send_warning(
                        title="System Structure Changed",
                        message=f"Detected {len(report.changes_detected)} structural changes",
                        changes=report.changes_detected,
                    )

                    for change in report.changes_detected:
                        logger.warning(f"STRUCTURAL CHANGE: {change}")

                # Wait for next interval
                await asyncio.sleep(self.fingerprint_interval)

            except asyncio.CancelledError:
                logger.info("Fingerprint loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in fingerprint loop: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def _daily_digest_loop(self):
        """Daily digest scheduler."""
        logger.info("Starting daily digest loop")

        while self.running:
            try:
                # Wait until digest hour
                now = datetime.now()
                digest_time = time(hour=self.alert_manager.digest_hour)

                # Calculate next digest time
                next_digest = datetime.combine(now.date(), digest_time)
                if now.time() > digest_time:
                    # Already past today's digest time, schedule for tomorrow
                    next_digest = datetime.combine(
                        now.date(), digest_time
                    ) + asyncio.timedelta(days=1)

                # Wait until digest time
                wait_seconds = (next_digest - now).total_seconds()
                logger.info(
                    f"Next daily digest scheduled for {next_digest} "
                    f"({wait_seconds / 3600:.1f} hours)"
                )

                await asyncio.sleep(wait_seconds)

                # Send digest
                await self.alert_manager.send_daily_digest()

            except asyncio.CancelledError:
                logger.info("Daily digest loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in daily digest loop: {e}", exc_info=True)
                await asyncio.sleep(3600)  # Wait an hour before retrying

    async def start(self):
        """Start all watchdog subsystems."""
        logger.info("Starting PEPPER Watchdog")

        self.running = True

        # Send startup notification
        await self.alert_manager.send_info(
            title="Watchdog Started",
            message="PEPPER Watchdog monitoring system started",
            version=self.config.get("version", "unknown"),
        )

        # Start all monitoring loops
        self.tasks = [
            asyncio.create_task(self._health_check_loop()),
            asyncio.create_task(self._drift_check_loop()),
            asyncio.create_task(self._api_validation_loop()),
            asyncio.create_task(self._fingerprint_loop()),
            asyncio.create_task(self._daily_digest_loop()),
        ]

        logger.info(f"Started {len(self.tasks)} monitoring loops")

        # Wait for all tasks
        try:
            await asyncio.gather(*self.tasks)
        except asyncio.CancelledError:
            logger.info("All monitoring loops cancelled")

    async def stop(self):
        """Stop all watchdog subsystems."""
        logger.info("Stopping PEPPER Watchdog")

        self.running = False

        # Cancel all tasks
        for task in self.tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self.tasks, return_exceptions=True)

        # Send shutdown notification
        await self.alert_manager.send_info(
            title="Watchdog Stopped",
            message="PEPPER Watchdog monitoring system stopped",
        )

        logger.info("Watchdog stopped")


async def main():
    """Main entry point."""
    # Determine config path
    config_path = os.getenv("WATCHDOG_CONFIG", "/root/pepper/watchdog.yaml")

    logger.info(f"PEPPER Watchdog starting with config: {config_path}")

    # Create and start orchestrator
    orchestrator = WatchdogOrchestrator(config_path)

    try:
        await orchestrator.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await orchestrator.stop()


if __name__ == "__main__":
    asyncio.run(main())
