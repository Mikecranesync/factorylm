"""
Telegram Router
===============
Handle incoming Telegram messages and send responses.
"""

import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
import httpx

from backend.config import settings
from backend.models.database import get_db, User, Command
from backend.services.command_parser import parse_command
from backend.services.node_client import execute_on_node
from backend.services.telemetry import get_tracer

logger = logging.getLogger(__name__)
router = APIRouter()
tracer = get_tracer()


class TelegramUpdate(BaseModel):
    """Telegram webhook update"""
    update_id: int
    message: Optional[dict] = None


@router.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Receive Telegram webhook updates.

    Flow:
    1. Receive message from Telegram
    2. Parse command with Claude
    3. Execute on target node
    4. Send result back to user
    """
    try:
        data = await request.json()
        update_id = data.get('update_id')
        logger.info(f"Received Telegram update: {update_id}")

        message = data.get("message", {})
        if not message:
            return {"ok": True}

        # Extract message details
        chat_id = message.get("chat", {}).get("id")
        user_id = message.get("from", {}).get("id")
        username = message.get("from", {}).get("username")
        text = message.get("text", "")

        if not text:
            return {"ok": True}

        logger.info(f"Message from {username} ({user_id}): {text}")

        # Trace the full message handling
        with tracer.span("handle_message", {
            "telegram.update_id": update_id,
            "telegram.chat_id": chat_id,
            "telegram.user_id": user_id,
            "telegram.username": username or "unknown",
            "message.text": text[:100],
        }) as span:

            # Parse command with tracing
            with tracer.span("parse_command", {"input.text": text[:100]}) as parse_span:
                parsed = await parse_command(text)
                parse_span.set_attribute("parsed.intent", parsed.get("intent", "unknown"))
                parse_span.set_attribute("parsed.node", parsed.get("node", "unknown"))
                parse_span.set_attribute("parsed.confidence", parsed.get("confidence", 0))

            logger.info(f"Parsed: {parsed}")
            span.set_attribute("parsed.intent", parsed.get("intent", "unknown"))

            # Execute on node
            if parsed.get("intent") in ["screenshot", "shell", "interpret", "click", "type"]:
                with tracer.span("execute_on_node", {
                    "node.name": parsed.get("node", "plc-laptop"),
                    "action.intent": parsed["intent"],
                }) as exec_span:
                    result = await execute_on_node(
                        node_name=parsed.get("node", "plc-laptop"),
                        intent=parsed["intent"],
                        args=parsed.get("args", {})
                    )
                    exec_span.set_attribute("result.success", result.get("success", False))
                    if result.get("error"):
                        exec_span.set_attribute("result.error", result.get("error"))

                # Send response
                response_text = f"✅ {parsed['intent'].title()} completed\n\n{result.get('output', 'Done')}"
                with tracer.span("send_response", {"response.type": "text"}):
                    await send_telegram_message(
                        chat_id=chat_id,
                        text=response_text
                    )

                # Send screenshot if available
                if result.get("screenshot_path"):
                    with tracer.span("send_screenshot", {"screenshot.path": result["screenshot_path"]}):
                        await send_telegram_photo(chat_id, result["screenshot_path"])

                span.set_attribute("result.success", True)

            else:
                await send_telegram_message(
                    chat_id=chat_id,
                    text=f"🤔 I didn't understand that command.\n\nTry:\n- 'screenshot'\n- 'run [command]'\n- 'open chrome and go to google.com'"
                )
                span.set_attribute("result.unknown_command", True)

        return {"ok": True}

    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        tracer.capture_message(f"Webhook error: {e}", level="error", extras={
            "error": str(e),
        })
        return {"ok": True}  # Always return 200 to Telegram


async def send_telegram_message(chat_id: int, text: str, parse_mode: str = "Markdown"):
    """Send message to Telegram"""
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        })
        return response.json()


async def send_telegram_photo(chat_id: int, photo_path: str, caption: str = ""):
    """Send photo to Telegram"""
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendPhoto"

    async with httpx.AsyncClient() as client:
        with open(photo_path, "rb") as photo:
            response = await client.post(url, data={
                "chat_id": chat_id,
                "caption": caption
            }, files={"photo": photo})
        return response.json()


@router.post("/send")
async def send_message(chat_id: int, text: str):
    """Manually send a message (for testing)"""
    result = await send_telegram_message(chat_id, text)
    return result


@router.get("/telemetry")
async def get_telemetry():
    """Get telemetry stats and recent traces."""
    return {
        "stats": tracer.get_stats(),
        "recent_spans": tracer.get_recent_spans(20),
    }
