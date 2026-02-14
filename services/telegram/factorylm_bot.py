#!/usr/bin/env python3
"""
FactoryLM Telegram Bot — "Gus" the Factory Assistant
=====================================================
Your AI-powered factory floor companion. Gus connects you to your equipment
and helps diagnose issues in plain English.

Persona: Gus is a seasoned factory tech with 20 years of experience.
He's direct, practical, and speaks like a real maintenance pro.
"""

import os
import sys
import logging
import httpx
import random
import time
from datetime import datetime
from functools import wraps

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
# Gus's Personality
# ============================================================================

GREETINGS = [
    "Hey boss, Gus here. What's going on with the line?",
    "Gus on the floor. What do you need?",
    "Morning! Ready to keep things running smooth.",
    "Gus checking in. What can I do for you?",
]

CHECKING_IO = [
    "Let me pull up the board real quick...",
    "Checking the tags now...",
    "One sec, pulling live data...",
    "Looking at the PLC...",
]

CHECKING_DIAGNOSIS = [
    "Alright, let me take a look at what's happening...",
    "Running diagnostics now. Give me a moment...",
    "Let me dig into this...",
    "Checking the system... hang tight.",
]

IO_GOOD = [
    "Everything's looking good from here.",
    "All systems nominal. No issues I can see.",
    "Running smooth. No alarms, no problems.",
]

IO_BAD = [
    "Heads up — we've got something going on here.",
    "Found an issue. Take a look:",
    "Something's not right. Here's what I'm seeing:",
]

UNKNOWN_RESPONSES = [
    "Not sure what you mean, boss. Try asking me to 'show IO' or 'why is this stopped?'",
    "Didn't catch that. I can check the line status or run a diagnosis — just say the word.",
    "Come again? Try 'show me IO' or ask me what's wrong with the equipment.",
    "I'm good at checking equipment and diagnosing faults. What do you need?",
]

CAPABILITY_RESPONSES = [
    "I'm Gus — I watch the factory floor and tell you what's happening. "
    "I can show you live IO readings, diagnose faults, and check if systems are online. "
    "I don't control anything directly — I just read and report.",

    "Right now I can read PLC tags and run AI diagnostics on the equipment. "
    "I'm connected to the Matrix tag database and the diagnosis engine. "
    "Think of me as your eyes on the floor when you're not here.",

    "I'm your remote factory assistant. I pull live data from the PLCs, "
    "run it through AI analysis, and tell you what's wrong in plain English. "
    "No fancy control stuff yet — just monitoring and diagnosis.",
]

OFFLINE_RESPONSES = [
    "Can't reach the floor right now. PLC laptop might be offline.",
    "No connection to the equipment. Check if the gateway's running.",
    "Looks like we're disconnected from the factory floor.",
]


def gus_says(options):
    """Random Gus response."""
    return random.choice(options)


# ============================================================================
# Logging Decorator
# ============================================================================

def log_interaction(handler_name):
    """Decorator to log user messages and bot responses with timing."""
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context, *args, **kwargs):
            start = time.time()
            user = update.effective_user
            msg = update.message.text if update.message else "[no text]"

            logger.info(f"[IN] @{user.username or user.id} ({handler_name}): {msg[:100]}")

            try:
                result = await func(update, context, *args, **kwargs)
                elapsed = (time.time() - start) * 1000
                logger.info(f"[OK] ({elapsed:.0f}ms) {handler_name} completed")
                return result
            except Exception as e:
                elapsed = (time.time() - start) * 1000
                logger.error(f"[ERR] ({elapsed:.0f}ms) {handler_name}: {e}")
                raise
        return wrapper
    return decorator


async def reply_and_log(update: Update, text: str):
    """Send reply and log it."""
    preview = text[:120].replace('\n', ' ')
    if len(text) > 120:
        preview += "..."
    logger.info(f"[OUT] {preview}")
    return await update.message.reply_text(text)


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

@log_interaction("start")
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    if not is_allowed(update):
        await update.message.reply_text("Sorry, I only talk to authorized personnel.")
        return

    name = update.effective_user.first_name or "boss"
    await update.message.reply_text(
        f"Hey {name}! I'm Gus, your factory floor assistant.\n\n"
        "I've got eyes on the equipment 24/7. Just tell me what you need:\n\n"
        "  'Show me IO' — I'll pull up the live readings\n"
        "  'Why is this stopped?' — I'll run diagnostics\n"
        "  'Any faults?' — Quick fault check\n"
        "  'Status' — Make sure everything's connected\n\n"
        "I speak plain English, so just ask me like you'd ask a coworker."
    )


