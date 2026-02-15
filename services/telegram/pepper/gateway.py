"""
PEPPER Telegram Bot Gateway

Main entry point for the PEPPER bot system. Handles message routing,
user authentication, and mode-based access control.
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict

from telegram import Update, ReactionTypeEmoji
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.error import TelegramError

from .config import PepperConfig, load_config, validate_config, get_active_bot
from .modes import UserMode, get_user_mode, get_mode_config, is_command_allowed

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple in-memory rate limiter for demo mode users"""

    def __init__(self, window_seconds: int = 3600):
        self.window_seconds = window_seconds
        self.requests: Dict[int, list] = defaultdict(list)

    def check_limit(self, user_id: int, max_requests: Optional[int]) -> bool:
        """
        Check if user has exceeded rate limit.

        Args:
            user_id: Telegram user ID
            max_requests: Maximum requests allowed (None = unlimited)

        Returns:
            True if under limit, False if exceeded
        """
        if max_requests is None:
            return True

        now = datetime.now()
        cutoff = now - timedelta(seconds=self.window_seconds)

        # Remove old requests
        self.requests[user_id] = [
            req_time for req_time in self.requests[user_id]
            if req_time > cutoff
        ]

        # Check if under limit
        if len(self.requests[user_id]) >= max_requests:
            return False

        # Record this request
        self.requests[user_id].append(now)
        return True


