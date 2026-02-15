"""
DigitalTwin Base Class

Represents a remote device in the FactoryLM ecosystem with capabilities,
health monitoring, and remote execution primitives.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional
import httpx
import logging

logger = logging.getLogger(__name__)


class TwinStatus(Enum):
    """Health status of a digital twin"""
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class DigitalTwin:
    """
    Base class for digital twin representations of physical devices.

    A digital twin knows:
    - What the device can do (capabilities)
    - How to communicate with it (url, protocol)
    - Its current health status
    - How to execute actions remotely
    """

    id: str
    name: str
    url: str
    capabilities: List[str] = field(default_factory=list)
    status: TwinStatus = TwinStatus.UNKNOWN
    last_heartbeat: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timeout: int = 30

    def __post_init__(self):
        """Initialize HTTP client after dataclass initialization"""
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self):
        """Close HTTP client resources"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> bool:
        """
        Check if the twin's physical device is online and responding.

        Returns:
            bool: True if device is healthy, False otherwise
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{self.url}/health")

            if response.status_code == 200:
                self.status = TwinStatus.ONLINE
                self.last_heartbeat = datetime.utcnow()
                logger.info(f"✅ {self.name} health check passed")
                return True
            else:
                self.status = TwinStatus.DEGRADED
                logger.warning(f"⚠️ {self.name} health check degraded: {response.status_code}")
                return False

        except httpx.RequestError as e:
            self.status = TwinStatus.OFFLINE
            logger.error(f"❌ {self.name} health check failed: {e}")
            return False

    async def execute(self, action: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a high-level action on the twin's physical device.

        Args:
            action: The action to execute (e.g., "read_plc_tags", "git_status")
            params: Action-specific parameters

        Returns:
            dict: Action result with status and data
        """
        if params is None:
            params = {}

        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.url}/execute",
                json={"action": action, "params": params}
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ {self.name}.{action} executed successfully")
                return result
            else:
                logger.error(f"❌ {self.name}.{action} failed: {response.status_code}")
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "details": response.text
                }

        except httpx.RequestError as e:
            logger.error(f"❌ {self.name}.{action} request failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def shell(self, command: str, timeout: int = 30) -> str:
        """
        Execute a shell command on the twin's physical device.

        Args:
            command: Shell command to execute
            timeout: Command timeout in seconds

        Returns:
            str: Command output
        """
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.url}/shell",
                json={"command": command, "timeout": timeout}
            )

            if response.status_code == 200:
                result = response.json()
                output = result.get("stdout", "") + result.get("stderr", "")
                logger.info(f"✅ {self.name} executed: {command[:50]}...")
                return output
            else:
                logger.error(f"❌ {self.name} shell failed: {response.status_code}")
                return f"Error: HTTP {response.status_code}"

        except httpx.RequestError as e:
            logger.error(f"❌ {self.name} shell request failed: {e}")
            return f"Error: {e}"

    async def read_file(self, path: str) -> str:
        """
        Read a file from the twin's physical device.

        Args:
            path: Absolute file path on the remote device

        Returns:
            str: File contents
        """
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.url}/files/read",
                json={"path": path}
            )

            if response.status_code == 200:
                result = response.json()
                content = result.get("content", "")
                logger.info(f"✅ {self.name} read file: {path}")
                return content
            else:
                logger.error(f"❌ {self.name} read file failed: {response.status_code}")
                return ""

        except httpx.RequestError as e:
            logger.error(f"❌ {self.name} read file request failed: {e}")
            return ""

    async def write_file(self, path: str, content: str) -> bool:
        """
        Write a file to the twin's physical device.

        Args:
            path: Absolute file path on the remote device
            content: File content to write

        Returns:
            bool: True if write succeeded, False otherwise
        """
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.url}/files/write",
                json={"path": path, "content": content}
            )

            if response.status_code == 200:
                logger.info(f"✅ {self.name} wrote file: {path}")
                return True
            else:
                logger.error(f"❌ {self.name} write file failed: {response.status_code}")
                return False

        except httpx.RequestError as e:
            logger.error(f"❌ {self.name} write file request failed: {e}")
            return False

    def has_capability(self, capability: str) -> bool:
        """Check if twin has a specific capability"""
        return capability in self.capabilities

    def is_online(self) -> bool:
        """Check if twin is currently online"""
        return self.status == TwinStatus.ONLINE

    def __repr__(self) -> str:
        """String representation of the twin"""
        return f"<{self.__class__.__name__} id={self.id} name={self.name} status={self.status.value}>"
