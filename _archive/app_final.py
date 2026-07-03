# ================================================
# Medical Reports Bot - Final Working Version
# ================================================

import sys
import os

# Windows encoding fix
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
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ================================================
# Handlers
# ================================================

async def start(update: Update, context) -> None:
    await update.message.reply_text("Bot is working! Send /start or any message.")

async def help_command(update: Update, context) -> None:
    await update.message.reply_text("Commands: /start, /help, /status")

async def status_command(update: Update, context) -> None:
    await update.message.reply_text("Bot is running normally!")

async def echo(update: Update, context) -> None:
    await update.message.reply_text(f"Echo: {update.message.text}")

async def error_handler(update: object, context) -> None:
    logger.error(f"Error: {context.error}")

# ================================================
# Main
# ================================================

async def main():
    if not BOT_TOKEN:
        logger.error("No token!")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_error_handler(error_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    
    logger.info("Starting bot...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    logger.info("Bot is running!")
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(10)
            logger.info("Bot alive...")
    except asyncio.CancelledError:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        logger.info("Bot stopped")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped by user")
    except Exception as e:
        logger.error(f"Error: {e}")