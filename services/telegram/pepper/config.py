"""
PEPPER POTTS Configuration

Loads configuration for digital twins, god users, and system settings.
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Set


@dataclass
class NodeConfig:
    """Configuration for a digital twin node."""
    name: str
    url: str
    capabilities: List[str] = None

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []


@dataclass
class PepperConfig:
    """PEPPER POTTS configuration."""
    nodes: Dict[str, NodeConfig]
    god_users: Set[int]
    features: Dict[str, bool]

    def get_node(self, name: str) -> NodeConfig:
        return self.nodes.get(name)


# Mike's Telegram ID
MIKE_USER_ID = 8445149012


def load_config() -> PepperConfig:
    """Load PEPPER POTTS configuration."""

    # Digital Twin nodes
    nodes = {
        "plc_laptop": NodeConfig(
            name="PLC Laptop",
            url="http://100.72.2.99:8765",
            capabilities=["factory_io", "micro820", "modbus", "shell"]
        ),
        "travel_laptop": NodeConfig(
            name="Travel Laptop",
            url="http://100.83.251.23:8765",
            capabilities=["claude_code", "git", "development"]
        ),
        "vps_ultron": NodeConfig(
            name="VPS Ultron",
            url="http://100.68.120.99:8765",
            capabilities=["telegram", "n8n", "orchestration"]
        ),
    }

    # God users (full access)
    god_users = {
        MIKE_USER_ID,  # Mike
    }

    # Feature flags
    features = {
        "voice_tts": True,
        "photo_analysis": False,  # Claude Vision not yet connected
        "voice_input": False,     # Whisper not yet connected
        "equipment_control": True,
        "goal_tracking": True,
    }

    return PepperConfig(
        nodes=nodes,
        god_users=god_users,
        features=features,
    )
