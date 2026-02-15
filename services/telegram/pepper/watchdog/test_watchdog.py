#!/usr/bin/env python3
"""
PEPPER Watchdog Test Suite
===========================

Quick validation of watchdog components.

Usage:
    python test_watchdog.py
"""

import asyncio
import logging
import sys
import tempfile
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger(__name__)


async def test_health_checker():
    """Test health checker functionality."""
    from health import HealthChecker, HealthStatus

    logger.info("Testing HealthChecker...")

    # Mock config
    config = {
        "health": {
            "timeout_seconds": 5,
            "nodes": [
                {
                    "id": "test_node",
                    "name": "Test Node",
                    "url": "http://httpbin.org/status/200",
                    "critical": True,
                }
            ],
            "services": [],
        }
    }

    checker = HealthChecker(config)
    report = await checker.check_all()

    assert report.overall_status in [HealthStatus.HEALTHY, HealthStatus.UNHEALTHY]
    logger.info(f"✓ Health check completed: {report.overall_status.value}")


async def test_drift_detector():
    """Test drift detector functionality."""
    from drift import DriftDetector, DriftSeverity

    logger.info("Testing DriftDetector...")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test file
        test_file = Path(tmpdir) / "test_config.yaml"
        test_file.write_text("version: 1.0.0\ntest: value")

        config = {
            "drift": {
                "enabled": True,
                "backup_on_change": True,
                "monitored_files": [
                    {
                        "path": str(test_file),
                        "critical_fields": [],
                        "warning_fields": [],
                    }
                ],
            }
        }

        detector = DriftDetector(config, tmpdir)

        # First run - establish baseline
        report1 = await detector.check_drift()
        assert not report1.has_changes

        # Modify file
        test_file.write_text("version: 1.0.1\ntest: changed")

        # Second run - detect drift
        report2 = await detector.check_drift()
        assert report2.has_changes

        logger.info(f"✓ Drift detection working: {len(report2.changes)} changes")


async def test_api_validator():
    """Test API validator functionality."""
    from api_validator import APIValidator, KeyStatus

    logger.info("Testing APIValidator...")

    # Mock config with invalid key
    config = {
        "api_validation": {
            "providers": [
                {
                    "name": "test_telegram",
                    "test_endpoint": "https://api.telegram.org/bot{token}/getMe",
                    "env_var": "TEST_INVALID_TOKEN",
                }
            ]
        }
    }

    validator = APIValidator(config)
    results = await validator.validate_all()

    assert "test_telegram" in results
    assert not results["test_telegram"].is_valid

    logger.info("✓ API validation working")


async def test_fingerprint():
    """Test system fingerprinting."""
    from fingerprint import SystemFingerprint

    logger.info("Testing SystemFingerprint...")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test file
        test_file = Path(tmpdir) / "test.conf"
        test_file.write_text("config data")

        config = {
            "fingerprint": {
                "interval_seconds": 300,
                "monitored_files": [str(test_file)],
                "monitored_env_vars": ["PATH"],
            },
            "health": {"nodes": [], "services": []},
        }

        fingerprint = SystemFingerprint(config, tmpdir)

        # First check
        report1 = await fingerprint.check_fingerprint()
        assert not report1.has_changes

        logger.info(f"✓ Fingerprint: {report1.current_fingerprint[:16]}...")


async def test_recovery_manager():
    """Test recovery manager."""
    from recovery import RecoveryManager, RecoveryAction

    logger.info("Testing RecoveryManager...")

    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "recovery": {
                "enabled": True,
                "max_attempts": 3,
                "cooldown_minutes": 5,
            },
            "health": {
                "services": [
                    {
                        "name": "test_service",
                        "critical": True,
                        "auto_restart": True,
                    }
                ]
            },
        }

        manager = RecoveryManager(config, tmpdir)

        # Check attempt counting
        count = manager.get_attempt_count("test_service")
        assert count == 0

        logger.info("✓ Recovery manager initialized")


async def test_alert_manager():
    """Test alert manager."""
    from alerts import AlertManager, AlertSeverity

    logger.info("Testing AlertManager...")

    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "alerts": {
                "telegram": {"enabled": False},
                "log": {
                    "enabled": True,
                    "path": str(Path(tmpdir) / "alerts.log"),
                },
                "severity_routing": {
                    "critical": ["log"],
                    "warning": ["log"],
                    "info": ["log"],
                },
                "daily_digest": {"enabled": False},
            }
        }

        manager = AlertManager(config, tmpdir)

        # Send test alert
        await manager.send_info("Test Alert", "This is a test message")

        # Check log file
        log_file = Path(tmpdir) / "alerts.log"
        assert log_file.exists()

        logger.info("✓ Alert manager working")


async def run_all_tests():
    """Run all tests."""
    logger.info("=" * 50)
    logger.info("PEPPER Watchdog Test Suite")
    logger.info("=" * 50)

    tests = [
        ("Health Checker", test_health_checker),
        ("Drift Detector", test_drift_detector),
        ("API Validator", test_api_validator),
        ("System Fingerprint", test_fingerprint),
        ("Recovery Manager", test_recovery_manager),
        ("Alert Manager", test_alert_manager),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            await test_func()
            passed += 1
        except Exception as e:
            logger.error(f"✗ {name} failed: {e}")
            failed += 1

    logger.info("=" * 50)
    logger.info(f"Results: {passed} passed, {failed} failed")
    logger.info("=" * 50)

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