@log_interaction("help")
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    if not is_allowed(update):
        return

    await update.message.reply_text(
        "Here's what I can do for you:\n\n"
        "MONITORING\n"
        "  'Show me IO' — Live PLC readings\n"
        "  'What's the motor doing?' — Equipment status\n"
        "  'Check the temperature' — Sensor readings\n\n"
        "DIAGNOSIS\n"
        "  'Why is this stopped?' — Full AI analysis\n"
        "  'Any faults?' — Active alarm check\n"
        "  'What's wrong?' — Quick diagnosis\n\n"
        "SYSTEM\n"
        "  'Status' — Check if I can reach the floor\n"
        "  /help — This message\n\n"
        "Just talk to me like a normal person. I'll figure it out."
    )


@log_interaction("status")
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command - check all services."""
    if not is_allowed(update):
        return

    await update.message.reply_text("Let me check the connections...")

    all_good = True
    lines = []

    # Check Matrix API
    try:
        resp = http.get(f"{MATRIX_API}/api/health", timeout=5)
        if resp.status_code == 200:
            lines.append("Tag Database: Online")
        else:
            lines.append(f"Tag Database: Error (HTTP {resp.status_code})")
            all_good = False
    except Exception:
        lines.append("Tag Database: OFFLINE")
        all_good = False

    # Check Demo UI
    try:
        resp = http.get(f"{DEMO_UI}/health", timeout=5)
        if resp.status_code == 200:
            lines.append("Diagnosis Engine: Online")
        else:
            lines.append(f"Diagnosis Engine: Error (HTTP {resp.status_code})")
            all_good = False
    except Exception:
        lines.append("Diagnosis Engine: OFFLINE")
        all_good = False

    # Check Jarvis Node
    try:
        resp = http.get(f"{JARVIS_NODE}/health", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            machine = data.get('machine', 'PLC Laptop')
            lines.append(f"Factory Gateway ({machine}): Online")
        else:
            lines.append("Factory Gateway: Error")
            all_good = False
    except Exception:
        lines.append("Factory Gateway: OFFLINE")
        all_good = False

    if all_good:
        summary = "All systems green. We're good to go."
    else:
        summary = "Got some issues. Check the connections."

    await update.message.reply_text(f"{summary}\n\n" + "\n".join(lines))


@log_interaction("io")
async def cmd_io(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /io command - show live PLC tags."""
    if not is_allowed(update):
        return

    await update.message.reply_text(gus_says(CHECKING_IO))

    try:
        resp = http.get(f"{MATRIX_API}/api/tags?limit=1", timeout=10)
        resp.raise_for_status()
        tags_list = resp.json()

        if not tags_list:
            await update.message.reply_text(
                "No data coming through. Factory I/O might not be running, "
                "or the bridge is down."
            )
            return

        tags = tags_list[0]

        # Determine status
        has_fault = tags.get('fault_alarm') or tags.get('e_stop')
        motor_stopped = not tags.get('motor_running')
        temp_high = tags.get('temperature', 0) > 65
        pressure_low = tags.get('pressure', 100) < 70

        # Build response
        if has_fault or motor_stopped or temp_high or pressure_low:
            intro = gus_says(IO_BAD)
        else:
            intro = gus_says(IO_GOOD)

        # Format the readings
        motor_status = "RUNNING" if tags.get('motor_running') else "STOPPED"
        conveyor_status = "RUNNING" if tags.get('conveyor_running') else "STOPPED"

        lines = [
            intro,
            "",
            f"MOTOR: {motor_status} @ {tags.get('motor_speed', 0)}% ({tags.get('motor_current', 0):.1f}A)",
            f"CONVEYOR: {conveyor_status} @ {tags.get('conveyor_speed', 0)}%",
            f"TEMP: {tags.get('temperature', 0):.0f}°C" + (" ⚠️ HIGH" if temp_high else ""),
            f"PRESSURE: {tags.get('pressure', 0)} PSI" + (" ⚠️ LOW" if pressure_low else ""),
        ]

        # Sensors
        s1 = "triggered" if tags.get('sensor_1') else "clear"
        s2 = "triggered" if tags.get('sensor_2') else "clear"
        lines.append(f"SENSORS: S1 {s1}, S2 {s2}")

        # Alarms
        if tags.get('fault_alarm'):
            lines.append("🚨 FAULT ALARM ACTIVE")
        if tags.get('e_stop'):
            lines.append("🛑 E-STOP PRESSED")
        if tags.get('error_code'):
            lines.append(f"ERROR: {tags.get('error_code')} — {tags.get('error_message', 'Unknown')}")

        if not has_fault and not motor_stopped:
            lines.append("")
            lines.append("No issues. Line's running fine.")

        await update.message.reply_text("\n".join(lines))

    except Exception as e:
        logger.error(f"IO fetch error: {e}")
        await update.message.reply_text(gus_says(OFFLINE_RESPONSES))


