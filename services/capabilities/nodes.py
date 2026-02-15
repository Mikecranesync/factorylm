"""
Nodes Capability - Multi-Node Routing
=====================================
Route commands to different Jarvis nodes (PLC, Travel, VPS).
"""

import os
import json
import logging
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Node configuration
DEFAULT_TIMEOUT = 30
STATE_FILE = Path(os.getenv("NODES_STATE_FILE", "/tmp/capabilities_nodes_state.json"))

# Default nodes if no config
DEFAULT_NODES = {
    "plc": {
        "id": "plc",
        "aliases": ["plc", "factory"],
        "url": "http://100.72.2.99:8765",
        "name": "PLC Laptop",
        "description": "Factory I/O + Micro 820",
        "capabilities": ["shell", "files", "screenshot"],
    },
    "travel": {
        "id": "travel",
        "aliases": ["travel", "dev"],
        "url": "http://100.83.251.23:8765",
        "name": "Travel Laptop",
        "description": "Development",
        "capabilities": ["shell", "files", "screenshot"],
    },
    "vps": {
        "id": "vps",
        "aliases": ["vps", "jarvis", "ultron"],
        "url": "http://100.68.120.99:8765",
        "name": "VPS (Jarvis)",
        "description": "Cloud orchestration",
        "capabilities": ["shell", "files"],
    },
}


@dataclass
class Node:
    """Represents a Jarvis node."""
    id: str
    aliases: List[str]
    url: str
    name: str
    description: str
    capabilities: List[str]


