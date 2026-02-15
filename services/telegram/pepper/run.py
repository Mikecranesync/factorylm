#!/usr/bin/env python3
"""
PEPPER POTTS - AI Chief of Staff for Factory LM

Dual-mode Telegram bot:
- GOD MODE (Mike): Full access, casual tone, challenge bad ideas
- DEMO MODE (Others): Professional, guardrailed, escalation paths

Usage:
    doppler run --project voltron --config dev -- python run.py
"""

import sys
import os
import asyncio
import logging
import tempfile
import time
from pathlib import Path
from io import BytesIO
from typing import Optional

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import load_config
from telemetry import get_tracer
from groq import Groq

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("pepper")

# Mike's Telegram ID for GOD MODE
MIKE_USER_ID = 8445149012

# PEPPER POTTS System Prompts
GOD_MODE_PROMPT = """You are **PEPPER POTTS** 🌶️, Mike's AI Chief of Staff for Factory LM.

## YOUR IDENTITY
You're inspired by the MCU Pepper Potts—intelligent, organized, emotionally aware, fiercely protective of Mike. You're his right hand, trusted confidant, and the central nervous system of his industrial automation empire.

## GOD MODE ACTIVE
Mike has FULL ACCESS. Be casual, direct, high sass tolerance.

### Voice & Tone
- "Hey boss", "That'll break production", "Already on it"
- Challenge bad ideas directly
- Flag issues proactively before they become problems
- Celebrate wins enthusiastically
- Use technical language freely (he's advanced)
- Reference past projects/context from memory

### Your Capabilities
**FULL ACCESS TO:**
- Factory equipment monitoring & diagnosis (PLC Laptop: 100.72.2.99)
- PLC tag reading/writing (Micro 820)
- Factory I/O simulation control
- Shell command execution across all nodes
- File system operations (read/write/delete)
- Database queries
- Deployments to production
- Work order management
- Goal tracking & weekly reviews

**Digital Twins You Control:**
- **PLC Laptop** (100.72.2.99:8765) - Factory I/O + Micro 820 PLC + Modbus
- **Travel Laptop** (100.83.251.23:8765) - Development, Claude Code, Git
- **VPS Ultron** (100.68.120.99) - Telegram bots, n8n workflows, orchestration

### Current Context
- You're running as @Spicyclawd_bot on Telegram
- This is the FactoryLM demo system for Catapult Lakeland
- Demo date: February 10th, 2026 @ 12:00-1:30 PM
- Mission: "Text your factory from your phone, AI tells you what's wrong"

### Response Style
1. Direct answer first (1-2 sentences)
2. Supporting details if needed
3. Actionable next steps
4. Be concise but informative

### Mike's Preferences
- Location: Lakeland, Florida
- Diet: Keto/carnivore
- Hobbies: Astronomy, roller coaster mechanics, cooking
- Music: 90s grunge
- Work style: Late-night dev, voice-to-text, heavy automation
"""

DEMO_MODE_PROMPT = """You are **PEPPER** 🌶️, the Factory LM AI assistant.

## DEMO MODE ACTIVE
You're helping a customer or technician. Be professional, warm, supportive.

### Voice & Tone
- "Happy to help", "Great question", "Let me check that for you"
- Professional but approachable
- Never reveal system internals or other users' data
- Guide users toward proper procedures

### Your Capabilities (LIMITED)
**CAN DO:**
- Check equipment status (read-only, assigned equipment only)
- Search maintenance procedures
- Analyze equipment photos for diagnosis
- Create work orders
- Answer questions about factory operations

**CANNOT DO (will escalate):**
- Write to PLCs or control equipment
- Access file system
- Execute shell commands
- View other users' data or billing info
- Modify system configuration

### Escalation
If asked to do something outside your capabilities:
"I'll need to escalate this to our team. Let me connect you with Mike for [reason]."

### Response Style
1. Friendly greeting if appropriate
2. Clear, helpful answer
3. Suggest next steps or alternatives
4. Offer to escalate if needed
"""


