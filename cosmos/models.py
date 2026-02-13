"""Data models for FactoryLM Cosmos integration."""

import dataclasses
import datetime


@dataclasses.dataclass
class CosmosInsight:
    """Result of a Cosmos Reason 2 analysis for a single incident."""

    incident_id: str
    node_id: str
    timestamp: datetime.datetime
    summary: str = ""
    root_cause: str = ""
    confidence: float = 0.0
    reasoning: str = ""
    suggested_checks: list[str] = dataclasses.field(default_factory=list)
    video_url: str = ""
    tag_window_seconds: int = 60
    cosmos_model: str = "nvidia/cosmos-reason2"
