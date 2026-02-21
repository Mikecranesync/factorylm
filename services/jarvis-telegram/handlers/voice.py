# Restored from: feature/rideview-continuous-improvement:projects/factorylm/puppeteer/bot.py
"""
Voice command handler — transcribes with Whisper and responds via Groq text model.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from prompts import VOICE_PROMPT

logger = logging.getLogger(__name__)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process a voice note and return an AI response with equipment context."""
    config = context.bot_data["config"]
    groq = context.bot_data["groq"]
    conv = context.bot_data["conversation_manager"]
    rate_limiter = context.bot_data["rate_limiter"]

    user_id = update.effective_user.id
    if not config.is_user_allowed(user_id):
        return

    if not rate_limiter.check(user_id):
        await update.message.reply_text("Rate limited — please wait a moment.")
        return

    if not groq:
        await update.message.reply_text("Voice processing not configured (GROQ_API_KEY missing).")
        return

    # Typing indicator while processing
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    status_msg = await update.message.reply_text("Processing voice...")

    try:
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        voice_bytes = bytes(await file.download_as_bytearray())

        # Build context-aware prompt
        prompt = VOICE_PROMPT
        if session := conv.get_or_create_session(str(user_id)):
            if session.last_diagnosis:
                prompt += f"\n\nPrevious equipment diagnosis:\n{session.last_diagnosis[:500]}"

        response = await groq.analyze_voice(voice_bytes, prompt)

        conv.add_bot_message(session, response, metadata={"source": "voice"})

        await status_msg.edit_text(response)
        logger.info(f"Voice processed for user {user_id}")

    except Exception as e:
        logger.error(f"Voice handler error: {e}")
        await status_msg.edit_text(f"Voice processing failed: {e}")
