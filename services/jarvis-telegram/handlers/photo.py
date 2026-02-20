# Restored from: feature/rideview-continuous-improvement:projects/factorylm/puppeteer/bot.py
"""
Photo analysis handler — equipment diagnosis, nameplate OCR, work order creation.
"""

import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from prompts import NAMEPLATE_PROMPT

logger = logging.getLogger(__name__)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process an equipment photo and return a structured diagnosis."""
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
        await update.message.reply_text("Photo analysis not configured (GROQ_API_KEY missing).")
        return

    session = conv.get_or_create_session(str(user_id))

    # Typing indicator while processing
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    status_msg = await update.message.reply_text("Analyzing...")

    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        photo_bytes = bytes(await file.download_as_bytearray())

        diagnosis = await groq.analyze_image(photo_bytes)

        # Store in session
        session.last_photo = photo_bytes
        session.add_diagnosis(diagnosis)

        keyboard = [
            [
                InlineKeyboardButton("Create Work Order", callback_data="create_wo"),
                InlineKeyboardButton("Re-analyze", callback_data="reanalyze"),
            ],
            [
                InlineKeyboardButton("Nameplate Focus", callback_data="nameplate"),
                InlineKeyboardButton("Ask Follow-up", callback_data="followup"),
            ],
        ]

        await status_msg.edit_text(
            diagnosis,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        logger.info(f"Photo analyzed for user {user_id}")

    except Exception as e:
        logger.error(f"Photo handler error: {e}")
        await status_msg.edit_text(f"Analysis failed: {e}")


async def handle_photo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button callbacks from photo diagnosis."""
    query = update.callback_query
    config = context.bot_data["config"]
    groq = context.bot_data["groq"]
    cmms = context.bot_data.get("cmms")
    conv = context.bot_data["conversation_manager"]

    user_id = query.from_user.id
    if not config.is_user_allowed(user_id):
        return

    await query.answer()
    session = conv.get_or_create_session(str(user_id))

    if query.data == "create_wo":
        if not session.last_diagnosis:
            await query.edit_message_text("No diagnosis to create WO from. Send a photo first.")
            return

        await query.edit_message_text("Creating work order...")

        wo_data = await groq.generate_work_order_json(session.last_diagnosis)
        if not wo_data:
            await query.edit_message_text("Failed to generate work order details")
            return

        if cmms is None:
            await query.edit_message_text("CMMS not configured. Set CMMS_URL, CMMS_EMAIL, CMMS_PASSWORD in .env")
            return

        result = await cmms.create_work_order(
            title=wo_data.get("title", "Equipment Issue"),
            description=wo_data.get("description", session.last_diagnosis),
            priority=wo_data.get("priority", "MEDIUM"),
        )

        if result:
            await query.edit_message_text(
                f"*Work Order Created*\n\n"
                f"*ID:* {result.get('id', 'N/A')}\n"
                f"*Title:* {wo_data.get('title', 'N/A')}\n"
                f"*Priority:* {wo_data.get('priority', 'MEDIUM')}",
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text("Failed to create work order in CMMS")

    elif query.data == "reanalyze":
        if session.last_photo:
            await query.edit_message_text("Re-analyzing...")
            diagnosis = await groq.analyze_image(session.last_photo)
            session.add_diagnosis(diagnosis)
            await query.edit_message_text(diagnosis)
        else:
            await query.edit_message_text("No photo to re-analyze. Send a new photo.")

    elif query.data == "nameplate":
        if session.last_photo:
            await query.edit_message_text("Focusing on nameplate...")
            result = await groq.analyze_image(session.last_photo, NAMEPLATE_PROMPT)
            await query.edit_message_text(
                f"*NAMEPLATE DATA*\n\n{result}",
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text("No photo. Send a photo of the nameplate.")

    elif query.data == "followup":
        await query.edit_message_text(
            f"*Previous diagnosis:*\n{session.last_diagnosis[:500] if session.last_diagnosis else 'None'}\n\n"
            "Type your follow-up question below:",
            parse_mode="Markdown",
        )


async def cmd_wo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Quick /wo command — create work order from last diagnosis."""
    config = context.bot_data["config"]
    groq = context.bot_data["groq"]
    cmms = context.bot_data.get("cmms")
    conv = context.bot_data["conversation_manager"]

    user_id = update.effective_user.id
    if not config.is_user_allowed(user_id):
        return

    session = conv.get_or_create_session(str(user_id))
    if not session.last_diagnosis:
        await update.message.reply_text("No recent diagnosis. Send a photo first.")
        return

    if cmms is None:
        await update.message.reply_text("CMMS not configured.")
        return

    await update.message.reply_text("Creating work order...")

    wo_data = await groq.generate_work_order_json(session.last_diagnosis)
    if wo_data:
        result = await cmms.create_work_order(
            title=wo_data.get("title", "Equipment Issue"),
            description=wo_data.get("description", session.last_diagnosis),
            priority=wo_data.get("priority", "MEDIUM"),
        )
        if result:
            await update.message.reply_text(f"Work order created: #{result.get('id')}")
        else:
            await update.message.reply_text("CMMS error")
    else:
        await update.message.reply_text("Failed to generate WO")


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show recent diagnoses for this user."""
    config = context.bot_data["config"]
    conv = context.bot_data["conversation_manager"]

    user_id = update.effective_user.id
    if not config.is_user_allowed(user_id):
        return

    session = conv.get_or_create_session(str(user_id))
    if not session.diagnosis_history:
        await update.message.reply_text("No history yet. Send a photo to start.")
        return

    text = "*Recent Activity*\n\n"
    for i, item in enumerate(reversed(session.diagnosis_history[-5:]), 1):
        text += f"{i}. {item['timestamp'][:16]}\n{item['result'][:100]}...\n\n"

    await update.message.reply_text(text, parse_mode="Markdown")
