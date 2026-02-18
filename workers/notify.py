"""
Notification Helper - Send messages to Mike via Telegram
========================================================
Uses the configured Telegram bot for Master of Puppets notifications.
"""

import os
import requests
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Mike's Telegram ID
MIKE_TELEGRAM_ID = "8445149012"

# Bot token from environment
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")


def notify_mike(message: str, silent: bool = False) -> bool:
    """
    Send a notification to Mike via Telegram.
    
    Args:
        message: The message to send
        silent: If True, sends without notification sound
    
    Returns:
        True if sent successfully, False otherwise
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("No TELEGRAM_BOT_TOKEN configured, cannot notify")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": MIKE_TELEGRAM_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_notification": silent
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.ok:
            logger.info(f"Notification sent: {message[:50]}...")
            return True
        else:
            logger.error(f"Failed to send notification: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        return False


def notify_monkey_completion(task_name: str, result: str, automaton: str):
    """
    Notify Mike when the Monkey completes a task.
    """
    message = f"""🐵 **Monkey Completed Task**

**Task:** {task_name}
**Handler:** {automaton}
**Time:** {datetime.now().strftime('%H:%M:%S')} UTC

**Result:** {result[:200]}{'...' if len(result) > 200 else ''}"""
    
    return notify_mike(message)


def notify_monkey_started(task_name: str, automaton: str):
    """
    Notify Mike when the Monkey starts a task.
    """
    message = f"""🐵 **Monkey Started Task**

**Task:** {task_name}
**Assigned to:** {automaton}
**Time:** {datetime.now().strftime('%H:%M:%S')} UTC"""
    
    return notify_mike(message, silent=True)
