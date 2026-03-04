"""Data models for the troubleshooting engine."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class SessionState:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    workflow_id: str | None = None
    node_id: str | None = None
    data: dict = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    photos: list[str] = field(default_factory=list)
    path: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def add_event(self, event_type: str, **kwargs) -> None:
        self.events.append({"type": event_type, "ts": time.time(), **kwargs})
        self.updated_at = time.time()


@dataclass
class EngineResponse:
    message_text: str
    buttons: list[dict] = field(default_factory=list)
    expecting: str = "done"  # "text" | "button" | "photo" | "done"
    attachments: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
