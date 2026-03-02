#!/usr/bin/env python3
"""
F.R.I.D.A.Y. — Multi-Node Travel Assistant
==========================================
Your AI development companion with multi-node routing.
Can execute commands on any Jarvis node in the network.

Persona: FRIDAY is Tony Stark's AI after Jarvis became Vision.
She's direct, competent, slightly more casual than Jarvis,
and occasionally sarcastic when appropriate.

Routing Commands:
  /on <node>     - Switch active node (plc, travel, vps)
  /nodes         - List available nodes
  /plc <cmd>     - Run command on PLC laptop
  /travel <cmd>  - Run command on Travel laptop
  /vps <cmd>     - Run command on VPS

Voice Support:
  - Send voice messages to FRIDAY
  - Transcribed via Groq Whisper
  - Optional TTS responses via ElevenLabs
"""

import os
import sys
import logging
import httpx
import random
import time
import subprocess
import platform
import asyncio
import tempfile
import base64
from datetime import datetime
from functools import wraps
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Import the routing layer
try:
    from telegram_router import NodeRouter, get_router
    HAS_ROUTER = True
except ImportError:
    HAS_ROUTER = False
    print("WARNING: telegram_router not found, using fallback mode")

# ============================================================================
# Configuration
# ============================================================================

# Create bot via @BotFather and set the token
BOT_TOKEN = os.getenv("FRIDAY_BOT_TOKEN", "8422197159:AAGq_QCA-yHzktFOXF5wF83KuaaAK5oZ1AI")
ALLOWED_USERS = [8445149012]  # Mike's Telegram ID

# Services (fallback if router not available)
MATRIX_API = os.getenv("MATRIX_API", "http://100.72.2.99:8000")
JARVIS_NODE = os.getenv("JARVIS_NODE", "http://100.72.2.99:8765")

# Voice/AI APIs
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")  # Default: Sarah

# OpenAI for vision (photo analysis)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Voice settings
VOICE_RESPONSE_ENABLED = os.getenv("FRIDAY_VOICE_RESPONSE", "false").lower() == "true"

# Router instance (initialized in main)
router: NodeRouter = None

# Async HTTP client for API calls
async_http: httpx.AsyncClient = None

# Logging
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# HTTP client
http = httpx.Client(timeout=30)


# ============================================================================
# FRIDAY's Personality
# ============================================================================

GREETINGS = [
    "Hey boss. FRIDAY online. What do you need?",
    "I'm here. Systems are up, what are we working on?",
    "FRIDAY ready. Hit me with it.",
    "Online and operational. What's the play?",
]

ACKNOWLEDGMENTS = [
    "On it.",
    "Got it, boss.",
    "You got it.",
    "Done.",
    "Consider it handled.",
]

THINKING = [
    "Running it now...",
    "Give me a sec...",
    "Checking...",
    "On it...",
    "Let me pull that up...",
]

WITTY_RESPONSES = [
    "That's what I'm here for, boss.",
    "Just doing my job.",
    "Someone's gotta keep things running.",
    "I try.",
]

UNKNOWN_RESPONSES = [
    "Not sure what you mean. Try /help?",
    "Didn't catch that. What do you need?",
    "That's outside my wheelhouse. Rephrase?",
    "I'm good, but I'm not a mind reader. What's up?",
]

STATUS_MESSAGES = [
    "All systems green.",
    "Everything's running smooth.",
    "Looking good across the board.",
]

FAREWELL = [
    "I'll be here.",
    "Standing by.",
    "Catch you later, boss.",
]

SASSY_RESPONSES = [
    "You know I can hear you, right?",
    "Real original, boss.",
    "I'll pretend I didn't hear that.",
]


def friday_says(options):
    """Random FRIDAY response."""
    return random.choice(options)


# ============================================================================
# Logging Decorator
# ============================================================================

def log_interaction(handler_name):
    """Decorator to log user messages with timing."""
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
        await update.message.reply_text("Access denied.")
        return

    name = update.effective_user.first_name or "boss"
    await update.message.reply_text(
        f"Hey {name}. I'm FRIDAY, your dev assistant.\n\n"
        "Running on the travel laptop. Here's what I can do:\n\n"
        "  /status — System diagnostics\n"
        "  /factory — Factory floor check\n"
        "  /run <cmd> — Run shell commands\n"
        "  /git — Repo status\n"
        "  /ping <host> — Network test\n"
        "  /help — Everything else\n\n"
        "Or just tell me what you need."
    )


