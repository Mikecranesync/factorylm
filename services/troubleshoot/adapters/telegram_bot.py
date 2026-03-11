"""Thin Telegram adapter for the Troubleshoot Engine.

Run:
    cd services/troubleshoot
    TELEGRAM_TOKEN=<token> OPENAI_API_KEY=<key> python -m adapters.telegram_bot
"""

from __future__ import annotations

import logging
import os
import socket
import sys
from pathlib import Path

from dotenv import load_dotenv

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from engine import EngineResponse, SessionState, TroubleshootEngine
from engine.llm import get_provider

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = BASE_DIR / "workflows"
PHOTOS_DIR = BASE_DIR / "photos"
WORK_ORDERS_DIR = BASE_DIR / "work_orders"

PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
WORK_ORDERS_DIR.mkdir(parents=True, exist_ok=True)

# Engine singleton — initialized in main()
engine: TroubleshootEngine | None = None


def _enforce_single_instance():
    """Bind a socket to prevent two bot instances on the same machine."""
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", 47200))
        lock.listen(1)
        return lock
    except OSError:
        logger.error("Another bot instance is running on this machine. Exiting.")
        sys.exit(1)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log unhandled exceptions so they don't fail silently."""
    logger.error("Unhandled error: %s", context.error, exc_info=context.error)


def _get_session(context: ContextTypes.DEFAULT_TYPE) -> SessionState | None:
    return context.user_data.get("session")


def _set_session(context: ContextTypes.DEFAULT_TYPE, session: SessionState) -> None:
    context.user_data["session"] = session


def _render_response(response: EngineResponse) -> tuple[str, InlineKeyboardMarkup | None]:
    """Convert EngineResponse to Telegram message text + keyboard."""
    text = response.message_text

    keyboard = None
    if response.buttons:
        rows = [
            [InlineKeyboardButton(btn["label"], callback_data=btn["id"])]
            for btn in response.buttons
        ]
        # Add skip button if expecting photo
        if response.expecting == "photo" and not any(
            btn["id"] == "__skip_photo__" for btn in response.buttons
        ):
            rows.append(
                [InlineKeyboardButton("Skip", callback_data="__skip_photo__")]
            )
        keyboard = InlineKeyboardMarkup(rows)

    if response.expecting == "done":
        text += "\n\n✅ Session complete. Send /start to begin a new session."

    return text, keyboard


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — begin a new troubleshooting session."""
    user_id = f"tg_{update.effective_user.id}"
    session, response = engine.start_session(user_id)
    _set_session(context, session)

    text, keyboard = _render_response(response)
    await update.message.reply_text(text, reply_markup=keyboard)


async def on_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button presses."""
    query = update.callback_query
    await query.answer()

    session = _get_session(context)
    if not session:
        await query.edit_message_text("No active session. Send /start to begin.")
        return

    response = await engine.handle_button(session, query.data)
    text, keyboard = _render_response(response)
    await query.edit_message_text(text, reply_markup=keyboard)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plain text messages."""
    session = _get_session(context)
    if not session:
        await update.message.reply_text("Send /start to begin a troubleshooting session.")
        return

    response = await engine.handle_text(session, update.message.text)
    text, keyboard = _render_response(response)
    await update.message.reply_text(text, reply_markup=keyboard)


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photo messages — download and pass to engine."""
    session = _get_session(context)
    if not session:
        await update.message.reply_text("Send /start to begin a troubleshooting session.")
        return

    # Download the largest photo
    photo = update.message.photo[-1]
    file = await photo.get_file()
    n = len(session.photos) + 1
    filename = PHOTOS_DIR / f"{session.session_id}_{n}.jpg"
    await file.download_to_drive(str(filename))
    logger.info("Photo saved: %s", filename)

    response = await engine.handle_photo(session, str(filename))
    text, keyboard = _render_response(response)
    await update.message.reply_text(text, reply_markup=keyboard)


def main() -> None:
    _lock = _enforce_single_instance()  # noqa: F841 — prevent GC

    load_dotenv(BASE_DIR / ".env")
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN not set")
        return

    global engine
    llm = get_provider()
    engine = TroubleshootEngine(
        workflows_dir=WORKFLOWS_DIR,
        llm=llm,
        work_orders_dir=WORK_ORDERS_DIR,
    )

    app = (
        Application.builder()
        .token(token)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(10)
        .build()
    )
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(on_callback_query))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)

    logger.info("Bot starting — %d workflows loaded", len(engine._workflows))
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
