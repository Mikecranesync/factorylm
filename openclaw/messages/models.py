"""Canonical message types for the OpenClaw pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openclaw.types import Channel


@dataclass
class InboundMessage:
    """A message received from any channel (Telegram, Gist, etc.)."""

    id: str
    channel: Channel
    user_id: str
    user_name: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OutboundMessage:
    """A message to send back through a channel."""

    channel: Channel
    user_id: str
    text: str
    attachments: list[Attachment] = field(default_factory=list)


@dataclass
class Attachment:
    """File attachment on an outbound message."""

    filename: str
    data: bytes
    mime_type: str = "application/octet-stream"