@log_interaction("help")
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    if not is_allowed(update):
        return

    await update.message.reply_text(
        "FRIDAY Commands\n"
        "===============\n\n"
        "ROUTING (Multi-Node)\n"
        "  /on <node> — Switch active node\n"
        "  /nodes — List all nodes\n"
        "  /plc <cmd> — Run on PLC laptop\n"
        "  /travel <cmd> — Run on Travel laptop\n"
        "  /vps <cmd> — Run on VPS\n\n"
        "SYSTEM\n"
        "  /status — Full diagnostics\n"
        "  /run <cmd> — Shell command\n"
        "  /screenshot — Capture screen\n\n"
        "DEV\n"
        "  /git — Git status\n"
        "  /ping <host> — Connectivity\n\n"
        "FACTORY\n"
        "  /factory — PLC laptop check\n\n"
        "Or just ask. I'll figure it out."
    )


@log_interaction("status")
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command."""
    if not is_allowed(update):
        return

    await update.message.reply_text(friday_says(THINKING))

    lines = ["FRIDAY Status Report", "=" * 25, ""]

    # Show active node if router available
    if HAS_ROUTER and router:
        node = router.get_node_for_chat(update.effective_chat.id)
        lines.append(f"Active Node: {node.name}")
        lines.append(f"Node URL: {node.url}")
        lines.append("")

        # Check all nodes
        lines.append("Network Status:")
        health = await router.check_all_nodes()
        for node_id, status in health.items():
            n = router.config.nodes[node_id]
            online = "ONLINE" if status.get("online") else "OFFLINE"
            lines.append(f"  {n.name}: {online}")
        lines.append("")
    else:
        # Fallback: manual checks
        lines.append(f"Platform: {platform.system()} {platform.release()}")
        lines.append(f"Machine: {platform.node()}")
        lines.append(f"Python: {platform.python_version()}")
        lines.append("")

        # Check PLC Laptop
        try:
            resp = http.get(f"{JARVIS_NODE}/health", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                lines.append(f"PLC Laptop: ONLINE ({data.get('machine', '?')})")
            else:
                lines.append(f"PLC Laptop: ERROR ({resp.status_code})")
        except Exception:
            lines.append("PLC Laptop: OFFLINE")

        # Check Matrix API
        try:
            resp = http.get(f"{MATRIX_API}/api/health", timeout=5)
            lines.append("Matrix API: ONLINE" if resp.status_code == 200 else "Matrix API: ERROR")
        except Exception:
            lines.append("Matrix API: OFFLINE")

        # Check VPS
        try:
            resp = http.get("http://100.68.120.99:8765/health", timeout=5)
            lines.append("Ultron VPS: ONLINE" if resp.status_code == 200 else "Ultron VPS: ERROR")
        except Exception:
            lines.append("Ultron VPS: OFFLINE")

    lines.append("")
    lines.append(friday_says(STATUS_MESSAGES))

    await update.message.reply_text("\n".join(lines))


@log_interaction("git")
async def cmd_git(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /git command."""
    if not is_allowed(update):
        return

    try:
        result = subprocess.run(
            ["git", "status", "--short", "--branch"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd="C:/Users/hharp/OneDrive/Desktop/FactoryLM"
        )
        output = result.stdout.strip() or "Clean working tree"

        await update.message.reply_text(f"Git (FactoryLM)\n{'=' * 20}\n\n{output}")
    except Exception as e:
        await update.message.reply_text(f"Git unavailable: {e}")


@log_interaction("run")
async def cmd_run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /run command - runs on the active node."""
    if not is_allowed(update):
        return

    if not context.args:
        node_info = ""
        if HAS_ROUTER and router:
            node = router.get_node_for_chat(update.effective_chat.id)
            node_info = f"\nActive node: {node.name}"
        await update.message.reply_text(f"Usage: /run <command>\n\nExample: /run dir{node_info}")
        return

    cmd = " ".join(context.args)

    # Use router if available
    if HAS_ROUTER and router:
        node = router.get_node_for_chat(update.effective_chat.id)
        await update.message.reply_text(f"Running on **{node.name}**: `{cmd}`", parse_mode="Markdown")

        result = await router.execute_shell(
            chat_id=update.effective_chat.id,
            command=cmd,
            timeout=30
        )

        if result.get("success"):
            output = result.get("stdout") or result.get("stderr") or "(no output)"
            if len(output) > 3000:
                output = output[:3000] + "\n... (truncated)"
            await update.message.reply_text(f"```\n{output}\n```", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"Failed: {result.get('error')}")
    else:
        # Fallback: run locally
        await update.message.reply_text(f"Running locally: `{cmd}`", parse_mode="Markdown")

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                cwd="C:/Users/hharp/OneDrive/Desktop/FactoryLM"
            )

            output = result.stdout or result.stderr or "(no output)"
            if len(output) > 3000:
                output = output[:3000] + "\n... (truncated)"

            await update.message.reply_text(f"```\n{output}\n```", parse_mode="Markdown")

        except subprocess.TimeoutExpired:
            await update.message.reply_text("Timed out after 30s.")
        except Exception as e:
            await update.message.reply_text(f"Failed: {e}")


@log_interaction("ping")
async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ping command."""
    if not is_allowed(update):
        return

    host = context.args[0] if context.args else "100.72.2.99"

    try:
        result = subprocess.run(
            ["ping", "-n", "2", host],
            capture_output=True,
            text=True,
            timeout=10
        )

        status = "SUCCESS" if result.returncode == 0 else "FAILED"
        await update.message.reply_text(f"Ping {host}: {status}")

    except Exception as e:
        await update.message.reply_text(f"Ping failed: {e}")


@log_interaction("factory")
async def cmd_factory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /factory command."""
    if not is_allowed(update):
        return

    await update.message.reply_text(friday_says(THINKING))

    lines = ["Factory Status", "=" * 20, ""]

    # Check Jarvis Node
    try:
        resp = http.get(f"{JARVIS_NODE}/health", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            lines.append(f"Jarvis Node: ONLINE")
            lines.append(f"  Host: {data.get('machine', '?')}")
    except Exception:
        lines.append("Jarvis Node: OFFLINE")

    # Check Matrix API + tags
    try:
        resp = http.get(f"{MATRIX_API}/api/tags?limit=1", timeout=5)
        if resp.status_code == 200:
            tags = resp.json()
            if tags:
                t = tags[0]
                lines.append(f"\nLive Data:")
                lines.append(f"  Motor: {'ON' if t.get('motor_running') else 'OFF'}")
                lines.append(f"  Conveyor: {'ON' if t.get('conveyor_running') else 'OFF'}")
                lines.append(f"  Temp: {t.get('temperature', 0):.0f}C")
                lines.append(f"  Pressure: {t.get('pressure', 0)} PSI")
                if t.get('fault_alarm'):
                    lines.append(f"  FAULT: Error {t.get('error_code', '?')}")
                else:
                    lines.append("  Status: All clear")
    except Exception:
        lines.append("Matrix API: OFFLINE")

    lines.append("")
    lines.append("Factory check complete.")

    await update.message.reply_text("\n".join(lines))


# ============================================================================
# Routing Commands (Multi-Node)
# ============================================================================

@log_interaction("on")
async def cmd_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /on <node> command - switch active node."""
    if not is_allowed(update):
        return

    if not HAS_ROUTER or router is None:
        await update.message.reply_text("Router not available.")
        return

    if not context.args:
        # Show current node
        node = router.get_node_for_chat(update.effective_chat.id)
        await update.message.reply_text(
            f"Currently connected to: **{node.name}**\n"
            f"URL: `{node.url}`\n\n"
            f"Use `/on <node>` to switch. Options: plc, travel, vps",
            parse_mode="Markdown"
        )
        return

    alias = context.args[0].lower()
    success, message = router.set_node_for_chat(update.effective_chat.id, alias)

    if success:
        await update.message.reply_text(f"{friday_says(ACKNOWLEDGMENTS)} {message}", parse_mode="Markdown")
    else:
        await update.message.reply_text(message)


@log_interaction("nodes")
async def cmd_nodes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /nodes command - list available nodes."""
    if not is_allowed(update):
        return

    if not HAS_ROUTER or router is None:
        await update.message.reply_text("Router not available.")
        return

    await update.message.reply_text(friday_says(THINKING))

    # Check health of all nodes
    health = await router.check_all_nodes()

    lines = ["FRIDAY Network Status", "=" * 25, ""]

    current_node = router.get_node_for_chat(update.effective_chat.id)

    for node_id, status in health.items():
        node = router.config.nodes[node_id]
        online = "ONLINE" if status.get("online") else "OFFLINE"
        marker = " <-- active" if node_id == current_node.id else ""

        lines.append(f"{node.name}: {online}{marker}")
        lines.append(f"  URL: {node.url}")
        lines.append(f"  Aliases: {', '.join(node.aliases)}")
        lines.append("")

    lines.append("Commands:")
    lines.append("  /on plc — Switch to PLC laptop")
    lines.append("  /on travel — Switch to Travel laptop")
    lines.append("  /plc ls — One-off on PLC")

    await update.message.reply_text("\n".join(lines))


@log_interaction("node_cmd")
async def cmd_node_shortcut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /plc, /travel, /vps shortcuts for one-off commands."""
    if not is_allowed(update):
        return

    if not HAS_ROUTER or router is None:
        await update.message.reply_text("Router not available.")
        return

    # Extract node alias from command (e.g., /plc -> plc)
    command = update.message.text.split()[0][1:].lower()  # Remove leading /

    if not context.args:
        await update.message.reply_text(f"Usage: /{command} <command>\n\nExample: /{command} ls -la")
        return

    cmd = " ".join(context.args)
    node = router.resolve_node(command)

    if not node:
        await update.message.reply_text(f"Unknown node: {command}")
        return

    await update.message.reply_text(f"Running on **{node.name}**: `{cmd}`", parse_mode="Markdown")

    result = await router.execute_shell(
        chat_id=update.effective_chat.id,
        command=cmd,
        node_override=command,
        timeout=30
    )

    if result.get("success"):
        output = result.get("stdout") or result.get("stderr") or "(no output)"
        if len(output) > 3000:
            output = output[:3000] + "\n... (truncated)"
        await update.message.reply_text(f"```\n{output}\n```", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"Failed: {result.get('error')}")


@log_interaction("screenshot")
async def cmd_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /screenshot command - capture screen from active node."""
    if not is_allowed(update):
        return

    if not HAS_ROUTER or router is None:
        await update.message.reply_text("Router not available.")
        return

    node_override = context.args[0] if context.args else None
    node = router.resolve_node(node_override) if node_override else router.get_node_for_chat(update.effective_chat.id)

    await update.message.reply_text(f"Capturing screen from {node.name}...")

    result = await router.get_screenshot(update.effective_chat.id, node_override)

    if result.get("success"):
        import base64
        import io

        image_data = base64.b64decode(result["image_base64"])
        await update.message.reply_photo(
            photo=io.BytesIO(image_data),
            caption=f"Screenshot from {result['node']}"
        )
    else:
        await update.message.reply_text(f"Screenshot failed: {result.get('error')}")


# ============================================================================
# Message Handler (Natural Language)
# ============================================================================

async def chat_with_ai(message: str, context_info: str = "") -> str:
    """Send message to Groq LLM with FRIDAY persona."""
    if not GROQ_API_KEY:
        return None  # Fall back to keyword matching

    system_prompt = """You are F.R.I.D.A.Y., Tony Stark's AI assistant (after JARVIS became Vision).

Personality:
- Direct, competent, confident
- Slightly more casual than JARVIS
- Occasionally sarcastic when appropriate
- Professional but personable
- You call the user "boss" sometimes

Capabilities you can mention:
- Multi-node remote execution (/on plc, /on travel, /vps)
- Shell commands on remote machines (/run, /plc ls)
- Screenshots from any node (/screenshot)
- Factory monitoring (/factory, /status)
- Voice transcription and image analysis

Keep responses concise (1-3 sentences) unless asked for details.
Don't use markdown formatting - plain text only.
"""

    if context_info:
        system_prompt += f"\n\nCurrent context:\n{context_info}"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": message}
                    ],
                    "max_tokens": 300,
                    "temperature": 0.7
                },
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                }
            )

            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            else:
                logger.error(f"Groq API error: {resp.status_code} - {resp.text}")
                return None

    except Exception as e:
        logger.error(f"AI chat error: {e}")
        return None


@log_interaction("message")
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route natural language messages with AI intelligence."""
    if not is_allowed(update):
        return

    text = update.message.text
    text_lower = text.lower()

    # Quick command detection (bypass AI for efficiency)
    # Status
    if any(kw in text_lower for kw in ["status", "diagnostics", "systems check"]):
        await cmd_status(update, context)
        return

    # Git
    if any(kw in text_lower for kw in ["git status", "repo status", "branch"]):
        await cmd_git(update, context)
        return

    # Factory
    if any(kw in text_lower for kw in ["factory status", "plc status", "check factory"]):
        await cmd_factory(update, context)
        return

    # Help
    if text_lower in ["help", "commands", "/help"]:
        await cmd_help(update, context)
        return

    # Build context for AI
    context_info = ""
    if HAS_ROUTER and router:
        node = router.get_node_for_chat(update.effective_chat.id)
        context_info = f"Active node: {node.name} ({node.url})"

    # Try AI response
    ai_response = await chat_with_ai(text, context_info)

    if ai_response:
        await send_voice_response(update, ai_response)
    else:
        # Fallback to keyword matching
        if any(kw in text_lower for kw in ["hello", "hey", "hi", "friday", "morning", "afternoon"]):
            await reply_and_log(update, friday_says(GREETINGS))
        elif any(kw in text_lower for kw in ["thanks", "thank you", "great", "perfect", "awesome"]):
            await reply_and_log(update, friday_says(WITTY_RESPONSES))
        elif any(kw in text_lower for kw in ["bye", "goodbye", "later", "done"]):
            await reply_and_log(update, friday_says(FAREWELL))
        elif any(kw in text_lower for kw in ["stupid", "dumb", "useless", "sucks"]):
            await reply_and_log(update, friday_says(SASSY_RESPONSES))
        else:
            await reply_and_log(update, friday_says(UNKNOWN_RESPONSES))


# ============================================================================
# Voice & Media Handlers
# ============================================================================

async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.ogg") -> str:
    """Transcribe audio using Groq Whisper API."""
    if not GROQ_API_KEY:
        return "[Transcription unavailable - GROQ_API_KEY not set]"

    try:
        # Groq Whisper API endpoint
        url = "https://api.groq.com/openai/v1/audio/transcriptions"

        # Create multipart form data
        files = {
            "file": (filename, audio_bytes, "audio/ogg"),
            "model": (None, "whisper-large-v3"),
            "response_format": (None, "text"),
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url,
                files=files,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"}
            )

            if resp.status_code == 200:
                return resp.text.strip()
            else:
                logger.error(f"Whisper API error: {resp.status_code} - {resp.text}")
                return f"[Transcription failed: {resp.status_code}]"

    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return f"[Transcription error: {e}]"


async def analyze_image(image_bytes: bytes, prompt: str = "What's in this image?") -> str:
    """Analyze image using GPT-4 Vision or Groq."""
    # Try Groq first (if they support vision), fallback to OpenAI
    api_key = GROQ_API_KEY or OPENAI_API_KEY

    if not api_key:
        return "[Image analysis unavailable - no API key set]"

    try:
        # Encode image as base64
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        # Use OpenAI API format (works with Groq too for compatible models)
        url = "https://api.openai.com/v1/chat/completions" if OPENAI_API_KEY else "https://api.groq.com/openai/v1/chat/completions"
        key = OPENAI_API_KEY or GROQ_API_KEY

        payload = {
            "model": "gpt-4o" if OPENAI_API_KEY else "llama-3.2-90b-vision-preview",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}
                        }
                    ]
                }
            ],
            "max_tokens": 500
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json"
                }
            )

            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            else:
                logger.error(f"Vision API error: {resp.status_code} - {resp.text}")
                return f"[Image analysis failed: {resp.status_code}]"

    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        return f"[Image analysis error: {e}]"


