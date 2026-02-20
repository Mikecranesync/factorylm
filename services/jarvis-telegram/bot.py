#!/usr/bin/env python3
"""
Jarvis Telegram Bot — Unified entry point

Combines all three original bot implementations:
- Puppeteer Bot (photo diagnosis, voice, work orders)
- Claude Bridge (text → Claude CLI)
- Management Dashboard (/status, /agents, /metrics)

Usage:
    python bot.py

Environment:
    TELEGRAM_BOT_TOKEN   — Required, from @BotFather
    TELEGRAM_ALLOWED_USERS — Comma-separated user IDs
    GROQ_API_KEY         — For photo/voice/text analysis (Groq)
    CMMS_URL             — Atlas CMMS endpoint
    CMMS_EMAIL           — CMMS login
    CMMS_PASSWORD        — CMMS password
    CLAUDE_WORKSPACE     — Optional, for Claude CLI bridge
    MACHINE_NAME         — Device identifier
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

from aiohttp import web
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from config import TelegramConfig, RateLimiter
from conversation import ConversationManager
from handlers.photo import handle_photo, handle_photo_callback, cmd_wo, cmd_history
from handlers.voice import handle_voice
from handlers.text import handle_text, cmd_clear
from handlers.management import cmd_status, cmd_agents, cmd_metrics
from integrations.claude_bridge import check_claude_available

logger = logging.getLogger(__name__)


async def start(update: Update, context) -> None:
    """Welcome message with all capabilities listed."""
    config = context.bot_data["config"]
    user_id = update.effective_user.id
    if not config.is_user_allowed(user_id):
        await update.message.reply_text("Access denied. Contact admin for access.")
        return

    await update.message.reply_text(
        f"*JARVIS ONLINE* ({config.machine_name})\n\n"
        "Industrial AI Assistant ready.\n\n"
        "*Send:*\n"
        "  Photo — Equipment diagnosis\n"
        "  Voice — Voice command\n"
        "  Text — AI response\n\n"
        "*Commands:*\n"
        "/wo — Create work order from last diagnosis\n"
        "/history — View recent diagnoses\n"
        "/status — System health check\n"
        "/agents — Agent roster\n"
        "/metrics — Performance KPIs\n"
        "/clear — Reset conversation\n\n"
        "_Point. Ask. Fix._",
        parse_mode="Markdown",
    )


async def health_check(request: web.Request) -> web.Response:
    """HTTP health check endpoint for monitoring."""
    return web.json_response({"status": "ok", "service": "jarvis-telegram"})


async def run_health_server(port: int = 8081) -> None:
    """Run a lightweight HTTP server for health checks."""
    app = web.Application()
    app.router.add_get("/health", health_check)
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health check server on port {port}")


def main() -> None:
    # Logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler()],
    )
    # Quiet httpx polling spam (getUpdates every 10s)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Load config
    try:
        config = TelegramConfig.from_env()
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    logger.info(f"Starting Jarvis Telegram Bot ({config.machine_name})")

    # Init conversation manager
    conv = ConversationManager()

    # Init Groq (optional)
    groq = None
    if config.groq_api_key:
        from integrations.groq_client import GroqClient
        groq = GroqClient(config.groq_api_key)
        logger.info("Groq enabled (vision + text + voice)")
    else:
        logger.warning("GROQ_API_KEY not set — photo/voice/text analysis disabled")

    # Init rate limiter
    rate_limiter = RateLimiter(max_per_minute=config.rate_limit)

    # Init CMMS (optional)
    cmms = None
    if config.cmms_url and config.cmms_email and config.cmms_password:
        from integrations.cmms import CMSSClient
        cmms = CMSSClient(config.cmms_url, config.cmms_email, config.cmms_password)
        logger.info(f"CMMS configured: {config.cmms_url}")
    else:
        logger.warning("CMMS not configured — work order creation disabled")

    # Check Claude CLI
    claude_available = check_claude_available()

    # Build Telegram application
    app = Application.builder().token(config.bot_token).build()

    # Store shared state in bot_data
    app.bot_data["config"] = config
    app.bot_data["conversation_manager"] = conv
    app.bot_data["groq"] = groq
    app.bot_data["cmms"] = cmms
    app.bot_data["claude_available"] = claude_available
    app.bot_data["rate_limiter"] = rate_limiter

    # Register handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("wo", cmd_wo))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("agents", cmd_agents))
    app.add_handler(CommandHandler("metrics", cmd_metrics))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_photo_callback))

    # Start health check server in background
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _run() -> None:
        await run_health_server()
        # Graceful shutdown on SIGTERM/SIGINT
        async with app:
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True)
            logger.info("Jarvis Telegram Bot running. Press Ctrl+C to stop.")

            stop_event = asyncio.Event()

            def _signal_handler():
                stop_event.set()

            try:
                loop = asyncio.get_running_loop()
                for sig in (signal.SIGINT, signal.SIGTERM):
                    try:
                        loop.add_signal_handler(sig, _signal_handler)
                    except NotImplementedError:
                        # Windows doesn't support add_signal_handler
                        pass
            except Exception:
                pass

            try:
                await stop_event.wait()
            except (KeyboardInterrupt, SystemExit):
                pass
            finally:
                logger.info("Shutting down...")
                await app.updater.stop()
                await app.stop()

    try:
        loop.run_until_complete(_run())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


if __name__ == "__main__":
    main()
