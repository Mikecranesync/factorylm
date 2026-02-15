"""
ResponseFormatter - Enforce OUTPUT FORMAT LAW for all personas
"""

import json
import re
from typing import Any, Dict, Optional
import logging

from .models import UserMode, Persona


logger = logging.getLogger(__name__)


class ResponseFormatter:
    """
    Enforces OUTPUT FORMAT LAW:
    - No raw JSON (unless explicitly requested)
    - Plain English an 11-year-old can understand
    - Simple ✅ or ❌ indicators
    - Strip technical jargon in Demo mode
    """

    def __init__(self, persona: Persona):
        """
        Initialize formatter for specific persona

        Args:
            persona: Active persona configuration
        """
        self.persona = persona

    def format_response(
        self,
        content: str,
        allow_technical: bool = False
    ) -> str:
        """
        Format response according to OUTPUT FORMAT LAW

        Args:
            content: Raw response content
            allow_technical: Override for God mode when technical output requested

        Returns:
            Formatted response suitable for user
        """
        # God mode can override if technical output explicitly requested
        if self.persona.mode == UserMode.GOD and allow_technical:
            return content

        # Clean up JSON leakage
        content = self._strip_raw_json(content)

        # Simplify technical jargon in Demo mode
        if self.persona.mode == UserMode.DEMO:
            content = self._simplify_jargon(content)

        # Ensure readable formatting
        content = self._ensure_readability(content)

        return content

    def _strip_raw_json(self, content: str) -> str:
        """
        Remove raw JSON from response and replace with plain English

        Args:
            content: Response content

        Returns:
            Content with JSON removed or simplified
        """
        # Pattern to detect JSON blocks
        json_pattern = r'```json\s*(.*?)\s*```'
        json_inline_pattern = r'\{["\w\s:,\[\]{}]+\}'

        # Find JSON blocks
        json_blocks = re.finditer(json_pattern, content, re.DOTALL)

        for match in json_blocks:
            json_str = match.group(1)
            try:
                # Parse JSON and convert to plain English
                data = json.loads(json_str)
                plain_text = self._json_to_plain_english(data)
                content = content.replace(match.group(0), plain_text)
            except json.JSONDecodeError:
                # If can't parse, just remove the code block
                logger.warning(f"Could not parse JSON block: {json_str[:100]}")
                content = content.replace(match.group(0), "[Technical data removed]")

        # Also check for inline JSON
        inline_matches = re.finditer(json_inline_pattern, content)
        for match in inline_matches:
            # Only replace if it looks like raw data dump, not part of explanation
            if match.group(0).count(":") > 2:  # Heuristic: multiple key-value pairs
                content = content.replace(match.group(0), "[data]")

        return content

    def _json_to_plain_english(self, data: Any, depth: int = 0) -> str:
        """
        Convert JSON structure to plain English

        Args:
            data: Parsed JSON data
            depth: Current nesting depth

        Returns:
            Plain English representation
        """
        if isinstance(data, dict):
            parts = []
            for key, value in data.items():
                # Convert snake_case to Title Case
                readable_key = key.replace("_", " ").title()

                if isinstance(value, (dict, list)):
                    nested = self._json_to_plain_english(value, depth + 1)
                    parts.append(f"**{readable_key}:** {nested}")
                else:
                    parts.append(f"**{readable_key}:** {value}")

            indent = "  " * depth
            return "\n".join(f"{indent}{part}" for part in parts)

        elif isinstance(data, list):
            if not data:
                return "None"
            if len(data) == 1:
                return str(data[0])
            # For lists, use bullet points
            items = [f"• {item}" for item in data]
            return "\n".join(items)

        else:
            return str(data)

    def _simplify_jargon(self, content: str) -> str:
        """
        Replace technical jargon with plain language (Demo mode)

        Args:
            content: Response content

        Returns:
            Simplified content
        """
        # Common technical terms and their plain English equivalents
        replacements = {
            r'\bAPI\b': 'interface',
            r'\bREST\b': 'web service',
            r'\bJSON\b': 'data',
            r'\bSQL\b': 'database query',
            r'\bGET/POST\b': 'request',
            r'\bHTTP\s*\d{3}\b': 'error code',
            r'\bSSL/TLS\b': 'security',
            r'\bUUID\b': 'ID',
            r'\btimestamp\b': 'time',
            r'\blatency\b': 'delay',
            r'\bthroughput\b': 'speed',
            r'\bstack trace\b': 'error details',
            # Keep these technical terms in Demo mode:
            # PLC, motor, sensor, conveyor, pump, valve (equipment terms)
        }

        for pattern, replacement in replacements.items():
            content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)

        return content

    def _ensure_readability(self, content: str) -> str:
        """
        Ensure content is formatted for readability

        Args:
            content: Response content

        Returns:
            Readable content with proper formatting
        """
        # Remove excessive newlines (more than 2 in a row)
        content = re.sub(r'\n{3,}', '\n\n', content)

        # Ensure proper spacing around headers
        content = re.sub(r'(#+\s+.+)\n([^\n])', r'\1\n\n\2', content)

        # Remove trailing whitespace
        content = "\n".join(line.rstrip() for line in content.split("\n"))

        return content.strip()

    def format_status_indicator(self, success: bool, message: str = "") -> str:
        """
        Create simple status indicator

        Args:
            success: Whether operation succeeded
            message: Optional message to append

        Returns:
            Formatted status string
        """
        indicator = "✅" if success else "❌"

        if message:
            return f"{indicator} {message}"
        else:
            return f"{indicator} {'Success' if success else 'Failed'}"

    def format_equipment_status(
        self,
        equipment_name: str,
        status: Dict[str, Any]
    ) -> str:
        """
        Format equipment status for display

        Args:
            equipment_name: Name/ID of equipment
            status: Status data dictionary

        Returns:
            Formatted equipment status
        """
        lines = [f"**{equipment_name}**"]

        # Common status fields
        if "running" in status:
            indicator = "✅ Running" if status["running"] else "❌ Stopped"
            lines.append(indicator)

        if "current" in status:
            lines.append(f"Current: {status['current']}A")

        if "temperature" in status:
            lines.append(f"Temperature: {status['temperature']}°C")

        if "fault_code" in status and status["fault_code"]:
            lines.append(f"⚠️ Fault: {status['fault_code']}")

        if "last_maintenance" in status:
            lines.append(f"Last Maintenance: {status['last_maintenance']}")

        # Any other fields as key: value
        displayed = {"running", "current", "temperature", "fault_code", "last_maintenance"}
        for key, value in status.items():
            if key not in displayed:
                readable_key = key.replace("_", " ").title()
                lines.append(f"{readable_key}: {value}")

        return "\n".join(lines)

    def format_fault_code(
        self,
        code: str,
        description: str,
        causes: list,
        actions: list
    ) -> str:
        """
        Format fault code information

        Args:
            code: Fault code (e.g., "E-47")
            description: What the fault means
            causes: List of common causes
            actions: List of troubleshooting actions

        Returns:
            Formatted fault code explanation
        """
        lines = [
            f"**Fault Code: {code}**",
            "",
            description,
            "",
        ]

        if causes:
            lines.append("**Common causes:**")
            for cause in causes:
                lines.append(f"• {cause}")
            lines.append("")

        if actions:
            lines.append("**What to check:**")
            for i, action in enumerate(actions, 1):
                lines.append(f"{i}. {action}")

        return "\n".join(lines)

    def format_procedure_steps(
        self,
        procedure_name: str,
        steps: list,
        safety_notes: Optional[list] = None
    ) -> str:
        """
        Format maintenance or troubleshooting procedure

        Args:
            procedure_name: Name of the procedure
            steps: List of step descriptions
            safety_notes: Optional safety warnings

        Returns:
            Formatted procedure
        """
        lines = [
            f"**{procedure_name}**",
            "",
        ]

        if safety_notes:
            lines.append("⚠️ **Safety:**")
            for note in safety_notes:
                lines.append(f"• {note}")
            lines.append("")

        lines.append("**Steps:**")
        for i, step in enumerate(steps, 1):
            lines.append(f"{i}. {step}")

        return "\n".join(lines)

    def truncate_if_too_long(
        self,
        content: str,
        max_length: int = 4000
    ) -> str:
        """
        Truncate content if it exceeds maximum length (for Telegram limits)

        Args:
            content: Response content
            max_length: Maximum allowed length

        Returns:
            Possibly truncated content
        """
        if len(content) <= max_length:
            return content

        # Truncate and add indicator
        truncated = content[:max_length - 100]

        # Try to truncate at a paragraph break
        last_break = truncated.rfind("\n\n")
        if last_break > max_length * 0.8:  # If we can keep at least 80%
            truncated = truncated[:last_break]

        truncated += "\n\n...\n\n[Message truncated. Want me to break this into sections?]"

        return truncated

    def should_allow_technical(self, user_request: str) -> bool:
        """
        Determine if user explicitly requested technical output

        Args:
            user_request: User's message

        Returns:
            True if technical output is explicitly requested
        """
        if self.persona.mode != UserMode.GOD:
            return False

        # Keywords that indicate technical output wanted
        technical_keywords = [
            "show me the json",
            "dump the",
            "raw data",
            "debug output",
            "stack trace",
            "full log",
            "complete output",
            "technical details",
        ]

        request_lower = user_request.lower()
        return any(keyword in request_lower for keyword in technical_keywords)