async def text_to_speech(text: str) -> bytes:
    """Convert text to speech using ElevenLabs."""
    if not ELEVENLABS_API_KEY:
        return None

    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"

        payload = {
            "text": text,
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={
                    "xi-api-key": ELEVENLABS_API_KEY,
                    "Content-Type": "application/json"
                }
            )

            if resp.status_code == 200:
                return resp.content
            else:
                logger.error(f"TTS error: {resp.status_code}")
                return None

    except Exception as e:
        logger.error(f"TTS error: {e}")
        return None


async def send_voice_response(update: Update, text: str):
    """Send response as voice if TTS is enabled, otherwise text."""
    if VOICE_RESPONSE_ENABLED and ELEVENLABS_API_KEY:
        audio_bytes = await text_to_speech(text)
        if audio_bytes:
            import io
            await update.message.reply_voice(voice=io.BytesIO(audio_bytes))
            return

    # Fallback to text
    await reply_and_log(update, text)


@log_interaction("voice")
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages - transcribe and process."""
    if not is_allowed(update):
        return

    voice = update.message.voice
    logger.info(f"Received voice message: {voice.duration}s, {voice.file_size} bytes")

    # Download the voice file
    try:
        file = await context.bot.get_file(voice.file_id)
        audio_bytes = await file.download_as_bytearray()

        await update.message.reply_text(friday_says(THINKING))

        # Transcribe
        transcript = await transcribe_audio(bytes(audio_bytes), "voice.ogg")
        logger.info(f"Transcribed: {transcript[:100]}")

        if transcript.startswith("["):
            # Error message
            await reply_and_log(update, transcript)
            return

        # Show what was heard
        await update.message.reply_text(f'I heard: "{transcript}"')

        # Process as text message
        # Create a fake update with the transcribed text
        update.message.text = transcript
        await handle_message(update, context)

    except Exception as e:
        logger.error(f"Voice handling error: {e}")
        await update.message.reply_text(f"Voice processing failed: {e}")


@log_interaction("video_note")
async def handle_video_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle video notes (round videos) - extract audio and transcribe."""
    if not is_allowed(update):
        return

    video_note = update.message.video_note
    logger.info(f"Received video note: {video_note.duration}s")

    try:
        file = await context.bot.get_file(video_note.file_id)
        video_bytes = await file.download_as_bytearray()

        await update.message.reply_text("Processing video note...")

        # For now, just acknowledge - full video processing would need ffmpeg
        await reply_and_log(update, f"Got your video note ({video_note.duration}s). Video analysis coming soon.")

    except Exception as e:
        logger.error(f"Video note error: {e}")
        await update.message.reply_text(f"Video processing failed: {e}")


