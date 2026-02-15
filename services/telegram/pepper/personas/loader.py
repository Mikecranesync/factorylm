"""
PersonaLoader - Dynamic persona loading and system prompt generation
"""

from pathlib import Path
from typing import Dict, List, Optional
import logging

from .models import Persona, UserMode


logger = logging.getLogger(__name__)


class PersonaLoader:
    """
    Loads persona configurations from SOUL_*.md files and builds system prompts
    """

    def __init__(self, personas_dir: Optional[Path] = None):
        """
        Initialize PersonaLoader

        Args:
            personas_dir: Directory containing SOUL_*.md files.
                         Defaults to directory containing this file.
        """
        if personas_dir is None:
            personas_dir = Path(__file__).parent
        self.personas_dir = Path(personas_dir)
        self._cache: Dict[UserMode, Persona] = {}

    def load_persona(self, mode: UserMode) -> Persona:
        """
        Load persona configuration for specified mode

        Args:
            mode: UserMode (GOD or DEMO)

        Returns:
            Persona object with full configuration

        Raises:
            FileNotFoundError: If persona file doesn't exist
            ValueError: If persona file is malformed
        """
        # Check cache first
        if mode in self._cache:
            logger.debug(f"Loading persona {mode.value} from cache")
            return self._cache[mode]

        # Map mode to file
        soul_file = self.personas_dir / f"SOUL_{mode.value.upper()}.md"

        if not soul_file.exists():
            raise FileNotFoundError(
                f"Persona file not found: {soul_file}\n"
                f"Available files: {list(self.personas_dir.glob('SOUL_*.md'))}"
            )

        logger.info(f"Loading persona from {soul_file}")

        # Read soul content
        soul_content = soul_file.read_text(encoding="utf-8")

        # Parse persona from content
        persona = self._parse_persona(mode, soul_content)

        # Cache it
        self._cache[mode] = persona

        return persona

    def _parse_persona(self, mode: UserMode, soul_content: str) -> Persona:
        """
        Parse persona attributes from SOUL.md content

        Args:
            mode: UserMode being loaded
            soul_content: Full markdown content of SOUL file

        Returns:
            Persona object
        """
        # Extract metadata from markdown
        # This is a simple parser - could be enhanced with frontmatter library
        lines = soul_content.split("\n")

        # Default values
        name = "Pepper"
        greeting = "Hello! How can I help?"
        sass_level = 5
        formality = 5
        can_curse = False
        can_challenge = False
        tools: List[str] = []
        guardrails: List[str] = []

        # Parse key attributes
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()

            # Extract name (case-insensitive check, case-sensitive split)
            if line_lower.startswith("**name:**"):
                # Use original line for splitting to preserve case
                parts = line.split("**Name:**") if "**Name:**" in line else line.split("**name:**")
                if len(parts) > 1:
                    name = parts[1].strip()

            # Extract greeting
            if line_lower.startswith("**default:**") and i > 0 and "greeting" in lines[i-1].lower():
                parts = line.split("**Default:**") if "**Default:**" in line else line.split("**default:**")
                if len(parts) > 1:
                    greeting = parts[1].strip().strip('"')

            # Extract sass level
            if "**sass level:**" in line_lower:
                try:
                    parts = line.split("**Sass Level:**") if "**Sass Level:**" in line else line.split("**sass level:**")
                    if len(parts) > 1:
                        sass_str = parts[1].strip().split("/")[0].strip()
                        sass_level = int(sass_str)
                except (ValueError, IndexError):
                    logger.warning(f"Could not parse sass_level from: {line}")

            # Extract formality
            if "**formality:**" in line_lower:
                try:
                    parts = line.split("**Formality:**") if "**Formality:**" in line else line.split("**formality:**")
                    if len(parts) > 1:
                        formality_str = parts[1].strip().split("/")[0].strip()
                        formality = int(formality_str)
                except (ValueError, IndexError):
                    logger.warning(f"Could not parse formality from: {line}")

            # Extract can_curse
            if "**can curse:**" in line_lower:
                parts = (line.split("**Can Curse:**") if "**Can Curse:**" in line
                        else line.split("**can curse:**"))
                if len(parts) > 1:
                    can_curse = "yes" in parts[1].lower()

            # Extract can_challenge
            if "**can challenge:**" in line_lower:
                parts = (line.split("**Can Challenge:**") if "**Can Challenge:**" in line
                        else line.split("**can challenge:**"))
                if len(parts) > 1:
                    can_challenge = "yes" in parts[1].lower() or "absolutely" in parts[1].lower()

        # Mode-specific configurations
        if mode == UserMode.GOD:
            tools = [
                "filesystem_read",
                "filesystem_write",
                "shell_execute",
                "plc_read",
                "database_query",
                "ai_layer_3",
                "ai_layer_2",
                "ai_layer_1",
                "ai_layer_0",
                "telegram_send",
                "email_send",
            ]
            guardrails = [
                "no_plc_writes",  # Even God mode respects this
                "confirm_external_comms",
                "confirm_production_deploys",
            ]

        else:  # DEMO mode
            tools = [
                "plc_read",
                "vector_search",
                "ai_layer_0",
                "ai_layer_1",
                "ai_layer_2",
                "manual_search",
                "fault_code_lookup",
            ]
            guardrails = [
                "no_plc_writes",
                "no_filesystem_access",
                "no_shell_execute",
                "no_external_comms",
                "no_user_data_access",
                "no_system_config",
            ]

        return Persona(
            mode=mode,
            name=name,
            soul_content=soul_content,
            greeting=greeting,
            sass_level=sass_level,
            formality=formality,
            can_curse=can_curse,
            can_challenge=can_challenge,
            tools=tools,
            guardrails=guardrails,
        )

    def build_system_prompt(
        self,
        persona: Persona,
        available_tools: Optional[List[str]] = None
    ) -> str:
        """
        Build complete system prompt from persona

        Args:
            persona: Persona configuration
            available_tools: Optional list of tools currently available.
                           Will be filtered against persona.tools.

        Returns:
            Complete system prompt string
        """
        # Filter tools if provided
        if available_tools:
            active_tools = [t for t in available_tools if t in persona.tools]
        else:
            active_tools = persona.tools

        # Build system prompt
        prompt_parts = [
            "# SYSTEM PROMPT",
            "",
            f"**Active Persona:** {persona.name}",
            f"**Mode:** {persona.mode.value.upper()}",
            "",
            "---",
            "",
            persona.soul_content,
            "",
            "---",
            "",
            "# ACTIVE TOOLS",
            "",
            "You have access to the following tools:",
            "",
        ]

        for tool in active_tools:
            prompt_parts.append(f"- {tool}")

        prompt_parts.extend([
            "",
            "# ACTIVE GUARDRAILS",
            "",
            "The following restrictions are enforced:",
            "",
        ])

        for guardrail in persona.guardrails:
            prompt_parts.append(f"- {guardrail}")

        prompt_parts.extend([
            "",
            "---",
            "",
            "**Remember:** Follow the OUTPUT FORMAT LAW. Plain English. No raw JSON unless explicitly requested.",
            "",
        ])

        return "\n".join(prompt_parts)

    def get_greeting(self, mode: UserMode, user_name: Optional[str] = None) -> str:
        """
        Get greeting message for persona

        Args:
            mode: UserMode to get greeting for
            user_name: Optional user name for personalization

        Returns:
            Greeting string
        """
        persona = self.load_persona(mode)

        greeting = persona.greeting

        # Personalize if name provided
        if user_name and "[name]" in greeting:
            greeting = greeting.replace("[name]", user_name)

        return greeting

    def reload_personas(self) -> None:
        """
        Clear cache and force reload of all personas

        Useful for development or if SOUL files are updated
        """
        logger.info("Reloading all personas...")
        self._cache.clear()

    def list_available_personas(self) -> List[str]:
        """
        List all available persona files

        Returns:
            List of persona mode names (e.g., ['GOD', 'DEMO'])
        """
        soul_files = self.personas_dir.glob("SOUL_*.md")
        personas = []

        for soul_file in soul_files:
            # Extract mode from filename (SOUL_GOD.md -> GOD)
            mode_name = soul_file.stem.replace("SOUL_", "")
            personas.append(mode_name)

        return sorted(personas)
