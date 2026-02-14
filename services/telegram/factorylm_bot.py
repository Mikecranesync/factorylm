#!/usr/bin/env python3
"""
FactoryLM Telegram Bot
======================
Routes Telegram messages to FactoryLM backend services on PLC laptop.

Commands:
  /start - Welcome message
  /help - Show commands
  /status - Check service connectivity
  /io or "show me IO" - Live PLC tags
  /diagnose or "why stopped" - AI fault diagnosis

Deployment:
  # On VPS (100.68.120.99)
  pip install python-telegram-bot httpx
  export TELEGRAM_BOT_TOKEN="8447289218:AAGKcDbW_2DEDoF-FAeQ6Ss7hH1tXNt-O5Q"
  python factorylm_bot.py

  # As systemd service
  systemctl start factorylm-telegram
"""

import os
import sys
import logging
import httpx
from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ============================================================================
# Configuration
# ============================================================================

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8447289218:AAGKcDbW_2DEDoF-FAeQ6Ss7hH1tXNt-O5Q")
ALLOWED_USERS = [8445149012]  # Mike's Telegram ID

# PLC Laptop services (via Tailscale)
MATRIX_API = os.getenv("MATRIX_API", "http://100.72.2.99:8000")
DEMO_UI = os.getenv("DEMO_UI", "http://100.72.2.99:8080")
JARVIS_NODE = os.getenv("JARVIS_NODE", "http://100.72.2.99:8765")

# Logging
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# HTTP client
http = httpx.Client(timeout=30)


# ============================================================================
# Auth Check
# ============================================================================

def is_allowed(update: Update) -> bool:
    """Check if user is in allowlist."""
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USERS:
        logger.warning(f"Unauthorized user: {user_id} ({update.effective_user.username})")
        return False
    return True


