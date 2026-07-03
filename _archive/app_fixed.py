# ================================================
# Medical Reports Bot - Working Version
# ================================================

import sys
import os

# Windows encoding fix - MUST be first
if sys.platform == 'win32':
    os.system('chcp 65001 >nul')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

import asyncio
import logging
import warnings
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from config.settings import BOT_TOKEN

# Disable warnings
warnings.filterwarnings("ignore", category=UserWarning, message=".*per_.*settings.*")

# Simple logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ================================================
# Simple Handlers
# ================================================

async def start(update: Update, context) -> None:
    """Handle /start command"""
    await update.message.reply_text(
        "Medical Reports Bot is working!\n\n"
        "Available commands:\n"
        "/start - Show this message\n"
        "/help - Show help\n"
        "/status - Check bot status\n\n"
        "Send any message and I'll reply!"
    )

async def help_command(update: Update, context) -> None:
    """Handle /help command"""
    await update.message.reply_text(
        "Medical Reports Bot Help\n\n"
        "Commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help\n"
        "/status - Check status\n\n"
        "This bot manages medical reports, patients, hospitals, and more."
    )

async def status_command(update: Update, context) -> None:
    """Handle /status command"""
    await update.message.reply_text("Bot is running normally!")

async def echo(update: Update, context) -> None:
    """Echo handler for testing"""
    await update.message.reply_text(f"You said: {update.message.text}")

async def error_handler(update: object, context) -> None:
    """Error handler"""
    logger.error(f"Error: {context.error}")

# ================================================
# Main Function
# ================================================

async def main():
    logger.info("=" * 50)
    logger.info("Starting Medical Bot...")
    logger.info("=" * 50)
    
    # Check token
    if not BOT_TOKEN:
        logger.error("ERROR: BOT_TOKEN not found!")
        return
    
    logger.info("Token found")
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add error handler
    app.add_error_handler(error_handler)
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    
    logger.info("Handlers registered")
    logger.info("Starting polling...")
    
    # Start polling
    await app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        poll_interval=1.0,
        timeout=30,
    )

# ================================================
# Entry Point
# ================================================

if __name__ == "__main__":
    logger.info("Medical Bot - Starting...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)