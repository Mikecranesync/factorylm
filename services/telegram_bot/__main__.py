"""
FactoryLM Conversational Maintenance Bot — Entry Point.

Usage:
    TELEGRAM_TOKEN=<token> python -m services.telegram_bot
    # or with Doppler:
    doppler run -p factorylm -c dev -- python -m services.telegram_bot
"""

import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN not set. Export it or use Doppler.")
        sys.exit(1)

    from services.telegram_bot.handler import create_app

    app = create_app(token)
    logger.info("FactoryLM maintenance bot starting (polling mode)")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