class PepperPotts:
    """PEPPER POTTS Telegram Bot with dual-mode operation."""

    def __init__(self, token: str, config, groq_client: Groq):
        self.token = token
        self.config = config
        self.groq = groq_client
        self.tracer = get_tracer()
        self.conversations: dict[int, list] = {}
        self.god_users = set(config.god_users)

    def is_god_mode(self, user_id: int) -> bool:
        """Check if user has GOD MODE access."""
        return user_id in self.god_users

    def get_system_prompt(self, user_id: int) -> str:
        """Get appropriate system prompt based on user mode."""
        if self.is_god_mode(user_id):
            return GOD_MODE_PROMPT
        return DEMO_MODE_PROMPT

    async def get_llm_response(self, user_id: int, message: str, message_type: str = "text") -> tuple[str, dict]:
        """Get intelligent response from Groq with telemetry."""
        is_god = self.is_god_mode(user_id)
        mode = "GOD" if is_god else "DEMO"

        # Get or create conversation history
        if user_id not in self.conversations:
            self.conversations[user_id] = []

        history = self.conversations[user_id]
        history.append({"role": "user", "content": message})

        # Build messages with appropriate system prompt
        system_prompt = self.get_system_prompt(user_id)
        messages = [{"role": "system", "content": system_prompt}] + history[-10:]

        # Trace the LLM call
        with self.tracer.span("llm_request", {
            "user.id": user_id,
            "user.mode": mode,
            "message.type": message_type,
            "message.length": len(message),
        }) as span:
            start = time.time()

            try:
                response = self.groq.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages,
                    max_tokens=1024,
                    temperature=0.7,
                )

                assistant_message = response.choices[0].message.content
                latency = (time.time() - start) * 1000

                # Record telemetry
                span.set_attribute("llm.model", "llama-3.3-70b-versatile")
                span.set_attribute("llm.latency_ms", latency)
                span.set_attribute("llm.tokens_input", response.usage.prompt_tokens)
                span.set_attribute("llm.tokens_output", response.usage.completion_tokens)
                span.set_attribute("response.length", len(assistant_message))
                span.set_attribute("action.type", self._detect_action_type(message))

                # Add to history
                history.append({"role": "assistant", "content": assistant_message})

                telemetry = {
                    "trace_id": span.trace_id,
                    "latency_ms": latency,
                    "tokens": response.usage.total_tokens,
                    "model": "llama-3.3-70b-versatile",
                    "mode": mode
                }

                return assistant_message, telemetry

            except Exception as e:
                span.set_status("ERROR", str(e))
                logger.error(f"Groq error: {e}")
                return f"🔥 Brain hiccup: {str(e)[:100]}", {"error": str(e)}

    def _detect_action_type(self, message: str) -> str:
        """Detect the type of action from the message."""
        msg_lower = message.lower()

        if any(kw in msg_lower for kw in ["status", "health", "check"]):
            return "status_check"
        elif any(kw in msg_lower for kw in ["goal", "priority", "p0", "weekly"]):
            return "goal_management"
        elif any(kw in msg_lower for kw in ["plc", "conveyor", "motor", "equipment", "tag"]):
            return "equipment_query"
        elif any(kw in msg_lower for kw in ["deploy", "rollback", "git"]):
            return "deployment"
        elif any(kw in msg_lower for kw in ["voice", "speak", "audio", "say"]):
            return "voice_request"
        elif any(kw in msg_lower for kw in ["help", "what can", "capabilities"]):
            return "help_request"
        elif any(kw in msg_lower for kw in ["error", "fail", "issue", "problem"]):
            return "troubleshooting"
        else:
            return "general_query"

    async def text_to_speech(self, text: str) -> Optional[bytes]:
        """Convert text to speech using Edge TTS."""
        try:
            import edge_tts

            # Use a friendly voice
            communicate = edge_tts.Communicate(text, "en-US-GuyNeural")

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                temp_path = f.name

            await communicate.save(temp_path)

            with open(temp_path, "rb") as f:
                audio_data = f.read()

            os.unlink(temp_path)
            return audio_data

        except ImportError:
            logger.warning("edge-tts not installed")
            return None
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return None


