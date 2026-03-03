"""Telegram channel adapter — polling-based bot."""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from collections import defaultdict
from typing import Callable, Awaitable

import httpx

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, MessageHandler, CommandHandler, filters

from openclaw.gateway.base import ChannelAdapter
from openclaw.messages.models import Attachment, InboundMessage, OutboundMessage
from openclaw.types import Channel, Intent

# TTS for voice messages
from openclaw.tts import synthesize as tts_synthesize

logger = logging.getLogger(__name__)

# Per-user conversation history settings
_MAX_HISTORY = 20  # Max messages per user (10 exchanges)
_HISTORY_TTL = 3600  # 1 hour — keep multi-photo troubleshooting sessions alive


class TelegramAdapter(ChannelAdapter):
    def __init__(
        self,
        token: str,
        dispatch: Callable[[InboundMessage], Awaitable[OutboundMessage]],
        allowed_users: list[int] | None = None,
        openai_api_key: str = "",
    ) -> None:
        self._token = token
        self._dispatch = dispatch
        self._allowed_users = set(allowed_users) if allowed_users else None
        self._app: Application | None = None
        self._openai_api_key = openai_api_key
        self._voice_enabled = True  # Can be toggled per-user later
        # Per-user conversation history: {user_id: [{"role": ..., "content": ..., "ts": ...}]}
        self._history: dict[str, list[dict]] = defaultdict(list)

    async def start(self) -> None:
        self._app = Application.builder().token(self._token).build()
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message))
        self._app.add_handler(MessageHandler(filters.PHOTO, self._on_photo))
        # Explicit command handlers
        self._app.add_handler(CommandHandler("start", self._on_start))
        self._app.add_handler(CommandHandler("help", self._on_help))
        self._app.add_handler(CommandHandler("clear", self._on_clear))
        # Route all known commands through generic handler
        for cmd in ("status", "diagnose", "health", "search", "run",
                     "diagram", "wiring", "gist", "project", "wo", "workorder",
                     "admin", "photo", "troubleshoot"):
            self._app.add_handler(CommandHandler(cmd, self._on_command))

        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)
        logger.info("Telegram adapter started")

    async def stop(self) -> None:
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()

    async def send(self, message: OutboundMessage) -> None:
        if self._app:
            # Send image attachments first
            for att in message.attachments:
                if att.type == "image" and att.data:
                    try:
                        await self._app.bot.send_photo(
                            chat_id=int(message.user_id),
                            photo=att.data,
                            caption=att.filename or "",
                        )
                    except Exception:
                        logger.exception("Failed to send photo via send()")
            await self._app.bot.send_message(
                chat_id=int(message.user_id),
                text=message.text,
                parse_mode="Markdown" if message.parse_mode == "markdown" else None,
            )

    def name(self) -> str:
        return "telegram"

    def _is_allowed(self, user_id: int) -> bool:
        if not self._allowed_users:
            return True
        return user_id in self._allowed_users

    def _get_history(self, user_id: str) -> list[dict]:
        """Get conversation history for a user, pruning stale entries."""
        history = self._history[user_id]
        now = time.time()
        # Remove entries older than TTL
        history[:] = [h for h in history if now - h.get("ts", 0) < _HISTORY_TTL]
        return [{"role": h["role"], "content": h["content"]} for h in history]

    def _add_to_history(self, user_id: str, role: str, content: str) -> None:
        """Add a message to conversation history, capping at max."""
        self._history[user_id].append({
            "role": role,
            "content": content,
            "ts": time.time(),
        })
        # Cap history length
        if len(self._history[user_id]) > _MAX_HISTORY:
            self._history[user_id] = self._history[user_id][-_MAX_HISTORY:]

    async def _capture_to_brain(self, role: str, content: str, user_id: str, source: str = "telegram") -> None:
        """Non-blocking capture of conversation to Open Brain."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(
                    os.environ.get("BRAIN_INGEST_URL", "http://localhost:8500") + "/ingest",
                    json={
                        "content": content,
                        "source": source,
                        "tags": [role, "conversation"],
                        "metadata": {"user_id": user_id, "role": role},
                    },
                )
        except Exception:
            logger.debug("brain capture failed (non-blocking)")

    async def _send_long(self, update: Update, text: str, parse_mode: str | None = None) -> None:
        """Send message, chunking if over Telegram's 4096 char limit."""
        MAX = 4096
        if len(text) <= MAX:
            await update.message.reply_text(text, parse_mode=parse_mode)
            return
        logger.debug("Chunking message: %d chars", len(text))
        chunks: list[str] = []
        while text:
            if len(text) <= MAX:
                chunks.append(text)
                break
            cut = text.rfind("\n\n", 0, MAX)
            if cut == -1:
                cut = text.rfind("\n", 0, MAX)
            if cut == -1:
                cut = MAX
            chunks.append(text[:cut])
            text = text[cut:].lstrip("\n")
        logger.debug("Chunking message: %d chunks", len(chunks))
        for chunk in chunks:
            try:
                await update.message.reply_text(chunk, parse_mode=parse_mode)
            except Exception:
                await update.message.reply_text(chunk)

    async def _reply(self, update: Update, text: str) -> None:
        """Reply with Markdown, falling back to plain text on parse errors."""
        try:
            await self._send_long(update, text, parse_mode="Markdown")
        except Exception:
            try:
                await self._send_long(update, text)
            except Exception:
                logger.exception("Failed to send even as plain text")
                await update.message.reply_text("Response generated but could not be sent. Please try again.")


    async def _send_attachments(self, update: Update, attachments: list) -> None:
        """Send image/document attachments from OutboundMessage."""
        for att in attachments:
            if att.type == "image" and att.data:
                try:
                    await update.message.reply_photo(
                        photo=att.data,
                        caption=att.filename or "diagram.png",
                    )
                except Exception:
                    logger.exception("Failed to send photo attachment")
            elif att.type == "document" and att.data:
                try:
                    await update.message.reply_document(
                        document=att.data,
                        filename=att.filename or "file",
                    )
                except Exception:
                    logger.exception("Failed to send document attachment")

    async def _send_voice(self, update: Update, text: str) -> None:
        """Convert text to OGG Opus and send as Telegram voice message."""
        try:
            await update.message.chat.send_action(ChatAction.RECORD_VOICE)
            audio_bytes = await tts_synthesize(text, self._openai_api_key)
            if audio_bytes:
                import io
                await update.message.reply_voice(
                    voice=io.BytesIO(audio_bytes),
                    caption=None,
                )
                logger.info("Voice message sent: %d bytes", len(audio_bytes))
            else:
                logger.warning("TTS synthesis returned None — text-only response")
        except Exception:
            logger.exception("Failed to send voice message — text already sent")

    async def _on_message(self, update: Update, context) -> None:
        if not update.message or not update.message.text:
            return
        user = update.message.from_user
        if not user or not self._is_allowed(user.id):
            return

        user_id = str(user.id)
        user_text = update.message.text

        # Show typing indicator
        await update.message.chat.send_action(ChatAction.TYPING)

        # Get conversation history and inject into metadata
        history = self._get_history(user_id)

        msg = InboundMessage(
            id=str(uuid.uuid4()),
            channel=Channel.TELEGRAM,
            user_id=user_id,
            user_name=user.first_name or "",
            text=user_text,
            metadata={"history": history} if history else {},
        )

        # Store user message in history
        self._add_to_history(user_id, "user", user_text)
        asyncio.create_task(self._capture_to_brain("user", user_text, user_id))

        try:
            response = await self._dispatch(msg)
            # Send image attachments first (e.g., diagrams)
            if response.attachments:
                await self._send_attachments(update, response.attachments)
            await self._reply(update, response.text)
            # Send voice message (non-blocking — text already sent)
            if self._voice_enabled and not response.attachments:
                await self._send_voice(update, response.text)
            # Store assistant response in history
            self._add_to_history(user_id, "assistant", response.text[:500])
            asyncio.create_task(self._capture_to_brain("assistant", response.text, user_id))
        except Exception:
            logger.exception("dispatch failed for message from user %s", user.id)
            await update.message.reply_text("Error processing request. Logged for review.")

    async def _on_photo(self, update: Update, context) -> None:
        if not update.message or not update.message.photo:
            return
        user = update.message.from_user
        if not user or not self._is_allowed(user.id):
            return

        user_id = str(user.id)

        # Show typing indicator
        await update.message.chat.send_action(ChatAction.TYPING)

        photo = update.message.photo[-1]  # Largest size
        file = await context.bot.get_file(photo.file_id)
        data = await file.download_as_bytearray()

        # Get conversation history so photo analysis has context
        history = self._get_history(user_id)

        msg = InboundMessage(
            id=str(uuid.uuid4()),
            channel=Channel.TELEGRAM,
            user_id=user_id,
            user_name=user.first_name or "",
            text=update.message.caption or "",
            attachments=[Attachment(type="image", data=bytes(data), mime_type="image/jpeg")],
            metadata={"history": history} if history else {},
        )

        # Store user message in history (note photo was sent)
        caption = update.message.caption or ""
        self._add_to_history(user_id, "user", f"[Sent a photo] {caption}".strip())
        asyncio.create_task(self._capture_to_brain("user", f"[Photo] {caption}", user_id, source="telegram_photo"))

        try:
            response = await self._dispatch(msg)
            await self._reply(update, response.text)
            # Store photo analysis with higher char limit so context is preserved
            self._add_to_history(
                user_id, "assistant",
                f"[Photo Analysis] {response.text[:1000]}",
            )
        except Exception:
            logger.exception("photo dispatch failed for user %s", user.id)
            await update.message.reply_text("Error processing request. Logged for review.")

    async def _on_start(self, update: Update, context) -> None:
        if update.message:
            await update.message.reply_text(
                "Jarvis online. What do you need, Mike?"
            )

    async def _on_help(self, update: Update, context) -> None:
        await self._on_start(update, context)

    async def _on_clear(self, update: Update, context) -> None:
        """Clear conversation history for this user."""
        if not update.message:
            return
        user = update.message.from_user
        if user:
            self._history[str(user.id)] = []
            await update.message.reply_text("Conversation history cleared.")

    async def _on_command(self, update: Update, context) -> None:
        if not update.message:
            return
        user = update.message.from_user
        if not user or not self._is_allowed(user.id):
            return

        user_id = str(user.id)
        text = update.message.text or ""

        # Show typing indicator
        await update.message.chat.send_action(ChatAction.TYPING)

        # Get conversation history
        history = self._get_history(user_id)

        msg = InboundMessage(
            id=str(uuid.uuid4()),
            channel=Channel.TELEGRAM,
            user_id=user_id,
            user_name=user.first_name or "",
            text=text,
            metadata={"history": history} if history else {},
        )

        # Store user message in history
        self._add_to_history(user_id, "user", text)

        try:
            response = await self._dispatch(msg)
            # Send image attachments first (e.g., diagrams)
            if response.attachments:
                await self._send_attachments(update, response.attachments)
            await self._reply(update, response.text)
            # Store assistant response in history
            self._add_to_history(user_id, "assistant", response.text[:500])
        except Exception:
            logger.exception("command dispatch failed for user %s", user.id)
            await update.message.reply_text("Error processing request. Logged for review.")
