"""
PEPPER Layer 0: Knowledge Base

Deterministic pattern matching for common queries.
Fastest layer - no LLM calls needed.

THE GOAL: Convert Layer 3 answers into Layer 0 patterns over time.
"""

import re
import logging
from typing import Optional, Any
from dataclasses import dataclass
from pathlib import Path


logger = logging.getLogger(__name__)


@dataclass
class KBResult:
    """Result from knowledge base lookup."""
    pattern: str
    response: str
    confidence: float
    category: str


# Built-in patterns for factory operations
BUILTIN_PATTERNS = [
    # Greetings
    {
        "patterns": [r"^(hi|hello|hey|sup|yo)$", r"^good (morning|afternoon|evening)"],
        "response": "Hey! How can I help with the factory today?",
        "confidence": 1.0,
        "category": "greeting"
    },

    # Status queries
    {
        "patterns": [r"(status|how is|what's happening|what is happening)"],
        "response": "I'll check the current system status for you.",
        "confidence": 0.6,  # Low confidence - should route to LLM for details
        "category": "status"
    },

    # Help
    {
        "patterns": [r"^(help|commands|\?)$", r"what can you do"],
        "response": """I can help you with:
• **Equipment Status** - Check conveyor, sensors, PLC
• **Fault Diagnosis** - "Why did the conveyor stop?"
• **Work Orders** - Create and track maintenance tasks
• **Procedures** - Find maintenance procedures

Just ask me naturally - I understand factory talk!""",
        "confidence": 1.0,
        "category": "help"
    },

    # Emergency stop
    {
        "patterns": [r"emergency|e[\-\s]?stop|stop all|shut down|shutdown"],
        "response": "⚠️ For EMERGENCY STOPS, use the physical E-Stop button on the equipment. I cannot remotely trigger emergency stops for safety reasons.",
        "confidence": 1.0,
        "category": "safety"
    },

    # Thanks
    {
        "patterns": [r"^(thanks|thank you|thx|ty|cheers)"],
        "response": "You're welcome! Let me know if you need anything else.",
        "confidence": 1.0,
        "category": "thanks"
    },

    # Conveyor quick status
    {
        "patterns": [r"conveyor (running|on|moving)\??"],
        "response": "Let me check the conveyor status...",
        "confidence": 0.5,  # Route to equipment check
        "category": "equipment"
    },

    # Fault codes
    {
        "patterns": [r"(fault|error|alarm) code (\d+)", r"code (\d+)"],
        "response": "Let me look up that fault code...",
        "confidence": 0.5,  # Route to diagnosis
        "category": "fault"
    },
]


class KnowledgeBase:
    """
    Knowledge base for deterministic responses.

    Supports:
    - Built-in patterns for common factory queries
    - Custom patterns from YAML files
    - Pattern matching with confidence scoring
    """

    def __init__(self, kb_path: Optional[str] = None):
        """
        Initialize knowledge base.

        Args:
            kb_path: Optional path to custom KB patterns
        """
        self.patterns = BUILTIN_PATTERNS.copy()
        self.kb_path = Path(kb_path) if kb_path else None

        # Load custom patterns if provided
        if self.kb_path and self.kb_path.exists():
            self._load_custom_patterns()

        # Compile regex patterns
        self._compile_patterns()

        logger.info(f"KnowledgeBase initialized with {len(self.patterns)} patterns")

    def _compile_patterns(self):
        """Compile regex patterns for faster matching."""
        for entry in self.patterns:
            entry["compiled"] = [
                re.compile(p, re.IGNORECASE)
                for p in entry["patterns"]
            ]

    def _load_custom_patterns(self):
        """Load custom patterns from YAML file."""
        try:
            import yaml

            kb_file = self.kb_path / "patterns.yaml"
            if kb_file.exists():
                with open(kb_file) as f:
                    custom = yaml.safe_load(f)
                    if custom and "patterns" in custom:
                        self.patterns.extend(custom["patterns"])
                        logger.info(f"Loaded {len(custom['patterns'])} custom patterns")
        except Exception as e:
            logger.error(f"Failed to load custom patterns: {e}")

    async def lookup(
        self,
        query: str,
        context: Optional[dict[str, Any]] = None
    ) -> Optional[KBResult]:
        """
        Look up query in knowledge base.

        Args:
            query: User query to match
            context: Optional context for dynamic responses

        Returns:
            KBResult if match found with sufficient confidence
        """
        query = query.strip().lower()

        best_match: Optional[KBResult] = None
        best_confidence = 0.0

        for entry in self.patterns:
            for pattern in entry.get("compiled", []):
                match = pattern.search(query)
                if match:
                    confidence = entry["confidence"]

                    # Boost confidence for exact matches
                    if pattern.fullmatch(query):
                        confidence = min(1.0, confidence + 0.2)

                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = KBResult(
                            pattern=pattern.pattern,
                            response=self._format_response(
                                entry["response"],
                                match,
                                context
                            ),
                            confidence=confidence,
                            category=entry.get("category", "general")
                        )

        return best_match

    def _format_response(
        self,
        response: str,
        match: re.Match,
        context: Optional[dict[str, Any]]
    ) -> str:
        """Format response with captured groups and context."""
        # Replace captured groups
        for i, group in enumerate(match.groups()):
            if group:
                response = response.replace(f"${i+1}", group)

        # Replace context variables
        if context:
            for key, value in context.items():
                response = response.replace(f"{{{key}}}", str(value))

        return response

    def add_pattern(
        self,
        patterns: list[str],
        response: str,
        confidence: float = 0.9,
        category: str = "custom"
    ):
        """
        Add a new pattern to the knowledge base.

        This is how Layer 3 answers get converted to Layer 0!

        Args:
            patterns: List of regex patterns to match
            response: Response template
            confidence: Confidence level (0-1)
            category: Pattern category
        """
        entry = {
            "patterns": patterns,
            "response": response,
            "confidence": confidence,
            "category": category,
            "compiled": [re.compile(p, re.IGNORECASE) for p in patterns]
        }
        self.patterns.append(entry)
        logger.info(f"Added pattern: {patterns[0][:50]}...")

    def save_patterns(self):
        """Save current patterns to file for persistence."""
        if not self.kb_path:
            logger.warning("No kb_path configured, cannot save patterns")
            return

        try:
            import yaml

            self.kb_path.mkdir(parents=True, exist_ok=True)
            kb_file = self.kb_path / "patterns.yaml"

            # Export patterns (without compiled regex)
            export = []
            for entry in self.patterns:
                export.append({
                    "patterns": entry["patterns"],
                    "response": entry["response"],
                    "confidence": entry["confidence"],
                    "category": entry.get("category", "general")
                })

            with open(kb_file, "w") as f:
                yaml.dump({"patterns": export}, f, default_flow_style=False)

            logger.info(f"Saved {len(export)} patterns to {kb_file}")

        except Exception as e:
            logger.error(f"Failed to save patterns: {e}")