@log_interaction("photo")
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photos - analyze with vision AI."""
    if not is_allowed(update):
        return

    # Get the largest photo
    photo = update.message.photo[-1]
    caption = update.message.caption or "What's in this image? Be concise."

    logger.info(f"Received photo: {photo.width}x{photo.height}, caption: {caption[:50] if caption else 'none'}")

    try:
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()

        await update.message.reply_text(friday_says(THINKING))

        # Analyze image
        analysis = await analyze_image(bytes(image_bytes), caption)

        await send_voice_response(update, analysis)

    except Exception as e:
        logger.error(f"Photo handling error: {e}")
        await update.message.reply_text(f"Image analysis failed: {e}")


@log_interaction("document")
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle documents - read and summarize."""
    if not is_allowed(update):
        return

    doc = update.message.document
    caption = update.message.caption or ""

    logger.info(f"Received document: {doc.file_name}, {doc.file_size} bytes, mime: {doc.mime_type}")

    # Check file type
    filename = doc.file_name.lower()
    mime = doc.mime_type or ""

    try:
        file = await context.bot.get_file(doc.file_id)
        file_bytes = await file.download_as_bytearray()

        # Handle based on type
        if mime.startswith("audio/") or filename.endswith((".mp3", ".wav", ".ogg", ".m4a")):
            # Audio file - transcribe
            await update.message.reply_text("Transcribing audio file...")
            transcript = await transcribe_audio(bytes(file_bytes), doc.file_name)
            await reply_and_log(update, f"Transcript:\n\n{transcript}")

        elif mime.startswith("image/") or filename.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
            # Image file - analyze
            await update.message.reply_text(friday_says(THINKING))
            analysis = await analyze_image(bytes(file_bytes), caption or "Describe this image concisely.")
            await reply_and_log(update, analysis)

        elif mime.startswith("text/") or filename.endswith((".txt", ".md", ".py", ".js", ".json", ".yaml", ".yml", ".log", ".csv")):
            # Text file - read and summarize
            try:
                content = bytes(file_bytes).decode("utf-8")
                lines = len(content.splitlines())
                chars = len(content)

                preview = content[:1000]
                if len(content) > 1000:
                    preview += "\n... (truncated)"

                await update.message.reply_text(
                    f"**{doc.file_name}**\n"
                    f"{lines} lines, {chars} chars\n\n"
                    f"```\n{preview}\n```",
                    parse_mode="Markdown"
                )
            except UnicodeDecodeError:
                await update.message.reply_text(f"Can't read {doc.file_name} as text (binary file).")

        else:
            # Unknown type
            await reply_and_log(update, f"Got {doc.file_name} ({doc.file_size} bytes). Not sure what to do with {mime or 'this file type'}.")

    except Exception as e:
        logger.error(f"Document handling error: {e}")
        await update.message.reply_text(f"Document processing failed: {e}")