class PepperGateway:
    """
    Main Telegram bot gateway for PEPPER.

    Handles message routing, authentication, and mode-based access control.
    """

    def __init__(self, config: PepperConfig, prefer_prime: bool = True):
        """
        Initialize PEPPER gateway.

        Args:
            config: PepperConfig instance
            prefer_prime: If True, use prime bot; otherwise use demo bot
        """
        self.config = config
        self.bot_config = get_active_bot(config, prefer_prime)
        self.rate_limiter = RateLimiter(config.rate_limit_window)
        self.application: Optional[Application] = None

        logger.info(f"Initialized PEPPER Gateway: {self.bot_config.name}")

    async def _add_eyes_reaction(self, update: Update) -> None:
        """Add 👀 reaction to message to indicate processing"""
        try:
            await update.message.set_reaction(reaction=ReactionTypeEmoji("👀"))
        except TelegramError as e:
            logger.warning(f"Failed to add reaction: {e}")

    async def _send_typing(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
        """Send typing indicator"""
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        except TelegramError as e:
            logger.warning(f"Failed to send typing action: {e}")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        user = update.effective_user
        mode_config = get_mode_config(user.id)

        logger.info(f"User {user.id} ({user.username}) started bot in {mode_config.mode.value} mode")

        await update.message.reply_text(
            mode_config.greeting,
            parse_mode="Markdown",
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command"""
        user = update.effective_user
        mode_config = get_mode_config(user.id)

        if mode_config.mode == UserMode.BLOCKED:
            await update.message.reply_text("Access denied.")
            return

        if mode_config.mode == UserMode.GOD:
            help_text = """
🔧 *PEPPER - God Mode*

You have full system access. Available commands:

*Basic:*
/start - Restart bot
/help - Show this message
/status - System status

*Factory:*
/diagnose - Diagnose equipment issues
/equipment - List connected equipment
/nodes - Show remote node status

*System:*
/plc - Direct PLC access
/logs - View recent logs
/debug - Toggle debug mode

Just ask me anything - I'll figure out what you need.
"""
        else:
            help_text = """
🏭 *PEPPER - Maintenance Assistant*

I can help you with:

*Equipment Diagnostics:*
/diagnose - Diagnose equipment issues
/equipment - List connected equipment
/status - Check system status

*Information:*
/help - Show this message

You can also just describe your problem in plain English, and I'll help you troubleshoot.

Example: "Motor 3 is overheating"
"""

        await update.message.reply_text(help_text, parse_mode="Markdown")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command - show system status"""
        user = update.effective_user
        mode_config = get_mode_config(user.id)

        if mode_config.mode == UserMode.BLOCKED:
            await update.message.reply_text("Access denied.")
            return

        await self._add_eyes_reaction(update)
        await self._send_typing(context, update.effective_chat.id)

        # Build status message
        status_lines = [
            f"🤖 *PEPPER Status* (v{self.config.version})",
            f"Mode: {mode_config.mode.value.upper()}",
            "",
            "*Remote Nodes:*",
        ]

        # Check node status (placeholder - implement actual health checks)
        for node_name, node_config in self.config.nodes.items():
            status_icon = "🟢" if node_config.enabled else "🔴"
            status_lines.append(f"{status_icon} {node_name}: {node_config.url}")

        if mode_config.mode == UserMode.GOD:
            status_lines.extend([
                "",
                "*Debug Info:*",
                f"User ID: `{user.id}`",
                f"Username: @{user.username or 'N/A'}",
            ])

        await update.message.reply_text(
            "\n".join(status_lines),
            parse_mode="Markdown",
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming text messages"""
        user = update.effective_user
        message = update.message
        text = message.text

        logger.info(f"Message from {user.id} ({user.username}): {text[:50]}...")

        # Get user mode and config
        mode_config = get_mode_config(user.id)

        # Check if user is blocked
        if mode_config.mode == UserMode.BLOCKED:
            logger.warning(f"Blocked user {user.id} attempted to send message")
            await message.reply_text("Access denied.")
            return

        # Check rate limit for demo users
        if mode_config.mode == UserMode.DEMO:
            if not self.rate_limiter.check_limit(user.id, mode_config.max_requests_per_hour):
                logger.warning(f"User {user.id} exceeded rate limit")
                await message.reply_text(
                    "⚠️ You've reached the rate limit. Please try again later."
                )
                return

        # Add eyes reaction to show we received the message
        await self._add_eyes_reaction(update)

        # Send typing indicator
        await self._send_typing(context, message.chat_id)

        # TODO: Route to appropriate handler based on message content
        # For now, send a placeholder response
        response = self._generate_placeholder_response(text, mode_config)

        await message.reply_text(response, parse_mode="Markdown")

    def _generate_placeholder_response(self, text: str, mode_config) -> str:
        """Generate a placeholder response (to be replaced with actual routing)"""
        if mode_config.mode == UserMode.GOD:
            return (
                f"🔧 *God Mode Active*\n\n"
                f"Received: _{text[:50]}_\n\n"
                f"Handler routing not yet implemented. "
                f"This will be routed to the appropriate service based on intent."
            )
        else:
            return (
                f"📋 *Demo Mode*\n\n"
                f"Received: _{text[:50]}_\n\n"
                f"I'm analyzing your request. Full handler integration coming soon!"
            )

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors"""
        logger.error(f"Update {update} caused error {context.error}")

        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ An error occurred while processing your request. "
                "Please try again later."
            )

    def build_application(self) -> Application:
        """
        Build and configure the Telegram application.

        Returns:
            Configured Application instance
        """
        logger.info(f"Building application for bot: {self.bot_config.name}")

        # Build application
        application = (
            ApplicationBuilder()
            .token(self.bot_config.token)
            .build()
        )

        # Add command handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("status", self.status_command))

        # Add message handler for all text messages
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

        # Add error handler
        application.add_error_handler(self.error_handler)

        logger.info("Application built successfully")

        self.application = application
        return application

    async def run(self) -> None:
        """
        Run the bot (async).

        This method starts the bot and runs until interrupted.
        """
        if self.application is None:
            self.build_application()

        logger.info(f"Starting PEPPER bot: {self.bot_config.name}")

        # Start the bot
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

        logger.info("Bot is running. Press Ctrl+C to stop.")

        # Keep running until interrupted
        try:
            # Run forever
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop the bot gracefully"""
        if self.application:
            logger.info("Stopping bot...")
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("Bot stopped successfully")

    def run_sync(self) -> None:
        """
        Run the bot (synchronous wrapper).

        This is a convenience method that wraps the async run() method.
        """
        asyncio.run(self.run())


async def main():
    """Main entry point for running PEPPER bot"""
    # Load configuration
    try:
        config = load_config()
        validate_config(config)
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return

    # Create and run gateway
    gateway = PepperGateway(config, prefer_prime=True)
    await gateway.run()


if __name__ == "__main__":
    asyncio.run(main())