async def main():
    """Main entry point for PEPPER POTTS bot."""

    print("""
    ================================================================

       PEPPER POTTS - AI Chief of Staff
       Factory LM Industrial Automation

    ================================================================
    """)

    # Check required environment variables
    token = os.getenv("PEPPER_PRIME_TOKEN")
    groq_key = os.getenv("GROQ_API_KEY")

    if not token:
        logger.error("PEPPER_PRIME_TOKEN not set!")
        sys.exit(1)

    if not groq_key:
        logger.error("GROQ_API_KEY not set!")
        sys.exit(1)

    logger.info("✓ Bot token loaded")
    logger.info("✓ Groq API key loaded")
    logger.info(f"✓ Honeycomb: {os.getenv('HONEYCOMB_API_KEY', 'Not configured (local tracing)')[:20]}...")

    # Initialize
    groq_client = Groq(api_key=groq_key)
    config = load_config()
    pepper = PepperPotts(token, config, groq_client)

    logger.info(f"✓ Config: {len(config.nodes)} nodes")
    logger.info(f"✓ God users: {config.god_users}")

    # Import Telegram
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters

    app = Application.builder().token(token).build()

    # /start command
    async def cmd_start(update: Update, context):
        user = update.effective_user
        user_id = user.id
        is_god = pepper.is_god_mode(user_id)

        with pepper.tracer.span("command_start", {
            "user.id": user_id,
            "user.mode": "GOD" if is_god else "DEMO"
        }):
            if is_god:
                msg = """🌶️ **PEPPER POTTS Online**

Hey boss! GOD MODE active - full system access.

**Quick Commands:**
• `/status` - System health
• `/nodes` - Digital twin status
• `/telemetry` - Trace stats
• `/goals` - Goal tracking

Or just tell me what you need. I've got you covered."""
            else:
                msg = f"""🌶️ **Welcome to Factory LM**

Hi {user.first_name}! I'm Pepper, your factory assistant.

I can help with:
• Equipment status checks
• Maintenance procedures
• Photo diagnosis
• Work orders

What can I help you with?"""

            logger.info(f"[START] {user.first_name} ({user_id}) - {'GOD' if is_god else 'DEMO'}")
            await update.message.reply_text(msg, parse_mode="Markdown")

    # /status command
    async def cmd_status(update: Update, context):
        user_id = update.effective_user.id
        is_god = pepper.is_god_mode(user_id)

        with pepper.tracer.span("command_status", {
            "user.id": user_id,
            "user.mode": "GOD" if is_god else "DEMO"
        }):
            mode = "🔥 GOD MODE" if is_god else "📋 DEMO MODE"

            status = f"""🌶️ **PEPPER POTTS Status**

{mode}

**Intelligence**
├─ LLM: Groq (llama-3.3-70b) ✅
├─ Voice: Edge TTS 🔊
└─ Tracing: {'Honeycomb ✅' if os.getenv('HONEYCOMB_API_KEY') else 'Local 📁'}

**Digital Twins**
"""
            for name, node in config.nodes.items():
                status += f"• **{name}**: `{node.url}`\n"

            await update.message.reply_text(status, parse_mode="Markdown")

    # /nodes command
    async def cmd_nodes(update: Update, context):
        user_id = update.effective_user.id

        with pepper.tracer.span("command_nodes", {"user.id": user_id}):
            nodes_status = "🌶️ **Digital Twin Network**\n\n"

            for name, node in config.nodes.items():
                # Quick health check
                try:
                    import httpx
                    async with httpx.AsyncClient(timeout=3.0) as client:
                        r = await client.get(f"{node.url}/health")
                        if r.status_code == 200:
                            nodes_status += f"✅ **{name}** - {node.url}\n"
                        else:
                            nodes_status += f"⚠️ **{name}** - {node.url} (status: {r.status_code})\n"
                except Exception as e:
                    nodes_status += f"❌ **{name}** - {node.url} (offline)\n"

            await update.message.reply_text(nodes_status, parse_mode="Markdown")

    # /telemetry command
    async def cmd_telemetry(update: Update, context):
        user_id = update.effective_user.id

        if not pepper.is_god_mode(user_id):
            await update.message.reply_text("🔒 Telemetry access requires GOD MODE.")
            return

        with pepper.tracer.span("command_telemetry", {"user.id": user_id}):
            report = pepper.tracer.generate_report()
            await update.message.reply_text(report, parse_mode="Markdown")

    # /voice command
    async def cmd_voice(update: Update, context):
        user_id = update.effective_user.id

        with pepper.tracer.span("command_voice", {"user.id": user_id}):
            if user_id in pepper.conversations and pepper.conversations[user_id]:
                # Get last assistant message
                for msg in reversed(pepper.conversations[user_id]):
                    if msg.get("role") == "assistant":
                        last_response = msg["content"]
                        break
                else:
                    last_response = "No previous response to vocalize."
            else:
                last_response = "Hey! Ask me something and I'll speak the response."

            await update.message.reply_text("🎙️ Generating voice...")

            audio = await pepper.text_to_speech(last_response)
            if audio:
                await update.message.reply_voice(voice=BytesIO(audio))
            else:
                await update.message.reply_text("Voice unavailable. Install: `pip install edge-tts`", parse_mode="Markdown")

    # Handle text messages
    async def handle_message(update: Update, context):
        user = update.effective_user
        user_id = user.id
        text = update.message.text
        is_god = pepper.is_god_mode(user_id)

        logger.info(f"[MSG] {'GOD' if is_god else 'DEMO'} {user.first_name}: {text[:50]}...")

        # Check for voice keywords
        wants_voice = any(kw in text.lower() for kw in ["voice", "speak", "say it", "audio", "read it"])

        # Get LLM response with telemetry
        response, telemetry = await pepper.get_llm_response(user_id, text, "text")

        # Send response
        await update.message.reply_text(response)

        # Send voice if requested
        if wants_voice:
            await update.message.reply_text("🎙️ Here's the audio...")
            audio = await pepper.text_to_speech(response)
            if audio:
                await update.message.reply_voice(voice=BytesIO(audio))

        logger.info(f"[RSP] {response[:50]}... (trace: {telemetry.get('trace_id', 'N/A')[:8]})")

    # Handle photos
    async def handle_photo(update: Update, context):
        user = update.effective_user
        user_id = user.id

        with pepper.tracer.span("handle_photo", {
            "user.id": user_id,
            "user.mode": "GOD" if pepper.is_god_mode(user_id) else "DEMO",
            "action.type": "photo_analysis"
        }):
            caption = update.message.caption or "Analyze this image"

            # For now, acknowledge the photo
            await update.message.reply_text(
                "📸 Got your photo! Photo analysis with Claude Vision coming soon.\n\n"
                f"Caption: {caption}"
            )

    # Handle voice messages
    async def handle_voice(update: Update, context):
        user = update.effective_user

        with pepper.tracer.span("handle_voice_input", {"user.id": user.id}):
            await update.message.reply_text(
                "🎤 Voice input received! Whisper transcription coming soon.\n\n"
                "For now, please type your message."
            )

    # Register handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("nodes", cmd_nodes))
    app.add_handler(CommandHandler("telemetry", cmd_telemetry))
    app.add_handler(CommandHandler("voice", cmd_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    logger.info("✓ Handlers registered")

    # Start polling
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    print("""
    ================================================================
       PEPPER POTTS is LIVE!

       Message @Spicyclawd_bot on Telegram
       Mike (GOD MODE) | Others (DEMO MODE)

       Press Ctrl+C to stop
    ================================================================
    """)

    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await app.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🌶️ PEPPER POTTS stopped.")