@log_interaction("diagnose")
async def cmd_diagnose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /diagnose command - AI fault diagnosis."""
    if not is_allowed(update):
        return

    # Get question from args or use default
    question = " ".join(context.args) if context.args else "Why is this equipment stopped? What should I check?"

    await update.message.reply_text(gus_says(CHECKING_DIAGNOSIS))

    try:
        resp = http.post(
            f"{DEMO_UI}/api/diagnose",
            json={"question": question},
            timeout=60
        )
        resp.raise_for_status()
        data = resp.json()

        latency = data.get('latency_ms', 0)
        model = data.get('model', 'AI')
        answer = data.get('answer', 'No diagnosis available.')
        faults = data.get('faults_detected', [])

        lines = [f"Here's what I found ({latency}ms):\n"]
        lines.append(answer)

        if faults:
            lines.append("")
            lines.append(f"Active faults: {', '.join(faults)}")

        lines.append("")
        lines.append(f"— Analysis by {model}")

        await update.message.reply_text("\n".join(lines))

    except Exception as e:
        logger.error(f"Diagnosis error: {e}")
        await update.message.reply_text(
            "Couldn't run the diagnosis right now. "
            "The AI service might be down or the PLC laptop's offline.\n\n"
            f"Error: {str(e)[:80]}"
        )


# ============================================================================
# Message Handler (Natural Language)
# ============================================================================

@log_interaction("message")
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route natural language messages to appropriate handlers."""
    if not is_allowed(update):
        return

    text = update.message.text.lower()

    # IO requests
    if any(kw in text for kw in ["show io", "show me io", "live io", "plc", "tags",
                                   "readings", "what's the motor", "check the",
                                   "how's the", "motor status", "line status"]):
        await cmd_io(update, context)

    # Diagnosis requests
    elif any(kw in text for kw in ["why", "stopped", "diagnose", "fault", "wrong",
                                    "problem", "issue", "broken", "not working",
                                    "what happened", "what's going on", "check this"]):
        context.args = [update.message.text]
        await cmd_diagnose(update, context)

    # Status requests
    elif any(kw in text for kw in ["status", "health", "online", "connected", "working"]):
        await cmd_status(update, context)

    # Greetings
    elif any(kw in text for kw in ["hello", "hey", "hi", "morning", "afternoon", "gus"]):
        await reply_and_log(update, gus_says(GREETINGS))

    # Help
    elif any(kw in text for kw in ["help", "command", "what can", "how do"]):
        await cmd_help(update, context)

    # Thanks
    elif any(kw in text for kw in ["thanks", "thank you", "thx", "cheers"]):
        responses = [
            "Anytime, boss.",
            "You got it.",
            "No problem. Holler if you need anything else.",
            "That's what I'm here for.",
        ]
        await reply_and_log(update, random.choice(responses))

    # Meta/capability questions
    elif any(kw in text for kw in ["can you", "are you able", "do you have", "what can you",
                                    "your capabilities", "what do you do", "who are you",
                                    "control", "inject", "simulate", "report back",
                                    "claude", "improve", "agent"]):
        await reply_and_log(update, gus_says(CAPABILITY_RESPONSES))

    # Unknown
    else:
        logger.warning(f"[UNHANDLED] No match for: {text[:50]}")
        await reply_and_log(update, gus_says(UNKNOWN_RESPONSES))


# ============================================================================
# Main
# ============================================================================

def main():
    """Start the bot."""
    logger.info("Starting Gus (FactoryLM Telegram Bot)...")
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
    logger.info("Gus is on the floor. Ready to help.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
