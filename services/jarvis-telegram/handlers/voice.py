# Restored from: feature/rideview-continuous-improvement:projects/factorylm/puppeteer/bot.py
"""
Voice command handler — transcribes and responds to voice notes.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from ..prompts import VOICE_PROMPT

logger = logging.getLogger(__name__)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process a voice note and return an AI response with equipment context."""
    config = context.bot_data["config"]
    gemini = context.bot_data["gemini"]
    conv = context.bot_data["conversation_manager"]

    user_id = update.effective_user.id
    if not config.is_user_allowed(user_id):
        return

    session = conv.get_or_create_session(str(user_id))
    status_msg = await update.message.reply_text("Processing voice...")

    try:
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        voice_bytes = bytes(await file.download_as_bytearray())

        # Build context-aware prompt
        prompt = VOICE_PROMPT
        if session.last_diagnosis:
            prompt += f"\n\nPrevious equipment diagnosis:\n{session.last_diagnosis[:500]}"

        response = await gemini.analyze_voice(voice_bytes, prompt)

        conv.add_bot_message(session, response, metadata={"source": "voice"})

        await status_msg.edit_text(response)
        logger.info(f"Voice processed for user {user_id}")

    except Exception as e:
        logger.error(f"Voice handler error: {e}")
        await status_msg.edit_text(f"Voice processing failed: {e}")
