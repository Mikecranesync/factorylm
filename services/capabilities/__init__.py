"""
Unified Capabilities API for FactoryLM Bots
============================================
All bots (PEPPER, FRIDAY, Gus, RemoteMe) share these capabilities.

Usage:
    from services.capabilities import CapabilityClient

    caps = CapabilityClient()

    # Voice
    text = await caps.voice.transcribe(audio_bytes)
    audio = await caps.voice.speak("Hello boss")

    # GitHub
    url = await caps.github.create_gist({"file.md": "content"}, "description")
    issue = await caps.github.create_issue("factorylm", "Bug", "Details...")

    # Memory (RAG)
    results = await caps.memory.query("how did we handle X before?")
    await caps.memory.add("user said X, bot responded Y")

    # Nodes (multi-machine)
    screenshot = await caps.nodes.screenshot("plc-laptop")
    output = await caps.nodes.shell("travel-laptop", "git status")

    # Telemetry
    with caps.telemetry.span("operation_name"):
        ...

    # Photos (vision)
    analysis = await caps.photos.analyze(image_bytes, "what equipment is this?")

    # Factory (PLC diagnosis)
    diagnosis = await caps.factory.diagnose("why is conveyor stopped?")
"""

from .memory import MemoryCapability
from .github import GitHubCapability
from .voice import VoiceCapability
from .nodes import NodesCapability
from .telemetry import TelemetryCapability
from .photos import PhotosCapability
from .factory import FactoryCapability


class CapabilityClient:
    """Unified client for all bot capabilities."""

    def __init__(self):
        self.memory = MemoryCapability()
        self.github = GitHubCapability()
        self.voice = VoiceCapability()
        self.nodes = NodesCapability()
        self.telemetry = TelemetryCapability()
        self.photos = PhotosCapability()
        self.factory = FactoryCapability()

    async def health_check(self) -> dict:
        """Check health of all capabilities."""
        return {
            "memory": await self.memory.health(),
            "github": await self.github.health(),
            "voice": await self.voice.health(),
            "nodes": await self.nodes.health(),
            "telemetry": self.telemetry.health(),
            "photos": await self.photos.health(),
            "factory": await self.factory.health(),
        }


# Singleton for easy import
_client: CapabilityClient = None


def get_capabilities() -> CapabilityClient:
    """Get the shared capability client."""
    global _client
    if _client is None:
        _client = CapabilityClient()
    return _client


__all__ = [
    "CapabilityClient",
    "get_capabilities",
    "MemoryCapability",
    "GitHubCapability",
    "VoiceCapability",
    "NodesCapability",
    "TelemetryCapability",
    "PhotosCapability",
    "FactoryCapability",
]