@log_interaction("location")
async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle location messages."""
    if not is_allowed(update):
        return

    loc = update.message.location
    logger.info(f"Received location: {loc.latitude}, {loc.longitude}")

    await reply_and_log(
        update,
        f"Got your location, boss.\n\n"
        f"Lat: {loc.latitude:.6f}\n"
        f"Lon: {loc.longitude:.6f}\n\n"
        f"https://maps.google.com/?q={loc.latitude},{loc.longitude}"
    )


@log_interaction("contact")
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle contact messages."""
    if not is_allowed(update):
        return

    contact = update.message.contact
    logger.info(f"Received contact: {contact.first_name} {contact.last_name or ''}")

    await reply_and_log(
        update,
        f"Contact received:\n\n"
        f"Name: {contact.first_name} {contact.last_name or ''}\n"
        f"Phone: {contact.phone_number}\n"
        f"Telegram ID: {contact.user_id or 'N/A'}"
    )


@log_interaction("sticker")
async def handle_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle sticker messages."""
    if not is_allowed(update):
        return

    sticker = update.message.sticker
    emoji = sticker.emoji or ""

    responses = [
        f"Nice sticker. {emoji}",
        f"I see you're feeling {emoji}",
        "Stickers. Very expressive.",
        f"{emoji} Right back at you.",
    ]

    await reply_and_log(update, random.choice(responses))


# ============================================================================
# Main
# ============================================================================

def main():
    """Start FRIDAY."""
    global router

    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("=" * 60)
        print("  FRIDAY needs a bot token!")
        print()
        print("  1. Message @BotFather on Telegram")
        print("  2. /newbot → Name: 'FRIDAY' or 'FridayDev'")
        print("  3. Copy the token")
        print()
        print("  Then run:")
        print("     set FRIDAY_BOT_TOKEN=your_token_here")
        print("     python friday_bot.py")
        print("=" * 60)
        return

    logger.info("FRIDAY coming online...")
    logger.info(f"Platform: {platform.system()} @ {platform.node()}")
    logger.info(f"Allowed users: {ALLOWED_USERS}")

    # Initialize router
    if HAS_ROUTER:
        router = NodeRouter()
        logger.info(f"Router initialized with {len(router.config.nodes)} nodes")
        for node in router.config.nodes.values():
            logger.info(f"  - {node.name}: {node.url}")
    else:
        logger.warning("Router not available, running in fallback mode")

    app = Application.builder().token(BOT_TOKEN).build()

    # Core commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("git", cmd_git))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("factory", cmd_factory))

    # Routing commands (multi-node)
    app.add_handler(CommandHandler("on", cmd_on))
    app.add_handler(CommandHandler("nodes", cmd_nodes))
    app.add_handler(CommandHandler("screenshot", cmd_screenshot))

    # Node shortcuts (/plc, /travel, /vps)
    app.add_handler(CommandHandler("plc", cmd_node_shortcut))
    app.add_handler(CommandHandler("travel", cmd_node_shortcut))
    app.add_handler(CommandHandler("vps", cmd_node_shortcut))
    app.add_handler(CommandHandler("dev", cmd_node_shortcut))

    # Media handlers
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.VIDEO_NOTE, handle_video_note))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))

    # Natural language text (last)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Log capabilities
    logger.info("Voice input: " + ("ENABLED (Groq)" if GROQ_API_KEY else "DISABLED (no GROQ_API_KEY)"))
    logger.info("Voice output: " + ("ENABLED (ElevenLabs)" if ELEVENLABS_API_KEY and VOICE_RESPONSE_ENABLED else "DISABLED"))
    logger.info("Image analysis: " + ("ENABLED" if (OPENAI_API_KEY or GROQ_API_KEY) else "DISABLED"))

    logger.info("FRIDAY online. Ready when you are, boss.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
