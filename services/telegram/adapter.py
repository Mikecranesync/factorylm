"""Telegram adapter — thin bridge from Telegram updates to FactoryLM pipeline.

Inbound:  Telegram update → FactoryLMInput → pipeline.process()
Outbound: FactoryLMResponse → format_telegram() → reply

Usage:
    from services.telegram.adapter import create_app

    app = create_app(bot_token="...")
    app.run_polling()
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Ensure monorepo root is importable
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.pipeline import FactoryLMInput, FactoryLMResponse, process
from services.media.telegram_media_handler import TelegramMediaHandler

logger = logging.getLogger("factorylm.telegram")

MEDIA_INBOX = Path.home() / ".openclaw" / "media-inbox" / "telegram"


# ---------------------------------------------------------------------------
# Format response for Telegram
# ---------------------------------------------------------------------------

def format_telegram(resp: FactoryLMResponse) -> str:
    """Format a pipeline response for Telegram delivery."""
    lines = [resp.text]
    footer_parts = []
    if resp.provider:
        footer_parts.append(resp.provider)
    if resp.elapsed_s:
        footer_parts.append(f"{resp.elapsed_s}s")
    if resp.trace_id:
        footer_parts.append(resp.trace_id[:8])
    if resp.incident_id:
        lines.append(f"\nIncident #{resp.incident_id} recorded.")
    if footer_parts:
        lines.append(f"\n[{' | '.join(footer_parts)}]")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

media_handler = TelegramMediaHandler()


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plain text messages — route through pipeline."""
    text = update.message.text or ""
    if not text.strip():
        return

    user = update.effective_user
    user_id = str(user.id) if user else "unknown"
    logger.info("Telegram msg from %s: text %d chars", user_id, len(text))

    inp = FactoryLMInput(
        text=text,
        user_id=user_id,
        channel="telegram",
    )

    resp = await process(inp)
    reply = format_telegram(resp)
    await update.message.reply_text(reply)
    logger.info("[%s] Reply sent to %s (%ss)", resp.trace_id or "?", user_id, resp.elapsed_s)


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photo/video — save to disk, route through vision pipeline."""
    message = update.message
    user = update.effective_user
    user_id = str(user.id) if user else "unknown"
    caption = message.caption or ""

    # Determine media type
    if message.photo:
        photo = message.photo[-1]
        file_id = photo.file_id
        media_type = "photo"
        ext = ".jpg"
    elif message.video:
        file_id = message.video.file_id
        media_type = "video"
        ext = ".mp4"
    else:
        await update.message.reply_text("Unsupported media type.")
        return

    # Download file
    tg_file = await context.bot.get_file(file_id)
    file_bytes = await tg_file.download_as_bytearray()

    # Save to inbox
    from datetime import datetime
    date_folder = MEDIA_INBOX / datetime.now().strftime("%Y-%m-%d")
    date_folder.mkdir(parents=True, exist_ok=True)
    username = (user.username or user.first_name or str(user.id)) if user else "unknown"
    safe_user = "".join(c for c in username if c.isalnum())[:10]
    filename = f"{datetime.now().strftime('%H%M%S')}_{safe_user}{ext}"
    file_path = date_folder / filename
    file_path.write_bytes(file_bytes)

    size_kb = len(file_bytes) / 1024
    logger.info("Telegram msg from %s: %s %.1f KB", user_id, media_type, size_kb)
    await update.message.reply_text(f"Received {media_type} ({size_kb:.1f} KB). Analyzing...")

    # Route through pipeline
    inp = FactoryLMInput(
        media_path=str(file_path),
        media_type=media_type,
        caption=caption,
        user_id=user_id,
        channel="telegram",
    )

    resp = await process(inp)
    reply = format_telegram(resp)
    await update.message.reply_text(reply)
    logger.info("[%s] Reply sent to %s (%ss)", resp.trace_id or "?", user_id, resp.elapsed_s)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start — welcome message."""
    await update.message.reply_text(
        "FactoryLM — AI factory diagnostics.\n\n"
        "Send a photo or video of your equipment for vision analysis.\n"
        "Or ask a question about your factory."
    )


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(bot_token: str | None = None) -> Application:
    """Build and return a configured Telegram Application."""
    token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, handle_media))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Telegram adapter ready")
    return app


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    app = create_app()
    app.run_polling()
