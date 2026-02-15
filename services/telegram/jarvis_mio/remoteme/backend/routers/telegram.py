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

logger = logging.getLogger(__name__)
router = APIRouter()


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
        logger.info(f"Received Telegram update: {data.get('update_id')}")
        
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
        
        # Parse command
        parsed = await parse_command(text)
        logger.info(f"Parsed: {parsed}")
        
        # Execute on node
        if parsed.get("intent") in ["screenshot", "shell", "interpret", "click", "type"]:
            result = await execute_on_node(
                node_name=parsed.get("node", "plc-laptop"),
                intent=parsed["intent"],
                args=parsed.get("args", {})
            )
            
            # Send response
            await send_telegram_message(
                chat_id=chat_id,
                text=f"✅ {parsed['intent'].title()} completed\n\n{result.get('output', 'Done')}"
            )
            
            # Send screenshot if available
            if result.get("screenshot_path"):
                await send_telegram_photo(chat_id, result["screenshot_path"])
        
        else:
            await send_telegram_message(
                chat_id=chat_id,
                text=f"🤔 I didn't understand that command.\n\nTry:\n- 'screenshot'\n- 'run [command]'\n- 'open chrome and go to google.com'"
            )
        
        return {"ok": True}
        
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
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
