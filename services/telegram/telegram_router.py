"""
Telegram Router - Multi-Node Routing Layer
===========================================
Routes commands from Telegram bots to the appropriate Jarvis node.
Supports:
- Per-chat node selection (/on plc, /on travel)
- Inline prefixes (/plc show me IO, /travel git status)
- Sticky node state per chat
- Health checks and node discovery

Usage:
    from telegram_router import NodeRouter

    router = NodeRouter()
    node = router.get_node_for_chat(chat_id)
    result = await router.execute(chat_id, "ls -la")
"""

import os
import json
import httpx
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
import yaml
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

CONFIG_PATH = Path(__file__).parent / "nodes_config.yaml"
DEFAULT_TIMEOUT = 30


@dataclass
class Node:
    """Represents a Jarvis node."""
    id: str
    aliases: List[str]
    url: str
    name: str
    description: str
    capabilities: List[str]
    matrix_api: Optional[str] = None
    _online: Optional[bool] = None
    _last_check: float = 0


@dataclass
class RouterConfig:
    """Router configuration."""
    nodes: Dict[str, Node] = field(default_factory=dict)
    default_node: str = "plc"
    state_file: str = "/tmp/telegram_router_state.json"
    alias_map: Dict[str, str] = field(default_factory=dict)  # alias -> node_id


def load_config() -> RouterConfig:
    """Load configuration from YAML file."""
    config = RouterConfig()

    if not CONFIG_PATH.exists():
        logger.warning(f"Config not found at {CONFIG_PATH}, using defaults")
        # Fallback defaults
        config.nodes["plc"] = Node(
            id="plc",
            aliases=["plc", "factory"],
            url="http://100.72.2.99:8765",
            name="PLC Laptop",
            description="Factory I/O + Micro 820",
            capabilities=["shell", "files"],
            matrix_api="http://100.72.2.99:8000"
        )
        config.nodes["travel"] = Node(
            id="travel",
            aliases=["travel", "dev"],
            url="http://100.83.251.23:8765",
            name="Travel Laptop",
            description="Development",
            capabilities=["shell", "files"]
        )
        config.alias_map = {"plc": "plc", "factory": "plc", "travel": "travel", "dev": "travel"}
        return config

    with open(CONFIG_PATH) as f:
        data = yaml.safe_load(f)

    for node_id, node_data in data.get("nodes", {}).items():
        node = Node(
            id=node_id,
            aliases=node_data.get("alias", [node_id]),
            url=node_data["url"],
            name=node_data.get("name", node_id),
            description=node_data.get("description", ""),
            capabilities=node_data.get("capabilities", []),
            matrix_api=node_data.get("matrix_api")
        )
        config.nodes[node_id] = node
        # Build alias map
        for alias in node.aliases:
            config.alias_map[alias.lower()] = node_id

    config.default_node = data.get("default_node", "plc")
    config.state_file = data.get("state_file", "/tmp/telegram_router_state.json")

    return config


# ============================================================================
# Chat State Management
# ============================================================================

class ChatState:
    """Manages per-chat node selection state."""

    def __init__(self, state_file: str):
        self.state_file = Path(state_file)
        self._state: Dict[str, str] = {}  # chat_id -> node_id
        self._load()

    def _load(self):
        """Load state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    self._state = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")
                self._state = {}

    def _save(self):
        """Save state to file."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(self._state, f)
        except Exception as e:
            logger.warning(f"Failed to save state: {e}")

    def get(self, chat_id: int, default: str = None) -> Optional[str]:
        """Get node for chat."""
        return self._state.get(str(chat_id), default)

    def set(self, chat_id: int, node_id: str):
        """Set node for chat."""
        self._state[str(chat_id)] = node_id
        self._save()

    def clear(self, chat_id: int):
        """Clear node for chat."""
        self._state.pop(str(chat_id), None)
        self._save()


# ============================================================================
# Node Router
# ============================================================================

