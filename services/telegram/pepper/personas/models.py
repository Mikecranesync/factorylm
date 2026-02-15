"""
Persona data models for PEPPER personality system
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class UserMode(Enum):
    """User access modes determining persona selection"""
    GOD = "god"      # Pepper Prime - Full access for Mike
    DEMO = "demo"    # Pepper - Customer/technician mode with guardrails


@dataclass
class Persona:
    """
    Persona configuration for PEPPER AI behavior

    Attributes:
        mode: User access mode (GOD or DEMO)
        name: Display name of the persona
        soul_content: Complete SOUL.md content defining personality
        greeting: Initial greeting message
        sass_level: 1-10 scale of sarcasm/directness allowed
        formality: 1-10 scale of professional distance
        can_curse: Whether mild profanity is acceptable
        can_challenge: Whether AI can push back on bad ideas
        tools: List of tool categories available to this persona
        guardrails: List of restrictions enforced on this persona
    """
    mode: UserMode
    name: str
    soul_content: str
    greeting: str
    sass_level: int  # 1-10
    formality: int   # 1-10
    can_curse: bool
    can_challenge: bool
    tools: List[str] = field(default_factory=list)
    guardrails: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate persona configuration"""
        if not 1 <= self.sass_level <= 10:
            raise ValueError(f"sass_level must be 1-10, got {self.sass_level}")
        if not 1 <= self.formality <= 10:
            raise ValueError(f"formality must be 1-10, got {self.formality}")
