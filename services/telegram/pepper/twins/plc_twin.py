"""
PLC Laptop Digital Twin

Represents the PLC laptop with Factory I/O simulation, Micro 820 PLC connection,
and Matrix API integration. Provides factory-specific diagnostics and fault injection.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from .twin import DigitalTwin, TwinStatus

logger = logging.getLogger(__name__)


class PLCTwin(DigitalTwin):
    """
    Digital twin for the PLC laptop (LAPTOP-0KA3C70H).

    Capabilities:
    - Factory I/O simulation control
    - Micro 820 PLC tag reading/writing via Matrix API
    - Fault injection for testing
    - AI-powered factory diagnosis
    - Real-time I/O status monitoring
    """

    def __init__(self, id: str = "plc", name: str = "PLC Laptop", url: str = "http://100.72.2.99:8765"):
        """Initialize PLC twin with factory-specific capabilities"""
        super().__init__(
            id=id,
            name=name,
            url=url,
            capabilities=[
                "read_plc_tags",
                "write_plc_tag",
                "inject_fault",
                "get_io_status",
                "diagnose",
                "start_factory_io",
                "stop_factory_io",
                "reset_simulation",
                "get_tag_history",
                "execute_ladder_logic"
            ],
            metadata={
                "device_type": "plc_laptop",
                "plc_model": "Micro 820",
                "simulation": "Factory I/O",
                "ip_address": "100.72.2.99",
                "tailscale_name": "LAPTOP-0KA3C70H"
            }
        )

    async def read_plc_tags(self, tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Read PLC tags via Matrix API.

        Args:
            tags: List of tag names to read, or None for all tags

        Returns:
            dict: Tag names mapped to their current values
        """
        params = {"tags": tags} if tags else {}
        result = await self.execute("read_plc_tags", params)

        if result.get("success"):
            logger.info(f"📊 Read {len(result.get('tags', {}))} PLC tags")
        else:
            logger.error(f"❌ Failed to read PLC tags: {result.get('error')}")

        return result

    async def write_plc_tag(self, tag: str, value: Any) -> bool:
        """
        Write a value to a PLC tag via Matrix API.

        Args:
            tag: Tag name
            value: Value to write

        Returns:
            bool: True if write succeeded
        """
        result = await self.execute("write_plc_tag", {"tag": tag, "value": value})

        if result.get("success"):
            logger.info(f"✍️ Wrote {tag} = {value}")
            return True
        else:
            logger.error(f"❌ Failed to write {tag}: {result.get('error')}")
            return False

    async def inject_fault(self, fault_type: str, duration: int = 60) -> Dict[str, Any]:
        """
        Inject a fault into the Factory I/O simulation for testing.

        Args:
            fault_type: Type of fault (e.g., "conveyor_jam", "sensor_failure", "motor_overload")
            duration: Fault duration in seconds

        Returns:
            dict: Fault injection result with details
        """
        result = await self.execute("inject_fault", {
            "fault_type": fault_type,
            "duration": duration,
            "timestamp": datetime.utcnow().isoformat()
        })

        if result.get("success"):
            logger.info(f"⚠️ Injected fault: {fault_type} for {duration}s")
        else:
            logger.error(f"❌ Fault injection failed: {result.get('error')}")

        return result

    async def get_io_status(self) -> Dict[str, Any]:
        """
        Get current I/O status from Factory I/O and PLC.

        Returns:
            dict: I/O status including inputs, outputs, and sensors
        """
        result = await self.execute("get_io_status")

        if result.get("success"):
            logger.info("📡 Retrieved I/O status")
        else:
            logger.error(f"❌ Failed to get I/O status: {result.get('error')}")

        return result

    async def diagnose(self, question: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        AI-powered factory diagnosis using current PLC state and I/O.

        Args:
            question: Natural language question about factory state
            context: Optional additional context for diagnosis

        Returns:
            str: AI diagnosis response
        """
        params = {"question": question}
        if context:
            params["context"] = context

        result = await self.execute("diagnose", params)

        if result.get("success"):
            diagnosis = result.get("response", "No diagnosis available")
            logger.info(f"🤖 AI Diagnosis complete for: {question[:50]}...")
            return diagnosis
        else:
            logger.error(f"❌ Diagnosis failed: {result.get('error')}")
            return f"Diagnosis failed: {result.get('error', 'Unknown error')}"

    async def start_factory_io(self) -> bool:
        """Start Factory I/O simulation"""
        result = await self.execute("start_factory_io")
        return result.get("success", False)

    async def stop_factory_io(self) -> bool:
        """Stop Factory I/O simulation"""
        result = await self.execute("stop_factory_io")
        return result.get("success", False)

    async def reset_simulation(self) -> bool:
        """Reset Factory I/O simulation to initial state"""
        result = await self.execute("reset_simulation")
        if result.get("success"):
            logger.info("🔄 Factory I/O simulation reset")
        return result.get("success", False)

    async def get_tag_history(self, tag: str, duration_minutes: int = 60) -> List[Dict[str, Any]]:
        """
        Get historical values for a PLC tag.

        Args:
            tag: Tag name
            duration_minutes: How far back to retrieve history

        Returns:
            list: Historical tag values with timestamps
        """
        result = await self.execute("get_tag_history", {
            "tag": tag,
            "duration_minutes": duration_minutes
        })

        if result.get("success"):
            history = result.get("history", [])
            logger.info(f"📈 Retrieved {len(history)} historical values for {tag}")
            return history
        else:
            logger.error(f"❌ Failed to get tag history: {result.get('error')}")
            return []

    async def execute_ladder_logic(self, program: str) -> Dict[str, Any]:
        """
        Execute ladder logic program on the PLC.

        Args:
            program: Ladder logic program code

        Returns:
            dict: Execution result
        """
        result = await self.execute("execute_ladder_logic", {"program": program})

        if result.get("success"):
            logger.info("⚙️ Ladder logic executed successfully")
        else:
            logger.error(f"❌ Ladder logic execution failed: {result.get('error')}")

        return result

    async def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information from PLC laptop"""
        info = {
            "twin_id": self.id,
            "twin_name": self.name,
            "status": self.status.value,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "capabilities": self.capabilities,
            "metadata": self.metadata
        }

        # Try to get additional system info via shell
        try:
            system_info = await self.shell("systeminfo | findstr /B /C:\"OS Name\" /C:\"OS Version\"")
            info["os_info"] = system_info
        except Exception as e:
            logger.warning(f"Could not retrieve OS info: {e}")

        return info
