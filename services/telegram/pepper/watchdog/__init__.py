"""
PEPPER Watchdog Monitoring System
==================================

Real-time health monitoring, drift detection, and auto-recovery for FactoryLM.

Components:
- health: Node and service health checking
- drift: Configuration drift detection
- api_validator: API key validation
- fingerprint: System structural fingerprinting
- recovery: Auto-recovery actions
- alerts: Multi-channel alert routing
- main: Orchestrator service

Author: FactoryLM Engineering
Version: 1.0.0
"""

from .health import HealthChecker, HealthReport, NodeHealth, ServiceHealth
from .drift import DriftDetector, DriftReport, DriftSeverity
from .api_validator import APIValidator, KeyStatus
from .fingerprint import SystemFingerprint, FingerprintReport
from .recovery import RecoveryManager, RecoveryAction, RecoveryResult
from .alerts import AlertManager, AlertSeverity, Alert

__version__ = "1.0.0"

__all__ = [
    # Health monitoring
    "HealthChecker",
    "HealthReport",
    "NodeHealth",
    "ServiceHealth",

    # Drift detection
    "DriftDetector",
    "DriftReport",
    "DriftSeverity",

    # API validation
    "APIValidator",
    "KeyStatus",

    # Fingerprinting
    "SystemFingerprint",
    "FingerprintReport",

    # Recovery
    "RecoveryManager",
    "RecoveryAction",
    "RecoveryResult",

    # Alerting
    "AlertManager",
    "AlertSeverity",
    "Alert",
]
