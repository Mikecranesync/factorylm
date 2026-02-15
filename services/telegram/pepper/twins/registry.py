"""
Twin Registry

Centralized registry for managing all digital twins in the FactoryLM ecosystem.
Provides twin discovery, routing, health monitoring, and lifecycle management.
"""

from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
import asyncio
import logging

from .twin import DigitalTwin, TwinStatus
from .plc_twin import PLCTwin
from .travel_twin import TravelTwin
from .vps_twin import VPSTwin

logger = logging.getLogger(__name__)


class TwinRegistry:
    """
    Central registry for managing digital twins.

    Responsibilities:
    - Twin discovery and registration
    - Intelligent routing based on capabilities
    - Health monitoring and status tracking
    - Twin lifecycle management
    """

    def __init__(self):
        """Initialize the twin registry"""
        self._twins: Dict[str, DigitalTwin] = {}
        self._capability_index: Dict[str, Set[str]] = {}  # capability -> twin IDs
        self._health_check_task: Optional[asyncio.Task] = None
        self._health_check_interval: int = 60  # seconds

    def register(self, twin: DigitalTwin):
        """
        Register a digital twin.

        Args:
            twin: Digital twin to register
        """
        self._twins[twin.id] = twin

        # Index capabilities for fast lookup
        for capability in twin.capabilities:
            if capability not in self._capability_index:
                self._capability_index[capability] = set()
            self._capability_index[capability].add(twin.id)

        logger.info(f"✅ Registered twin: {twin.name} ({twin.id}) with {len(twin.capabilities)} capabilities")

    def unregister(self, twin_id: str):
        """
        Unregister a digital twin.

        Args:
            twin_id: ID of the twin to unregister
        """
        twin = self._twins.pop(twin_id, None)
        if twin:
            # Remove from capability index
            for capability in twin.capabilities:
                if capability in self._capability_index:
                    self._capability_index[capability].discard(twin_id)
                    if not self._capability_index[capability]:
                        del self._capability_index[capability]

            logger.info(f"🗑️ Unregistered twin: {twin.name} ({twin_id})")
        else:
            logger.warning(f"⚠️ Attempted to unregister unknown twin: {twin_id}")

    def get_twin(self, twin_id: str) -> Optional[DigitalTwin]:
        """
        Get a twin by ID.

        Args:
            twin_id: Twin identifier

        Returns:
            DigitalTwin or None if not found
        """
        return self._twins.get(twin_id)

    def get_all_twins(self) -> List[DigitalTwin]:
        """
        Get all registered twins.

        Returns:
            list: All digital twins
        """
        return list(self._twins.values())

    def get_online_twins(self) -> List[DigitalTwin]:
        """
        Get all twins currently online.

        Returns:
            list: Online digital twins
        """
        return [twin for twin in self._twins.values() if twin.status == TwinStatus.ONLINE]

    def get_offline_twins(self) -> List[DigitalTwin]:
        """
        Get all twins currently offline.

        Returns:
            list: Offline digital twins
        """
        return [twin for twin in self._twins.values() if twin.status == TwinStatus.OFFLINE]

    def resolve_twin(self, identifier: str) -> Optional[DigitalTwin]:
        """
        Resolve a twin by ID, name, or alias.

        Args:
            identifier: Twin ID, name, or alias (e.g., "plc", "factory", "PLC Laptop")

        Returns:
            DigitalTwin or None if not found
        """
        # Try exact ID match first
        twin = self._twins.get(identifier)
        if twin:
            return twin

        # Try name match (case-insensitive)
        identifier_lower = identifier.lower()
        for twin in self._twins.values():
            if twin.name.lower() == identifier_lower:
                return twin

        # Try alias matches for common references
        alias_map = {
            "factory": "plc",
            "plc_laptop": "plc",
            "micro820": "plc",
            "factorio": "plc",
            "dev": "travel",
            "development": "travel",
            "laptop": "travel",
            "cloud": "vps",
            "server": "vps",
            "jarvis": "vps",
            "clawdbot": "vps"
        }

        alias_id = alias_map.get(identifier_lower)
        if alias_id:
            return self._twins.get(alias_id)

        logger.warning(f"⚠️ Could not resolve twin: {identifier}")
        return None

    def find_twins_with_capability(self, capability: str, online_only: bool = True) -> List[DigitalTwin]:
        """
        Find all twins that have a specific capability.

        Args:
            capability: Capability to search for
            online_only: Only return online twins

        Returns:
            list: Twins with the specified capability
        """
        twin_ids = self._capability_index.get(capability, set())
        twins = [self._twins[twin_id] for twin_id in twin_ids if twin_id in self._twins]

        if online_only:
            twins = [twin for twin in twins if twin.status == TwinStatus.ONLINE]

        return twins

    def get_best_twin_for_capability(self, capability: str) -> Optional[DigitalTwin]:
        """
        Get the best available twin for a specific capability.

        Selection criteria:
        1. Online status
        2. Last heartbeat recency
        3. Fewer active connections (if tracked)

        Args:
            capability: Required capability

        Returns:
            DigitalTwin or None if no suitable twin found
        """
        candidates = self.find_twins_with_capability(capability, online_only=True)

        if not candidates:
            logger.warning(f"⚠️ No online twins found with capability: {capability}")
            return None

        # Sort by last heartbeat (most recent first)
        candidates.sort(
            key=lambda t: t.last_heartbeat or datetime.min,
            reverse=True
        )

        best_twin = candidates[0]
        logger.info(f"🎯 Selected {best_twin.name} for capability: {capability}")
        return best_twin

    async def health_check_all(self) -> Dict[str, bool]:
        """
        Check health of all registered twins.

        Returns:
            dict: Twin ID mapped to health status
        """
        results = {}

        # Run health checks in parallel
        tasks = [
            (twin.id, twin.health_check())
            for twin in self._twins.values()
        ]

        for twin_id, coro in tasks:
            try:
                is_healthy = await coro
                results[twin_id] = is_healthy
            except Exception as e:
                logger.error(f"❌ Health check failed for {twin_id}: {e}")
                results[twin_id] = False

        online_count = sum(1 for healthy in results.values() if healthy)
        total_count = len(results)
        logger.info(f"💓 Health check complete: {online_count}/{total_count} twins online")

        return results

    async def start_health_monitoring(self, interval: int = 60):
        """
        Start periodic health monitoring.

        Args:
            interval: Health check interval in seconds
        """
        self._health_check_interval = interval

        async def health_monitor():
            while True:
                try:
                    await self.health_check_all()
                except Exception as e:
                    logger.error(f"❌ Health monitoring error: {e}")

                await asyncio.sleep(self._health_check_interval)

        self._health_check_task = asyncio.create_task(health_monitor())
        logger.info(f"🏥 Started health monitoring (interval: {interval}s)")

    async def stop_health_monitoring(self):
        """Stop periodic health monitoring"""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
            logger.info("🛑 Stopped health monitoring")

    def get_status_summary(self) -> Dict[str, any]:
        """
        Get a summary of all twins and their status.

        Returns:
            dict: Status summary including counts and details
        """
        total = len(self._twins)
        online = len(self.get_online_twins())
        offline = len(self.get_offline_twins())
        degraded = len([t for t in self._twins.values() if t.status == TwinStatus.DEGRADED])

        return {
            "total_twins": total,
            "online": online,
            "offline": offline,
            "degraded": degraded,
            "twins": [
                {
                    "id": twin.id,
                    "name": twin.name,
                    "status": twin.status.value,
                    "url": twin.url,
                    "last_heartbeat": twin.last_heartbeat.isoformat() if twin.last_heartbeat else None,
                    "capabilities_count": len(twin.capabilities)
                }
                for twin in self._twins.values()
            ]
        }

    async def broadcast(self, action: str, params: Dict = None) -> Dict[str, any]:
        """
        Broadcast an action to all online twins.

        Args:
            action: Action to execute
            params: Action parameters

        Returns:
            dict: Results from each twin
        """
        if params is None:
            params = {}

        online_twins = self.get_online_twins()
        results = {}

        for twin in online_twins:
            try:
                result = await twin.execute(action, params)
                results[twin.id] = result
            except Exception as e:
                logger.error(f"❌ Broadcast failed for {twin.id}: {e}")
                results[twin.id] = {"success": False, "error": str(e)}

        logger.info(f"📡 Broadcast {action} to {len(online_twins)} twins")
        return results

    async def shutdown(self):
        """Shutdown the registry and clean up resources"""
        await self.stop_health_monitoring()

        # Close all twin connections
        for twin in self._twins.values():
            try:
                await twin.close()
            except Exception as e:
                logger.error(f"❌ Error closing twin {twin.id}: {e}")

        logger.info("🛑 Twin registry shutdown complete")

    @classmethod
    def create_default(cls) -> "TwinRegistry":
        """
        Create a registry with default twins for FactoryLM.

        Returns:
            TwinRegistry: Registry with PLC, Travel, and VPS twins
        """
        registry = cls()

        # Register default twins
        registry.register(PLCTwin())
        registry.register(TravelTwin())
        registry.register(VPSTwin())

        logger.info("🏭 Created default twin registry with 3 twins")
        return registry