class NodesCapability:
    """Multi-node routing and execution."""

    def __init__(self, nodes_config: Dict = None, default_node: str = "plc"):
        self.nodes: Dict[str, Node] = {}
        self.alias_map: Dict[str, str] = {}
        self.default_node = default_node
        self._chat_state: Dict[str, str] = {}
        self._http = None

        # Load nodes
        config = nodes_config or DEFAULT_NODES
        for node_id, node_data in config.items():
            node = Node(
                id=node_id,
                aliases=node_data.get("aliases", [node_id]),
                url=node_data["url"],
                name=node_data.get("name", node_id),
                description=node_data.get("description", ""),
                capabilities=node_data.get("capabilities", []),
            )
            self.nodes[node_id] = node
            for alias in node.aliases:
                self.alias_map[alias.lower()] = node_id

        # Load state
        self._load_state()

    def _get_http(self):
        """Lazy-load httpx client."""
        if self._http is None:
            import httpx
            self._http = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)
        return self._http

    def _load_state(self):
        """Load chat state from file."""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE) as f:
                    self._chat_state = json.load(f)
            except Exception:
                self._chat_state = {}

    def _save_state(self):
        """Save chat state to file."""
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(STATE_FILE, 'w') as f:
                json.dump(self._chat_state, f)
        except Exception as e:
            logger.warning(f"Failed to save state: {e}")

    async def health(self) -> dict:
        """Check nodes health."""
        results = await self.check_all()
        online = sum(1 for r in results.values() if r.get("online"))
        return {
            "status": "ok" if online > 0 else "unavailable",
            "nodes_online": online,
            "nodes_total": len(self.nodes),
        }

    def resolve(self, alias: str) -> Optional[Node]:
        """Resolve alias to node."""
        node_id = self.alias_map.get(alias.lower())
        return self.nodes.get(node_id) if node_id else None

    def get_for_chat(self, chat_id: int) -> Node:
        """Get active node for a chat."""
        node_id = self._chat_state.get(str(chat_id), self.default_node)
        return self.nodes.get(node_id, self.nodes[self.default_node])

    def set_for_chat(self, chat_id: int, alias: str) -> Tuple[bool, str]:
        """Set active node for chat."""
        node = self.resolve(alias)
        if not node:
            available = ", ".join(self.alias_map.keys())
            return False, f"Unknown node '{alias}'. Available: {available}"

        self._chat_state[str(chat_id)] = node.id
        self._save_state()
        return True, f"Switched to {node.name} ({node.url})"

    async def shell(
        self,
        node_or_alias: str,
        command: str,
        timeout: int = 30,
        cwd: str = None
    ) -> Dict[str, Any]:
        """
        Execute shell command on a node.

        Args:
            node_or_alias: Node ID or alias
            command: Shell command to execute
            timeout: Command timeout
            cwd: Working directory

        Returns:
            {success, stdout, stderr, exit_code, node}
        """
        node = self.resolve(node_or_alias)
        if not node:
            return {"success": False, "error": f"Unknown node: {node_or_alias}"}

        try:
            http = self._get_http()
            resp = await http.post(
                f"{node.url}/shell",
                json={"command": command, "timeout": timeout, "cwd": cwd}
            )

            if resp.status_code == 200:
                data = resp.json()
                return {
                    "success": True,
                    "stdout": data.get("stdout", ""),
                    "stderr": data.get("stderr", ""),
                    "exit_code": data.get("exit_code", 0),
                    "duration_ms": data.get("duration_ms", 0),
                    "node": node.name,
                    "node_id": node.id
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {resp.status_code}: {resp.text}",
                    "node": node.name
                }

        except Exception as e:
            return {"success": False, "error": str(e), "node": node.name}

    async def screenshot(self, node_or_alias: str) -> Dict[str, Any]:
        """
        Get screenshot from a node.

        Args:
            node_or_alias: Node ID or alias

        Returns:
            {success, image_base64, node}
        """
        node = self.resolve(node_or_alias)
        if not node:
            return {"success": False, "error": f"Unknown node: {node_or_alias}"}

        try:
            http = self._get_http()
            resp = await http.get(f"{node.url}/screenshot")

            if resp.status_code == 200:
                data = resp.json()
                return {
                    "success": True,
                    "image_base64": data.get("image_base64", ""),
                    "node": node.name
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {resp.status_code}",
                    "node": node.name
                }

        except Exception as e:
            return {"success": False, "error": str(e), "node": node.name}

    async def read_file(self, node_or_alias: str, path: str) -> Dict[str, Any]:
        """Read a file from a node."""
        node = self.resolve(node_or_alias)
        if not node:
            return {"success": False, "error": f"Unknown node: {node_or_alias}"}

        try:
            http = self._get_http()
            resp = await http.post(f"{node.url}/files/read", json={"path": path})

            if resp.status_code == 200:
                data = resp.json()
                return {"success": True, "content": data.get("content", ""), "node": node.name}
            else:
                return {"success": False, "error": f"HTTP {resp.status_code}", "node": node.name}

        except Exception as e:
            return {"success": False, "error": str(e), "node": node.name}

    async def write_file(self, node_or_alias: str, path: str, content: str) -> Dict[str, Any]:
        """Write a file to a node."""
        node = self.resolve(node_or_alias)
        if not node:
            return {"success": False, "error": f"Unknown node: {node_or_alias}"}

        try:
            http = self._get_http()
            resp = await http.post(
                f"{node.url}/files/write",
                json={"path": path, "content": content}
            )

            if resp.status_code == 200:
                return {"success": True, "node": node.name}
            else:
                return {"success": False, "error": f"HTTP {resp.status_code}", "node": node.name}

        except Exception as e:
            return {"success": False, "error": str(e), "node": node.name}

    async def check_node(self, node: Node) -> Dict[str, Any]:
        """Check if a node is online."""
        try:
            http = self._get_http()
            resp = await http.get(f"{node.url}/health", timeout=5)

            if resp.status_code == 200:
                data = resp.json()
                return {
                    "online": True,
                    "machine": data.get("machine", node.name),
                    "capabilities": data.get("capabilities", {})
                }
            return {"online": False, "error": f"HTTP {resp.status_code}"}

        except Exception as e:
            return {"online": False, "error": str(e)}

    async def check_all(self) -> Dict[str, Dict[str, Any]]:
        """Check health of all nodes."""
        tasks = [self.check_node(node) for node in self.nodes.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            node_id: (
                r if not isinstance(r, Exception)
                else {"online": False, "error": str(r)}
            )
            for node_id, r in zip(self.nodes.keys(), results)
        }

    def list_nodes(self) -> List[Dict[str, Any]]:
        """List all configured nodes."""
        return [
            {
                "id": node.id,
                "name": node.name,
                "url": node.url,
                "description": node.description,
                "aliases": node.aliases,
                "capabilities": node.capabilities
            }
            for node in self.nodes.values()
        ]

    def format_nodes_list(self) -> str:
        """Format nodes list for display."""
        lines = ["Available Nodes", "=" * 20, ""]

        for node in self.nodes.values():
            aliases = ", ".join(node.aliases)
            lines.append(f"{node.name} ({node.id})")
            lines.append(f"  URL: {node.url}")
            lines.append(f"  Aliases: {aliases}")
            lines.append(f"  {node.description}")
            lines.append("")

        return "\n".join(lines)

    async def close(self):
        """Close HTTP client."""
        if self._http:
            await self._http.aclose()
