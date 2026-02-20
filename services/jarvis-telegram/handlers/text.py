# Restored from: main:installers/claude-telegram-bridge/claude_telegram_bridge.py
"""
Text message handler — routes text to Claude CLI or Groq depending on context.
"""

import logging
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from integrations.claude_bridge import run_claude
from prompts import VOICE_PROMPT

logger = logging.getLogger(__name__)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process a text message — uses Claude CLI bridge if available, else Groq."""
    config = context.bot_data["config"]
    conv = context.bot_data["conversation_manager"]
    groq = context.bot_data.get("groq")
    claude_available = context.bot_data.get("claude_available", False)
    rate_limiter = context.bot_data["rate_limiter"]

    user_id = update.effective_user.id
    if not config.is_user_allowed(user_id):
        logger.warning(f"Unauthorized user: {user_id}")
        await update.message.reply_text("Access denied. Contact admin for access.")
        return

    if not rate_limiter.check(user_id):
        await update.message.reply_text("Rate limited — please wait a moment.")
        return

    message = update.message.text
    session = conv.get_or_create_session(str(user_id))
    conv.add_user_message(session, message)

    # Show typing indicator
    if config.typing_indicator:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # Route: Claude CLI if available, else Groq with context
    if claude_available:
        workspace = Path(config.claude_workspace) if config.claude_workspace else None
        response = await run_claude(message, workspace=workspace)
    elif groq:
        context_parts = [VOICE_PROMPT]
        if session.last_diagnosis:
            context_parts.append(f"Previous diagnosis:\n{session.last_diagnosis[:500]}")
        context_parts.append(f"Technician asks: {message}")
        response = await groq.generate_text(context_parts)
    else:
        response = "No AI backend configured. Set GROQ_API_KEY or install Claude CLI."

    conv.add_bot_message(session, response)

    # Telegram has 4096 char limit — split if needed
    if len(response) > 4000:
        chunks = [response[i : i + 4000] for i in range(0, len(response), 4000)]
        for chunk in chunks:
            await update.message.reply_text(chunk)
    else:
        await update.message.reply_text(response)


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /clear — reset conversation session."""
    config = context.bot_data["config"]
    conv = context.bot_data["conversation_manager"]

    user_id = update.effective_user.id
    if not config.is_user_allowed(user_id):
        return

    # Remove session
    conv.active_sessions.pop(str(user_id), None)
    await update.message.reply_text("Conversation cleared")
