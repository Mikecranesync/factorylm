#!/usr/bin/env python3
"""
Telegram Media Handler
======================
Captures photos, videos, and documents sent to Gus bot.
Saves to local inbox with metadata for downstream processing.

Usage:
    # In factorylm_bot.py, add:
    from services.media import TelegramMediaHandler
    media_handler = TelegramMediaHandler()

    # Register handler:
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL,
                                   media_handler.handle_media))
"""

import os
import json
import base64
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class TelegramMediaHandler:
    """
    Handles media files sent to Telegram bot.

    Saves files to:
        ~/.openclaw/media-inbox/telegram/<date>/<filename>

    Creates metadata sidecar:
        ~/.openclaw/media-inbox/telegram/<date>/<filename>.json
    """

    def __init__(self, inbox_dir: Optional[str] = None):
        """Initialize media handler."""
        if inbox_dir:
            self.inbox_dir = Path(inbox_dir)
        else:
            self.inbox_dir = Path.home() / ".openclaw" / "media-inbox" / "telegram"

        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Media inbox: {self.inbox_dir}")

        # Track session for grouping related media
        self.current_session_id = None
        self.session_start_time = None

    def _get_date_folder(self) -> Path:
        """Get or create today's folder."""
        today = datetime.now().strftime("%Y-%m-%d")
        folder = self.inbox_dir / today
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _generate_filename(self, original_name: str, file_type: str, user: str) -> str:
        """Generate timestamped filename."""
        timestamp = datetime.now().strftime("%H%M%S")
        ext = Path(original_name).suffix if original_name else f".{file_type}"
        safe_user = "".join(c for c in user if c.isalnum())[:10]
        return f"{timestamp}_{safe_user}{ext}"

    async def handle_media(self, update, context) -> Dict[str, Any]:
        """
        Handle incoming media message.

        Supports:
        - Photos (gets highest resolution)
        - Videos
        - Documents (PDFs, images, etc.)

        Returns:
            dict with saved file info and metadata
        """
        message = update.message
        user = update.effective_user
        caption = message.caption or ""

        result = {
            "success": False,
            "file_path": None,
            "metadata_path": None,
            "error": None
        }

        try:
            # Determine file type and get file_id
            if message.photo:
                # Get highest resolution photo
                photo = message.photo[-1]
                file_id = photo.file_id
                file_type = "jpg"
                media_type = "photo"
                original_name = f"photo_{photo.file_unique_id}.jpg"
            elif message.video:
                video = message.video
                file_id = video.file_id
                file_type = "mp4"
                media_type = "video"
                original_name = video.file_name or f"video_{video.file_unique_id}.mp4"
            elif message.document:
                doc = message.document
                file_id = doc.file_id
                file_type = Path(doc.file_name).suffix.lstrip('.') if doc.file_name else "bin"
                media_type = "document"
                original_name = doc.file_name or f"doc_{doc.file_unique_id}"
            else:
                result["error"] = "No supported media found"
                return result

            # Download file from Telegram
            file = await context.bot.get_file(file_id)
            file_bytes = await file.download_as_bytearray()

            # Generate paths
            date_folder = self._get_date_folder()
            username = user.username or user.first_name or str(user.id)
            filename = self._generate_filename(original_name, file_type, username)
            file_path = date_folder / filename
            metadata_path = date_folder / f"{filename}.json"

            # Save file
            file_path.write_bytes(file_bytes)

            # Create metadata
            metadata = {
                "timestamp": datetime.now().isoformat(),
                "user_id": user.id,
                "username": username,
                "chat_id": update.effective_chat.id,
                "media_type": media_type,
                "original_name": original_name,
                "caption": caption,
                "file_size_bytes": len(file_bytes),
                "telegram_file_id": file_id,
                "session_id": self.current_session_id,
                "source": "telegram",
                "processed": False,
                "synced_to_gdrive": False
            }

            # Add type-specific metadata
            if message.photo:
                photo = message.photo[-1]
                metadata["dimensions"] = {"width": photo.width, "height": photo.height}
            elif message.video:
                metadata["duration_seconds"] = message.video.duration
                metadata["dimensions"] = {"width": message.video.width, "height": message.video.height}

            # Save metadata
            metadata_path.write_text(json.dumps(metadata, indent=2))

            result["success"] = True
            result["file_path"] = str(file_path)
            result["metadata_path"] = str(metadata_path)
            result["metadata"] = metadata

            logger.info(f"Saved media: {file_path.name} ({len(file_bytes)} bytes)")

            # Send confirmation
            size_kb = len(file_bytes) / 1024
            response = f"📸 Got it! Saved {media_type} ({size_kb:.1f} KB)"
            if caption:
                response += f"\nCaption: \"{caption[:50]}{'...' if len(caption) > 50 else ''}\""
            response += "\n\nThis will be synced to Google Drive and available for content production."

            await update.message.reply_text(response)

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Failed to save media: {e}")
            await update.message.reply_text(f"⚠️ Couldn't save that file: {e}")

        return result

    def start_session(self, session_name: Optional[str] = None) -> str:
        """Start a new capture session (groups related media)."""
        self.current_session_id = session_name or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_start_time = datetime.now()
        logger.info(f"Started media session: {self.current_session_id}")
        return self.current_session_id

    def end_session(self) -> Dict[str, Any]:
        """End current session and return summary."""
        if not self.current_session_id:
            return {"error": "No active session"}

        # Count files in session
        session_files = []
        for date_folder in self.inbox_dir.iterdir():
            if date_folder.is_dir():
                for meta_file in date_folder.glob("*.json"):
                    try:
                        meta = json.loads(meta_file.read_text())
                        if meta.get("session_id") == self.current_session_id:
                            session_files.append(meta)
                    except:
                        pass

        summary = {
            "session_id": self.current_session_id,
            "start_time": self.session_start_time.isoformat() if self.session_start_time else None,
            "end_time": datetime.now().isoformat(),
            "file_count": len(session_files),
            "files": session_files
        }

        self.current_session_id = None
        self.session_start_time = None

        return summary

    def get_unsynced_files(self) -> list:
        """Get list of files not yet synced to Google Drive."""
        unsynced = []

        for date_folder in self.inbox_dir.iterdir():
            if date_folder.is_dir():
                for meta_file in date_folder.glob("*.json"):
                    try:
                        meta = json.loads(meta_file.read_text())
                        if not meta.get("synced_to_gdrive"):
                            file_path = meta_file.with_suffix("")  # Remove .json
                            if file_path.exists():
                                unsynced.append({
                                    "file_path": str(file_path),
                                    "metadata_path": str(meta_file),
                                    "metadata": meta
                                })
                    except:
                        pass

        return unsynced

    def mark_synced(self, metadata_path: str):
        """Mark a file as synced to Google Drive."""
        meta_path = Path(metadata_path)
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            meta["synced_to_gdrive"] = True
            meta["synced_at"] = datetime.now().isoformat()
            meta_path.write_text(json.dumps(meta, indent=2))


# Standalone test
if __name__ == "__main__":
    handler = TelegramMediaHandler()
    print(f"Inbox: {handler.inbox_dir}")
    print(f"Unsynced files: {len(handler.get_unsynced_files())}")
