"""
Telegram Bot Setup
"""

import logging

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from app.core.config import settings
from app.utils.logger import setup_logging
from telegram_bot.client import BotServiceClient
from telegram_bot.handlers import TelegramHandlers

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram bot manager - Polling mode only"""

    def __init__(self, service_url: str = "http://localhost:8001"):
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.bot_client = BotServiceClient(service_url)
        self.handlers = TelegramHandlers(self.bot_client)
        self.application = None

    def setup(self):
        """Setup bot application"""
        logger.info("Setting up Telegram bot...")

        # Create application
        self.application = Application.builder().token(self.token).build()

        # Add command handlers
        self.application.add_handler(CommandHandler("start", self.handlers.start_command))
        self.application.add_handler(CommandHandler("help", self.handlers.help_command))
        self.application.add_handler(CommandHandler("status", self.handlers.handle_text_message))
        self.application.add_handler(CommandHandler("clear", self.handlers.handle_text_message))
        self.application.add_handler(CommandHandler("model", self.handlers.handle_text_message))
        self.application.add_handler(CommandHandler("models", self.handlers.handle_text_message))

        # Add message handlers
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlers.handle_text_message)
        )
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handlers.handle_photo))
        self.application.add_handler(
            MessageHandler(filters.Document.IMAGE, self.handlers.handle_document)
        )

        # Add error handler
        self.application.add_error_handler(self.handlers.error_handler)

        logger.info("Telegram bot setup complete")

    def run(self):
        """Run the bot in polling mode"""
        if not self.application:
            self.setup()

        # Use polling mode
        logger.info("Starting bot in polling mode...")
        logger.info(f"Bot service URL: {self.bot_client.service_url}")
        logger.info(f"Default Model: {settings.TELEGRAM_DEFAULT_MODEL}")
        logger.info(f"Available Models: {len(settings.telegram_models_list)}")
        logger.info(f"Rate limit: {settings.TELEGRAM_RATE_LIMIT}/min")
        logger.info("=" * 60)
        self.application.run_polling(drop_pending_updates=True)


def main():
    """Main entry point"""
    try:
        bot = TelegramBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("\nBot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)


if __name__ == "__main__":
    main()
