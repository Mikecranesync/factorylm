"""
Health Checker Module
=====================

Monitors node and service health across the FactoryLM infrastructure.

Checks:
- Node reachability (PLC, Travel, VPS)
- Service status (systemd services)
- API endpoints (Matrix API)
- Response latency and uptime
"""

import asyncio
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class NodeHealth:
    """Health status for a single node."""
    node_id: str
    name: str
    url: str
    status: HealthStatus
    latency_ms: Optional[float] = None
    last_seen: Optional[datetime] = None
    error: Optional[str] = None
    critical: bool = False

    @property
    def is_healthy(self) -> bool:
        """Quick check if node is healthy."""
        return self.status == HealthStatus.HEALTHY


@dataclass
class ServiceHealth:
    """Health status for a systemd service."""
    name: str
    status: HealthStatus
    active: bool = False
    running: bool = False
    pid: Optional[int] = None
    uptime: Optional[str] = None
    error: Optional[str] = None
    critical: bool = False

    @property
    def is_healthy(self) -> bool:
        """Quick check if service is healthy."""
        return self.active and self.running


@dataclass
class HealthReport:
    """Comprehensive health report."""
    timestamp: datetime
    nodes: Dict[str, NodeHealth] = field(default_factory=dict)
    services: Dict[str, ServiceHealth] = field(default_factory=dict)
    overall_status: HealthStatus = HealthStatus.UNKNOWN

    def compute_overall_status(self) -> HealthStatus:
        """
        Compute overall system health.

        Logic:
        - If any CRITICAL component is UNHEALTHY -> UNHEALTHY
        - If any component is DEGRADED -> DEGRADED
        - Otherwise -> HEALTHY
        """
        critical_unhealthy = any(
            (node.critical and not node.is_healthy for node in self.nodes.values()) or
            (svc.critical and not svc.is_healthy for svc in self.services.values())
        )

        if critical_unhealthy:
            return HealthStatus.UNHEALTHY

        any_degraded = any(
            node.status == HealthStatus.DEGRADED for node in self.nodes.values()
        ) or any(
            svc.status == HealthStatus.DEGRADED for svc in self.services.values()
        )

        if any_degraded:
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    def get_critical_issues(self) -> List[str]:
        """Get list of critical issues."""
        issues = []

        for node in self.nodes.values():
            if node.critical and not node.is_healthy:
                issues.append(f"Node '{node.name}' is {node.status.value}")

        for svc in self.services.values():
            if svc.critical and not svc.is_healthy:
                issues.append(f"Service '{svc.name}' is {svc.status.value}")

        return issues