# ============================================================================
# Command Handlers
# ============================================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    if not is_allowed(update):
        await update.message.reply_text("Not authorized.")
        return

    await update.message.reply_text(
        "Welcome to FactoryLM!\n\n"
        "I connect you to your factory equipment.\n\n"
        "Commands:\n"
        "  /io - Live PLC tags\n"
        "  /diagnose - AI fault diagnosis\n"
        "  /status - Service health\n"
        "  /help - This message\n\n"
        "Or just ask:\n"
        '  "show me IO"\n'
        '  "why is this stopped?"\n'
        '  "what faults are active?"'
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    if not is_allowed(update):
        return

    await update.message.reply_text(
        "FactoryLM Commands:\n\n"
        "Monitoring:\n"
        "  /io - Display live PLC tags\n"
        '  "show me IO" - Same as /io\n\n'
        "Diagnosis:\n"
        "  /diagnose [question] - AI fault analysis\n"
        '  "why is this stopped?" - Quick diagnosis\n'
        '  "what faults are active?" - Check faults\n\n'
        "System:\n"
        "  /status - Check service connectivity\n"
        "  /help - This message"
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command - check all services."""
    if not is_allowed(update):
        return

    status_lines = ["System Status:\n"]

    # Check Matrix API
    try:
        resp = http.get(f"{MATRIX_API}/api/health", timeout=5)
        if resp.status_code == 200:
            status_lines.append(f"[OK] Matrix API: {MATRIX_API}")
        else:
            status_lines.append(f"[!] Matrix API: HTTP {resp.status_code}")
    except Exception as e:
        status_lines.append(f"[X] Matrix API: {str(e)[:40]}")

    # Check Demo UI
    try:
        resp = http.get(f"{DEMO_UI}/health", timeout=5)
        if resp.status_code == 200:
            status_lines.append(f"[OK] Demo UI: {DEMO_UI}")
        else:
            status_lines.append(f"[!] Demo UI: HTTP {resp.status_code}")
    except Exception as e:
        status_lines.append(f"[X] Demo UI: {str(e)[:40]}")

    # Check Jarvis Node
    try:
        resp = http.get(f"{JARVIS_NODE}/health", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            status_lines.append(f"[OK] PLC Laptop: {data.get('machine', 'online')}")
        else:
            status_lines.append(f"[!] PLC Laptop: HTTP {resp.status_code}")
    except Exception as e:
        status_lines.append(f"[X] PLC Laptop: {str(e)[:40]}")

    await update.message.reply_text("\n".join(status_lines))


async def cmd_io(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /io command - show live PLC tags."""
    if not is_allowed(update):
        return

    try:
        resp = http.get(f"{MATRIX_API}/api/tags?limit=1", timeout=10)
        resp.raise_for_status()
        tags_list = resp.json()

        if not tags_list:
            await update.message.reply_text("No tag data available. Is Factory I/O running?")
            return

        tags = tags_list[0]

        # Format output
        lines = [
            "Live I/O Status:",
            f"  Node: {tags.get('node_id', 'unknown')}",
            f"  Time: {tags.get('timestamp', '')[:19]}",
            "",
            "Motors:",
            f"  Motor:     {'RUNNING' if tags.get('motor_running') else 'STOPPED'} @ {tags.get('motor_speed', 0)}%",
            f"  Current:   {tags.get('motor_current', 0):.2f} A",
            f"  Conveyor:  {'RUNNING' if tags.get('conveyor_running') else 'STOPPED'} @ {tags.get('conveyor_speed', 0)}%",
            "",
            "Sensors:",
            f"  Temp:      {tags.get('temperature', 0):.1f} C",
            f"  Pressure:  {tags.get('pressure', 0)} PSI",
            f"  Sensor 1:  {'ACTIVE' if tags.get('sensor_1') else 'clear'}",
            f"  Sensor 2:  {'ACTIVE' if tags.get('sensor_2') else 'clear'}",
            "",
            "Alarms:",
            f"  Fault:     {'ACTIVE!' if tags.get('fault_alarm') else 'None'}",
            f"  E-Stop:    {'PRESSED!' if tags.get('e_stop') else 'Clear'}",
        ]

        if tags.get('error_code'):
            lines.append(f"  Error:     {tags.get('error_code')} - {tags.get('error_message', '')}")

        await update.message.reply_text("\n".join(lines))

    except Exception as e:
        logger.error(f"IO fetch error: {e}")
        await update.message.reply_text(f"Failed to fetch IO: {str(e)[:100]}")


async def cmd_diagnose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /diagnose command - AI fault diagnosis."""
    if not is_allowed(update):
        return

    # Get question from args or use default
    question = " ".join(context.args) if context.args else "Why is this equipment stopped?"

    await update.message.reply_text(f"Analyzing: {question}\n\nPlease wait...")

    try:
        resp = http.post(
            f"{DEMO_UI}/api/diagnose",
            json={"question": question},
            timeout=60
        )
        resp.raise_for_status()
        data = resp.json()

        lines = [
            f"AI Diagnosis ({data.get('latency_ms', 0)}ms):",
            f"Model: {data.get('model', 'unknown')}",
            "",
            data.get('answer', 'No answer available')
        ]

        faults = data.get('faults_detected', [])
        if faults:
            lines.append("")
            lines.append(f"Active Faults: {', '.join(faults)}")

        await update.message.reply_text("\n".join(lines))

    except Exception as e:
        logger.error(f"Diagnosis error: {e}")
        await update.message.reply_text(f"Diagnosis failed: {str(e)[:100]}")


# ============================================================================
# Message Handler (Natural Language)
# ============================================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route natural language messages to appropriate handlers."""
    if not is_allowed(update):
        return

    text = update.message.text.lower()

    # Route based on keywords
    if any(kw in text for kw in ["show io", "show me io", "live io", "plc io", "tags"]):
        await cmd_io(update, context)

    elif any(kw in text for kw in ["why", "stopped", "diagnose", "fault", "wrong", "problem"]):
        # Extract question for diagnosis
        context.args = [update.message.text]
        await cmd_diagnose(update, context)

    elif any(kw in text for kw in ["status", "health", "online"]):
        await cmd_status(update, context)

    elif any(kw in text for kw in ["help", "command", "what can"]):
        await cmd_help(update, context)

    else:
        await update.message.reply_text(
            f'I didn\'t understand: "{update.message.text}"\n\n'
            "Try:\n"
            '  "show me IO" - View live PLC tags\n'
            '  "why is this stopped?" - AI diagnosis\n'
            "  /help - All commands"
        )


# ============================================================================
# Main
# ============================================================================

def main():
    """Start the bot."""
    logger.info("Starting FactoryLM Telegram Bot...")
    logger.info(f"Matrix API: {MATRIX_API}")
    logger.info(f"Demo UI: {DEMO_UI}")
    logger.info(f"Allowed users: {ALLOWED_USERS}")

    # Build application
    app = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("io", cmd_io))
    app.add_handler(CommandHandler("diagnose", cmd_diagnose))

    # Natural language handler (must be last)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Run
    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
