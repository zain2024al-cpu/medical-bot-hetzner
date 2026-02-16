# ================================================
# Medical Reports Bot - Full Working Version
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
# Basic Handlers (fallback)
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

async def unknown_command(update: Update, context) -> None:
    """Handle unknown commands"""
    await update.message.reply_text(
        "المعذرة، لم أفهم طلبك.\n"
        "استخدم /start لبدء استخدام النظام."
    )

async def error_handler(update: object, context) -> None:
    """Error handler"""
    error = context.error
    error_str = str(error).lower()
    
    # تجاهل أخطاء التعارض (Conflict) - تحدث عندما يعمل أكثر من نسخة من البوت
    if "Conflict" in str(error) or "terminated by other getUpdates" in error_str:
        logger.warning(f"⚠️ Conflict detected - another bot instance may be running: {error}")
        logger.warning("💡 Make sure only one bot instance is running!")
        return  # تجاهل الخطأ ولا نوقف البوت
    
    # تجاهل أخطاء الشبكة المؤقتة
    network_errors = ['timed out', 'network', 'connection', 'read error', 'write error', 'httpx']
    if any(err in error_str for err in network_errors):
        logger.warning(f"Network error (ignored): {error}")
        return
    
    # تسجيل الأخطاء الأخرى
    logger.error(f"Error: {error}", exc_info=True)

# ================================================
# Main
# ================================================

async def main():
    logger.info("=" * 50)
    logger.info("Starting Medical Bot...")
    logger.info("=" * 50)
    
    if not BOT_TOKEN:
        logger.error("ERROR: No BOT_TOKEN!")
        return
    
    logger.info("Token found")
    
    # Create application with increased timeouts
    from telegram.ext import ApplicationBuilder
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(30.0)
        .build()
    )
    app.add_error_handler(error_handler)
    
    # Try to add advanced handlers
    try:
        logger.info("Loading advanced handlers...")
        from bot.handlers_registry import register_all_handlers
        register_all_handlers(app)
        logger.info("Advanced handlers loaded successfully!")
    except Exception as e:
        logger.warning(f"Could not load advanced handlers: {e}")
        logger.info("Using basic handlers only")
        # Add basic handlers only if advanced handlers failed
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("status", status_command))
    
    logger.info("Starting bot...")

    # حذف webhook أولاً قبل أي شيء لتجنب التعارض
    try:
        from telegram import Bot
        temp_bot = Bot(token=BOT_TOKEN)
        await temp_bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook deleted before initialization")
    except Exception as e:
        logger.warning(f"⚠️ Could not delete webhook: {e}")

    await app.initialize()
    await app.start()
    
    # ✅ إضافة allowed_updates للتأكد من استقبال inline_query
    await app.updater.start_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query", "inline_query", "chosen_inline_result", "edited_message"]
    )
    logger.info("=" * 50)
    logger.info("Bot is running!")
    logger.info(f"Bot: @med_reports_bot")
    logger.info("=" * 50)
    
    # Keep running
    last_maintenance = 0
    try:
        while True:
            await asyncio.sleep(30)
            
            # Run maintenance every 24 hours (86400 seconds)
            import time
            current_time = time.time()
            # Initial run after 1 minute if not run yet (for testing), then every 24 hours
            # But let's stick to simple logic: run if > 24h
            # To ensure it runs on startup/restart after a bit, we can check if last_maintenance == 0
            if last_maintenance == 0:
                 # Don't run immediately on startup to allow bot to initialize fully
                 last_maintenance = current_time - 86000 # Run in ~400 seconds (approx 6 mins)
            
            if current_time - last_maintenance > 86400:
                logger.info("⏰ Running daily scheduled maintenance...")
                try:
                    from db.maintenance import run_scheduled_maintenance
                    # Run in thread to avoid blocking the event loop
                    await asyncio.to_thread(run_scheduled_maintenance)
                    last_maintenance = current_time
                    logger.info("✅ Daily maintenance completed")
                except Exception as e:
                    logger.error(f"❌ Maintenance failed: {e}")
            
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
        sys.exit(1)