class HealthChecker:
    """
    Health checker for nodes and services.

    Monitors:
    - Remote nodes (via HTTP health endpoints)
    - Local systemd services
    - API endpoints
    """

    def __init__(self, config: dict):
        """
        Initialize health checker.

        Args:
            config: Watchdog configuration from watchdog.yaml
        """
        self.config = config
        self.timeout = config.get("health", {}).get("timeout_seconds", 10)
        self.node_configs = config.get("health", {}).get("nodes", [])
        self.service_configs = config.get("health", {}).get("services", [])

    async def check_all(self) -> HealthReport:
        """
        Run all health checks.

        Returns:
            Comprehensive health report
        """
        logger.info("Starting health check cycle")
        report = HealthReport(timestamp=datetime.now())

        # Check nodes concurrently
        node_tasks = [
            self._check_node(node_cfg)
            for node_cfg in self.node_configs
        ]
        node_results = await asyncio.gather(*node_tasks, return_exceptions=True)

        for node_cfg, result in zip(self.node_configs, node_results):
            if isinstance(result, Exception):
                logger.error(f"Node check failed for {node_cfg['id']}: {result}")
                report.nodes[node_cfg["id"]] = NodeHealth(
                    node_id=node_cfg["id"],
                    name=node_cfg["name"],
                    url=node_cfg["url"],
                    status=HealthStatus.UNHEALTHY,
                    error=str(result),
                    critical=node_cfg.get("critical", False),
                )
            else:
                report.nodes[node_cfg["id"]] = result

        # Check services sequentially (systemctl is local)
        for svc_cfg in self.service_configs:
            try:
                svc_health = await self._check_service(svc_cfg)
                report.services[svc_cfg["name"]] = svc_health
            except Exception as e:
                logger.error(f"Service check failed for {svc_cfg['name']}: {e}")
                report.services[svc_cfg["name"]] = ServiceHealth(
                    name=svc_cfg["name"],
                    status=HealthStatus.UNHEALTHY,
                    error=str(e),
                    critical=svc_cfg.get("critical", False),
                )

        # Compute overall status
        report.overall_status = report.compute_overall_status()

        logger.info(
            f"Health check complete: {report.overall_status.value} "
            f"({len(report.nodes)} nodes, {len(report.services)} services)"
        )

        return report

    async def _check_node(self, node_cfg: dict) -> NodeHealth:
        """
        Check health of a single node.

        Args:
            node_cfg: Node configuration from watchdog.yaml

        Returns:
            NodeHealth status
        """
        node_id = node_cfg["id"]
        name = node_cfg["name"]
        url = node_cfg["url"]
        critical = node_cfg.get("critical", False)

        start_time = datetime.now()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                latency_ms = (datetime.now() - start_time).total_seconds() * 1000

                if response.status_code == 200:
                    return NodeHealth(
                        node_id=node_id,
                        name=name,
                        url=url,
                        status=HealthStatus.HEALTHY,
                        latency_ms=latency_ms,
                        last_seen=datetime.now(),
                        critical=critical,
                    )
                else:
                    return NodeHealth(
                        node_id=node_id,
                        name=name,
                        url=url,
                        status=HealthStatus.DEGRADED,
                        latency_ms=latency_ms,
                        error=f"HTTP {response.status_code}",
                        critical=critical,
                    )

        except httpx.TimeoutException:
            logger.warning(f"Node {name} timed out after {self.timeout}s")
            return NodeHealth(
                node_id=node_id,
                name=name,
                url=url,
                status=HealthStatus.UNHEALTHY,
                error="Timeout",
                critical=critical,
            )

        except Exception as e:
            logger.error(f"Node {name} check failed: {e}")
            return NodeHealth(
                node_id=node_id,
                name=name,
                url=url,
                status=HealthStatus.UNHEALTHY,
                error=str(e),
                critical=critical,
            )

    async def _check_service(self, svc_cfg: dict) -> ServiceHealth:
        """
        Check health of a systemd service.

        Args:
            svc_cfg: Service configuration from watchdog.yaml

        Returns:
            ServiceHealth status
        """
        name = svc_cfg["name"]
        critical = svc_cfg.get("critical", False)

        try:
            # Run systemctl status
            result = subprocess.run(
                ["systemctl", "status", name],
                capture_output=True,
                text=True,
                timeout=5,
            )

            output = result.stdout + result.stderr
            active = "active" in output.lower()
            running = "running" in output.lower()

            # Extract PID if available
            pid = None
            for line in output.split("\n"):
                if "Main PID:" in line:
                    try:
                        pid = int(line.split("Main PID:")[1].split()[0])
                    except (IndexError, ValueError):
                        pass

            # Determine status
            if active and running:
                status = HealthStatus.HEALTHY
            elif active:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.UNHEALTHY

            return ServiceHealth(
                name=name,
                status=status,
                active=active,
                running=running,
                pid=pid,
                critical=critical,
            )

        except subprocess.TimeoutExpired:
            logger.error(f"Service check timeout for {name}")
            return ServiceHealth(
                name=name,
                status=HealthStatus.UNHEALTHY,
                error="Timeout",
                critical=critical,
            )

        except Exception as e:
            logger.error(f"Service check failed for {name}: {e}")
            return ServiceHealth(
                name=name,
                status=HealthStatus.UNHEALTHY,
                error=str(e),
                critical=critical,
            )