class NodeRouter:
    """Main router class for multi-node command routing."""

    def __init__(self, config: RouterConfig = None):
        self.config = config or load_config()
        self.state = ChatState(self.config.state_file)
        self.http = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)

    async def close(self):
        """Close HTTP client."""
        await self.http.aclose()

    # ========================================================================
    # Node Resolution
    # ========================================================================

    def resolve_node(self, alias: str) -> Optional[Node]:
        """Resolve alias to node."""
        node_id = self.config.alias_map.get(alias.lower())
        if node_id:
            return self.config.nodes.get(node_id)
        return None

    def get_node_for_chat(self, chat_id: int) -> Node:
        """Get the active node for a chat."""
        node_id = self.state.get(chat_id, self.config.default_node)
        return self.config.nodes.get(node_id, self.config.nodes[self.config.default_node])

    def set_node_for_chat(self, chat_id: int, alias: str) -> Tuple[bool, str]:
        """
        Set the active node for a chat.
        Returns (success, message).
        """
        node = self.resolve_node(alias)
        if not node:
            available = ", ".join(self.config.alias_map.keys())
            return False, f"Unknown node '{alias}'. Available: {available}"

        self.state.set(chat_id, node.id)
        return True, f"Switched to **{node.name}** ({node.url})"

    def parse_inline_prefix(self, text: str) -> Tuple[Optional[str], str]:
        """
        Parse inline prefix from command.
        Example: "/plc ls -la" -> ("plc", "ls -la")
        Example: "/travel git status" -> ("travel", "git status")
        Example: "ls -la" -> (None, "ls -la")
        """
        if not text.startswith("/"):
            return None, text

        parts = text.split(None, 1)
        if not parts:
            return None, text

        potential_alias = parts[0][1:].lower()  # Remove leading /
        if potential_alias in self.config.alias_map:
            remainder = parts[1] if len(parts) > 1 else ""
            return potential_alias, remainder

        return None, text

    # ========================================================================
    # Command Execution
    # ========================================================================

    async def execute_shell(
        self,
        chat_id: int,
        command: str,
        node_override: str = None,
        timeout: int = 30,
        cwd: str = None
    ) -> Dict[str, Any]:
        """
        Execute a shell command on the appropriate node.

        Args:
            chat_id: Telegram chat ID
            command: Shell command to execute
            node_override: Optional node alias to override chat state
            timeout: Command timeout in seconds
            cwd: Working directory

        Returns:
            {"success": bool, "stdout": str, "stderr": str, "exit_code": int, "node": str}
        """
        # Determine target node
        if node_override:
            node = self.resolve_node(node_override)
            if not node:
                return {"success": False, "error": f"Unknown node: {node_override}"}
        else:
            node = self.get_node_for_chat(chat_id)

        # Execute on node
        try:
            resp = await self.http.post(
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

        except httpx.TimeoutException:
            return {"success": False, "error": f"Timeout connecting to {node.name}", "node": node.name}
        except Exception as e:
            return {"success": False, "error": str(e), "node": node.name}

    async def read_file(self, chat_id: int, path: str, node_override: str = None) -> Dict[str, Any]:
        """Read a file from a node."""
        node = self.resolve_node(node_override) if node_override else self.get_node_for_chat(chat_id)

        try:
            resp = await self.http.post(f"{node.url}/files/read", json={"path": path})
            if resp.status_code == 200:
                data = resp.json()
                return {"success": True, "content": data.get("content", ""), "node": node.name}
            else:
                return {"success": False, "error": f"HTTP {resp.status_code}", "node": node.name}
        except Exception as e:
            return {"success": False, "error": str(e), "node": node.name}

    async def get_screenshot(self, chat_id: int, node_override: str = None) -> Dict[str, Any]:
        """Get screenshot from a node."""
        node = self.resolve_node(node_override) if node_override else self.get_node_for_chat(chat_id)

        try:
            resp = await self.http.get(f"{node.url}/screenshot")
            if resp.status_code == 200:
                data = resp.json()
                return {"success": True, "image_base64": data.get("image_base64", ""), "node": node.name}
            else:
                return {"success": False, "error": f"HTTP {resp.status_code}", "node": node.name}
        except Exception as e:
            return {"success": False, "error": str(e), "node": node.name}

    # ========================================================================
    # Health Checks
    # ========================================================================

    async def check_node_health(self, node: Node) -> Dict[str, Any]:
        """Check if a node is online."""
        try:
            resp = await self.http.get(f"{node.url}/health", timeout=5)
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

    async def check_all_nodes(self) -> Dict[str, Dict[str, Any]]:
        """Check health of all nodes."""
        results = {}
        tasks = []

        for node_id, node in self.config.nodes.items():
            tasks.append(self.check_node_health(node))

        health_results = await asyncio.gather(*tasks, return_exceptions=True)

        for (node_id, node), health in zip(self.config.nodes.items(), health_results):
            if isinstance(health, Exception):
                results[node_id] = {"online": False, "error": str(health), "name": node.name}
            else:
                results[node_id] = {**health, "name": node.name, "url": node.url}

        return results

    # ========================================================================
    # Info Methods
    # ========================================================================

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
            for node in self.config.nodes.values()
        ]

    def format_nodes_message(self) -> str:
        """Format nodes list for Telegram message."""
        lines = ["**Available Nodes**", "=" * 20, ""]

        for node in self.config.nodes.values():
            aliases = ", ".join(node.aliases)
            lines.append(f"**{node.name}** (`{node.id}`)")
            lines.append(f"  URL: {node.url}")
            lines.append(f"  Aliases: {aliases}")
            lines.append(f"  {node.description}")
            lines.append("")

        lines.append("Usage:")
        lines.append("  `/on plc` — Switch to PLC laptop")
        lines.append("  `/plc ls` — One-off command on PLC")
        lines.append("  `/nodes` — Show this list")

        return "\n".join(lines)


# ============================================================================
# Singleton Instance
# ============================================================================

_router_instance: Optional[NodeRouter] = None


def get_router() -> NodeRouter:
    """Get or create the singleton router instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = NodeRouter()
    return _router_instance


# ============================================================================
# Test / Demo
# ============================================================================

async def main():
    """Demo the router."""
    router = NodeRouter()

    print("Configured nodes:")
    for node in router.list_nodes():
        print(f"  {node['id']}: {node['name']} @ {node['url']}")

    print("\nChecking node health...")
    health = await router.check_all_nodes()
    for node_id, status in health.items():
        online = "ONLINE" if status.get("online") else "OFFLINE"
        print(f"  {node_id}: {online}")

    await router.close()


if __name__ == "__main__":
    asyncio.run(main())
