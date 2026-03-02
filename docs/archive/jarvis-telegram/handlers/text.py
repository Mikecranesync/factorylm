# Restored from: main:installers/claude-telegram-bridge/claude_telegram_bridge.py
"""
Text message handler — routes text through LLM fallback chain (Groq → Cerebras → OpenRouter),
with Claude CLI as last resort.
"""

import logging
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from integrations.claude_bridge import run_claude
from prompts import VOICE_PROMPT

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = VOICE_PROMPT


def _build_messages(session, message: str) -> list[dict]:
    """Build OpenAI-format messages from session context."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if session.last_diagnosis:
        messages.append({"role": "system", "content": f"Previous equipment diagnosis:\n{session.last_diagnosis[:500]}"})
    messages.append({"role": "user", "content": message})
    return messages


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process a text message — uses LLM fallback chain, Claude CLI as last resort."""
    config = context.bot_data["config"]
    conv = context.bot_data["conversation_manager"]
    llm_chain = context.bot_data.get("llm_chain")
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

    # Route: LLM fallback chain (Groq → Cerebras → OpenRouter), Claude CLI as last resort
    if llm_chain:
        messages = _build_messages(session, message)
        response, provider = await llm_chain.chat(messages)
        logger.info(f"Text response via {provider} for user {user_id}")
    elif claude_available:
        workspace = Path(config.claude_workspace) if config.claude_workspace else None
        enriched = message
        if session.last_diagnosis:
            enriched = f"Previous equipment diagnosis:\n{session.last_diagnosis[:500]}\n\nTechnician's follow-up: {message}"
        response = await run_claude(enriched, workspace=workspace)
        provider = "claude"
    else:
        response = "No AI backend configured. Set GROQ_API_KEY or install Claude CLI."
        provider = None

    conv.add_bot_message(session, response)

    # Byline only in Telegram display, not in conversation history
    display = f"{response}\n\n— via {provider}" if provider else response

    # Telegram has 4096 char limit — split if needed
    if len(display) > 4000:
        chunks = [display[i : i + 4000] for i in range(0, len(display), 4000)]
        for chunk in chunks:
            await update.message.reply_text(chunk)
    else:
        await update.message.reply_text(display)


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
