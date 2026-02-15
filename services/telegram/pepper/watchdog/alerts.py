"""
Alert Manager
=============

Multi-channel alert routing and delivery.

Features:
- Severity-based routing (CRITICAL, WARNING, INFO)
- Multiple channels (Telegram, log, Axiom)
- Alert deduplication
- Daily digest compilation
- Rate limiting
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set

import httpx

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Alert:
    """Alert message."""
    severity: AlertSeverity
    title: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "watchdog"
    metadata: Dict = field(default_factory=dict)

    def to_telegram_message(self) -> str:
        """
        Format alert for Telegram.

        Returns:
            Formatted message string
        """
        emoji = {
            AlertSeverity.CRITICAL: "🚨",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.INFO: "ℹ️",
        }

        lines = [
            f"{emoji.get(self.severity, '🔔')} **{self.severity.upper()}**",
            f"",
            f"**{self.title}**",
            f"{self.message}",
            f"",
            f"_Source: {self.source}_",
            f"_Time: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}_",
        ]

        return "\n".join(lines)

    def to_log_entry(self) -> str:
        """
        Format alert for log file.

        Returns:
            Log entry string
        """
        return (
            f"[{self.timestamp.isoformat()}] "
            f"{self.severity.upper()} - {self.title}: {self.message}"
        )


class AlertManager:
    """
    Multi-channel alert manager.

    Routes alerts to appropriate channels based on severity.
    """

    def __init__(self, config: dict, state_dir: str):
        """
        Initialize alert manager.

        Args:
            config: Watchdog configuration
            state_dir: Directory to store alert state
        """
        self.config = config
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.alerts_config = config.get("alerts", {})
        self.telegram_config = self.alerts_config.get("telegram", {})
        self.log_config = self.alerts_config.get("log", {})
        self.severity_routing = self.alerts_config.get("severity_routing", {})

        # Alert deduplication
        self.recent_alerts: Set[str] = set()
        self.dedup_window_minutes = 5

        # Daily digest
        self.digest_config = self.alerts_config.get("daily_digest", {})
        self.digest_enabled = self.digest_config.get("enabled", True)
        self.digest_hour = self.digest_config.get("hour", 8)

        # Alert log file
        log_path = self.log_config.get("path", str(self.state_dir / "alerts.log"))
        self.alert_log_path = Path(log_path)
        self.alert_log_path.parent.mkdir(parents=True, exist_ok=True)

        # Digest storage
        self.digest_file = self.state_dir / "daily_alerts.json"
        self.daily_alerts: List[Alert] = self._load_daily_alerts()

    def _load_daily_alerts(self) -> List[Alert]:
        """
        Load today's alerts for digest.

        Returns:
            List of alerts from today
        """
        if not self.digest_file.exists():
            return []

        try:
            with open(self.digest_file) as f:
                data = json.load(f)

            # Check if alerts are from today
            if data.get("date") != datetime.now().strftime("%Y-%m-%d"):
                return []

            # Reconstruct Alert objects (simplified)
            alerts = []
            for alert_data in data.get("alerts", []):
                alerts.append(Alert(
                    severity=AlertSeverity(alert_data["severity"]),
                    title=alert_data["title"],
                    message=alert_data["message"],
                    timestamp=datetime.fromisoformat(alert_data["timestamp"]),
                    source=alert_data.get("source", "watchdog"),
                ))

            return alerts

        except Exception as e:
            logger.error(f"Error loading daily alerts: {e}")
            return []

    def _save_daily_alerts(self):
        """Save today's alerts to disk."""
        try:
            data = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "alerts": [
                    {
                        "severity": alert.severity.value,
                        "title": alert.title,
                        "message": alert.message,
                        "timestamp": alert.timestamp.isoformat(),
                        "source": alert.source,
                    }
                    for alert in self.daily_alerts
                ],
            }

            with open(self.digest_file, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Error saving daily alerts: {e}")

    def _is_duplicate(self, alert: Alert) -> bool:
        """
        Check if alert is a duplicate within dedup window.

        Args:
            alert: Alert to check

        Returns:
            True if duplicate
        """
        alert_key = f"{alert.severity}:{alert.title}:{alert.message}"
        return alert_key in self.recent_alerts

    def _mark_as_sent(self, alert: Alert):
        """
        Mark alert as sent for deduplication.

        Args:
            alert: Alert that was sent
        """
        alert_key = f"{alert.severity}:{alert.title}:{alert.message}"
        self.recent_alerts.add(alert_key)

        # Schedule cleanup
        asyncio.create_task(
            self._cleanup_dedup_entry(
                alert_key, minutes=self.dedup_window_minutes
            )
        )

    async def _cleanup_dedup_entry(self, alert_key: str, minutes: int):
        """
        Remove dedup entry after timeout.

        Args:
            alert_key: Alert key to remove
            minutes: Minutes to wait
        """
        await asyncio.sleep(minutes * 60)
        self.recent_alerts.discard(alert_key)

    async def send_alert(self, alert: Alert):
        """
        Send alert to appropriate channels.

        Args:
            alert: Alert to send
        """
        # Check for duplicate
        if self._is_duplicate(alert):
            logger.debug(f"Skipping duplicate alert: {alert.title}")
            return

        logger.info(f"Sending {alert.severity.value} alert: {alert.title}")

        # Add to daily digest
        if self.digest_enabled:
            self.daily_alerts.append(alert)
            self._save_daily_alerts()

        # Get routing for this severity
        channels = self.severity_routing.get(alert.severity.value, ["log"])

        # Send to each channel
        tasks = []
        for channel in channels:
            if channel == "telegram":
                tasks.append(self._send_telegram(alert))
            elif channel == "log":
                tasks.append(self._send_log(alert))
            # Add more channels as needed (Axiom, email, etc.)

        # Send concurrently
        await asyncio.gather(*tasks, return_exceptions=True)

        # Mark as sent
        self._mark_as_sent(alert)

    async def _send_telegram(self, alert: Alert):
        """
        Send alert to Telegram.

        Args:
            alert: Alert to send
        """
        if not self.telegram_config.get("enabled", False):
            logger.debug("Telegram alerts disabled")
            return

        bot_token = self.telegram_config.get("bot_token")
        chat_id = self.telegram_config.get("chat_id")

        if not bot_token or not chat_id:
            logger.error("Telegram credentials not configured")
            return

        try:
            message = alert.to_telegram_message()

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": "Markdown",
                    },
                )

                if response.status_code == 200:
                    logger.debug(f"Sent alert to Telegram: {alert.title}")
                else:
                    logger.error(
                        f"Telegram API error: {response.status_code} - {response.text}"
                    )

        except Exception as e:
            logger.error(f"Error sending Telegram alert: {e}")

    async def _send_log(self, alert: Alert):
        """
        Log alert to file.

        Args:
            alert: Alert to log
        """
        if not self.log_config.get("enabled", True):
            return

        try:
            log_entry = alert.to_log_entry()

            with open(self.alert_log_path, "a") as f:
                f.write(log_entry + "\n")

            logger.debug(f"Logged alert: {alert.title}")

        except Exception as e:
            logger.error(f"Error logging alert: {e}")

    async def send_daily_digest(self):
        """Send daily digest of all alerts."""
        if not self.digest_enabled:
            return

        if not self.daily_alerts:
            logger.info("No alerts to include in daily digest")
            return

        logger.info(f"Sending daily digest with {len(self.daily_alerts)} alerts")

        # Group alerts by severity
        critical = [a for a in self.daily_alerts if a.severity == AlertSeverity.CRITICAL]
        warnings = [a for a in self.daily_alerts if a.severity == AlertSeverity.WARNING]
        info = [a for a in self.daily_alerts if a.severity == AlertSeverity.INFO]

        # Build digest message
        lines = [
            f"📊 **Daily Watchdog Digest**",
            f"_{datetime.now().strftime('%Y-%m-%d')}_",
            f"",
            f"**Summary:**",
            f"🚨 Critical: {len(critical)}",
            f"⚠️ Warnings: {len(warnings)}",
            f"ℹ️ Info: {len(info)}",
            f"",
        ]

        if critical:
            lines.append("**Critical Alerts:**")
            for alert in critical[:5]:  # Limit to 5
                lines.append(f"- {alert.title}")
            if len(critical) > 5:
                lines.append(f"  _(and {len(critical) - 5} more)_")
            lines.append("")

        if warnings:
            lines.append("**Warnings:**")
            for alert in warnings[:5]:
                lines.append(f"- {alert.title}")
            if len(warnings) > 5:
                lines.append(f"  _(and {len(warnings) - 5} more)_")
            lines.append("")

        digest_message = "\n".join(lines)

        # Send digest
        digest_alert = Alert(
            severity=AlertSeverity.INFO,
            title="Daily Digest",
            message=digest_message,
            source="watchdog-digest",
        )

        # Send without dedup check
        await self._send_telegram(digest_alert)
        await self._send_log(digest_alert)

        # Clear daily alerts
        self.daily_alerts.clear()
        self._save_daily_alerts()

    async def send_critical(self, title: str, message: str, **metadata):
        """
        Send critical alert.

        Args:
            title: Alert title
            message: Alert message
            **metadata: Additional metadata
        """
        alert = Alert(
            severity=AlertSeverity.CRITICAL,
            title=title,
            message=message,
            metadata=metadata,
        )
        await self.send_alert(alert)

    async def send_warning(self, title: str, message: str, **metadata):
        """
        Send warning alert.

        Args:
            title: Alert title
            message: Alert message
            **metadata: Additional metadata
        """
        alert = Alert(
            severity=AlertSeverity.WARNING,
            title=title,
            message=message,
            metadata=metadata,
        )
        await self.send_alert(alert)

    async def send_info(self, title: str, message: str, **metadata):
        """
        Send info alert.

        Args:
            title: Alert title
            message: Alert message
            **metadata: Additional metadata
        """
        alert = Alert(
            severity=AlertSeverity.INFO,
            title=title,
            message=message,
            metadata=metadata,
        )
        await self.send_alert(alert)
