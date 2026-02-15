"""
VPS Digital Twin

Represents the VPS server with Clawdbot, n8n workflows, and orchestration services.
Provides messaging, workflow automation, and system management capabilities.
"""

from typing import Dict, Any, List, Optional
import logging

from .twin import DigitalTwin, TwinStatus

logger = logging.getLogger(__name__)


class VPSTwin(DigitalTwin):
    """
    Digital twin for the VPS (100.68.120.99).

    Capabilities:
    - Telegram messaging via Clawdbot
    - n8n workflow execution
    - Service orchestration
    - Log retrieval and analysis
    - System health monitoring
    """

    def __init__(self, id: str = "vps", name: str = "VPS Server", url: str = "http://100.68.120.99:8765"):
        """Initialize VPS twin with orchestration capabilities"""
        super().__init__(
            id=id,
            name=name,
            url=url,
            capabilities=[
                "send_telegram",
                "trigger_workflow",
                "get_logs",
                "list_workflows",
                "get_service_status",
                "restart_service",
                "execute_webhook",
                "get_metrics",
                "backup_data",
                "restore_data",
                "manage_cron",
                "update_config"
            ],
            metadata={
                "device_type": "vps",
                "ip_address": "100.68.120.99",
                "role": "orchestration",
                "services": ["clawdbot", "n8n", "jarvis", "nginx"],
                "provider": "unknown"
            }
        )

    async def send_telegram(self, chat_id: str, message: str, parse_mode: str = "Markdown") -> bool:
        """
        Send a Telegram message via Clawdbot.

        Args:
            chat_id: Telegram chat ID
            message: Message text
            parse_mode: Message formatting ("Markdown", "HTML", or None)

        Returns:
            bool: True if message sent successfully
        """
        result = await self.execute("send_telegram", {
            "chat_id": chat_id,
            "message": message,
            "parse_mode": parse_mode
        })

        if result.get("success"):
            logger.info(f"💬 Sent Telegram message to {chat_id}")
            return True
        else:
            logger.error(f"❌ Failed to send Telegram message: {result.get('error')}")
            return False

    async def trigger_workflow(self, workflow_id: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Trigger an n8n workflow.

        Args:
            workflow_id: n8n workflow ID or name
            data: Optional workflow input data

        Returns:
            dict: Workflow execution result
        """
        params = {"workflow_id": workflow_id}
        if data:
            params["data"] = data

        result = await self.execute("trigger_workflow", params)

        if result.get("success"):
            logger.info(f"⚙️ Triggered workflow: {workflow_id}")
        else:
            logger.error(f"❌ Workflow trigger failed: {result.get('error')}")

        return result

    async def get_logs(self, service: str, lines: int = 100, level: str = "all") -> str:
        """
        Retrieve logs from a service.

        Args:
            service: Service name ("clawdbot", "n8n", "jarvis", "nginx")
            lines: Number of log lines to retrieve
            level: Log level filter ("error", "warning", "info", "all")

        Returns:
            str: Log contents
        """
        result = await self.execute("get_logs", {
            "service": service,
            "lines": lines,
            "level": level
        })

        if result.get("success"):
            logs = result.get("logs", "")
            logger.info(f"📄 Retrieved {lines} lines from {service} logs")
            return logs
        else:
            logger.error(f"❌ Failed to get logs: {result.get('error')}")
            return ""

    async def list_workflows(self) -> List[Dict[str, Any]]:
        """
        List all n8n workflows.

        Returns:
            list: Workflow information including ID, name, active status
        """
        result = await self.execute("list_workflows")

        if result.get("success"):
            workflows = result.get("workflows", [])
            logger.info(f"📋 Retrieved {len(workflows)} workflows")
            return workflows
        else:
            logger.error(f"❌ Failed to list workflows: {result.get('error')}")
            return []

    async def get_service_status(self, service: Optional[str] = None) -> Dict[str, Any]:
        """
        Get status of VPS services.

        Args:
            service: Specific service name, or None for all services

        Returns:
            dict: Service status information
        """
        params = {}
        if service:
            params["service"] = service

        result = await self.execute("get_service_status", params)

        if result.get("success"):
            if service:
                logger.info(f"📊 Service status: {service}")
            else:
                logger.info("📊 Retrieved all service statuses")
        else:
            logger.error(f"❌ Failed to get service status: {result.get('error')}")

        return result

    async def restart_service(self, service: str) -> bool:
        """
        Restart a VPS service.

        Args:
            service: Service name to restart

        Returns:
            bool: True if restart succeeded
        """
        result = await self.execute("restart_service", {"service": service})

        if result.get("success"):
            logger.info(f"🔄 Restarted service: {service}")
            return True
        else:
            logger.error(f"❌ Failed to restart service: {result.get('error')}")
            return False

    async def execute_webhook(self, webhook_id: str, method: str = "POST", data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute an n8n webhook.

        Args:
            webhook_id: Webhook ID or path
            method: HTTP method ("GET", "POST", "PUT", "DELETE")
            data: Optional webhook data

        Returns:
            dict: Webhook response
        """
        params = {
            "webhook_id": webhook_id,
            "method": method
        }
        if data:
            params["data"] = data

        result = await self.execute("execute_webhook", params)

        if result.get("success"):
            logger.info(f"🪝 Executed webhook: {webhook_id}")
        else:
            logger.error(f"❌ Webhook execution failed: {result.get('error')}")

        return result

    async def get_metrics(self, metric_type: Optional[str] = None, duration: str = "1h") -> Dict[str, Any]:
        """
        Get system metrics.

        Args:
            metric_type: Specific metric ("cpu", "memory", "disk", "network", None for all)
            duration: Time range for metrics ("1h", "24h", "7d")

        Returns:
            dict: System metrics
        """
        params = {"duration": duration}
        if metric_type:
            params["metric_type"] = metric_type

        result = await self.execute("get_metrics", params)

        if result.get("success"):
            logger.info(f"📈 Retrieved metrics for {duration}")
        else:
            logger.error(f"❌ Failed to get metrics: {result.get('error')}")

        return result

    async def backup_data(self, backup_type: str = "full", services: Optional[List[str]] = None) -> bool:
        """
        Create a backup of VPS data.

        Args:
            backup_type: Backup type ("full", "incremental", "config")
            services: Specific services to backup (None for all)

        Returns:
            bool: True if backup succeeded
        """
        params = {"backup_type": backup_type}
        if services:
            params["services"] = services

        result = await self.execute("backup_data", params)

        if result.get("success"):
            logger.info(f"💾 Backup created: {backup_type}")
            return True
        else:
            logger.error(f"❌ Backup failed: {result.get('error')}")
            return False

    async def restore_data(self, backup_id: str, services: Optional[List[str]] = None) -> bool:
        """
        Restore data from a backup.

        Args:
            backup_id: Backup identifier
            services: Specific services to restore (None for all)

        Returns:
            bool: True if restore succeeded
        """
        params = {"backup_id": backup_id}
        if services:
            params["services"] = services

        result = await self.execute("restore_data", params)

        if result.get("success"):
            logger.info(f"♻️ Restored from backup: {backup_id}")
            return True
        else:
            logger.error(f"❌ Restore failed: {result.get('error')}")
            return False

    async def manage_cron(self, action: str, job_id: Optional[str] = None, schedule: Optional[str] = None, command: Optional[str] = None) -> Dict[str, Any]:
        """
        Manage cron jobs.

        Args:
            action: Action to perform ("list", "add", "remove", "enable", "disable")
            job_id: Job identifier for remove/enable/disable actions
            schedule: Cron schedule for add action (e.g., "0 * * * *")
            command: Command to run for add action

        Returns:
            dict: Cron management result
        """
        params = {"action": action}
        if job_id:
            params["job_id"] = job_id
        if schedule:
            params["schedule"] = schedule
        if command:
            params["command"] = command

        result = await self.execute("manage_cron", params)

        if result.get("success"):
            logger.info(f"⏰ Cron {action} succeeded")
        else:
            logger.error(f"❌ Cron {action} failed: {result.get('error')}")

        return result

    async def update_config(self, service: str, config: Dict[str, Any], restart: bool = True) -> bool:
        """
        Update service configuration.

        Args:
            service: Service name
            config: Configuration updates
            restart: Whether to restart service after update

        Returns:
            bool: True if update succeeded
        """
        result = await self.execute("update_config", {
            "service": service,
            "config": config,
            "restart": restart
        })

        if result.get("success"):
            logger.info(f"⚙️ Updated {service} configuration")
            return True
        else:
            logger.error(f"❌ Config update failed: {result.get('error')}")
            return False

    async def get_clawdbot_stats(self) -> Dict[str, Any]:
        """
        Get Clawdbot statistics and status.

        Returns:
            dict: Bot statistics including message counts, uptime, active chats
        """
        result = await self.execute("get_clawdbot_stats")

        if result.get("success"):
            logger.info("🤖 Retrieved Clawdbot stats")
        else:
            logger.error(f"❌ Failed to get Clawdbot stats: {result.get('error')}")

        return result
