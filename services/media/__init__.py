"""
FactoryLM Media Pipeline
========================
Collects, syncs, and processes media from all field devices.

Components:
- MediaOffloadAgent: Syncs media from devices to Google Drive
- TelegramMediaHandler: Captures media sent to Gus bot
- multi_image_assembler: Creates YouTube Shorts from multiple images

Usage:
    from services.media import MediaOffloadAgent, TelegramMediaHandler
    from services.media.multi_image_assembler import assemble_shorts_video
"""

from .media_offload_agent import MediaOffloadAgent
from .telegram_media_handler import TelegramMediaHandler
from .multi_image_assembler import (
    assemble_shorts_video,
    assemble_multi_image_video,
    VideoAssemblyError,
    check_ffmpeg_installed
)

__all__ = [
    "MediaOffloadAgent",
    "TelegramMediaHandler",
    "assemble_shorts_video",
    "assemble_multi_image_video",
    "VideoAssemblyError",
    "check_ffmpeg_installed"
]
