# ================================================
# Medical Reports Bot - Full Working Version
# ================================================

import sys
import os
import atexit

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

_instance_lock_handle = None


def _acquire_single_instance_lock() -> bool:
    """
    Prevent multiple running bot instances on the same host.
    """
    global _instance_lock_handle
    lock_path = os.getenv("BOT_INSTANCE_LOCKFILE", "/tmp/medbot_single_instance.lock")
    try:
        lock_file = open(lock_path, "a+")
    except Exception as e:
        logger.error(f"Could not open lock file: {e}")
        return False

    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_file.seek(0)
        lock_file.truncate(0)
        lock_file.write(str(os.getpid()))
        lock_file.flush()
    except Exception:
        logger.error("Another bot instance appears to be running. Exiting.")
        try:
            lock_file.close()
        except Exception:
            pass
        return False

    _instance_lock_handle = lock_file
    atexit.register(_release_single_instance_lock)
    return True


def _release_single_instance_lock():
    global _instance_lock_handle
    if not _instance_lock_handle:
        return
    try:
        if os.name != "nt":
            import fcntl
            fcntl.flock(_instance_lock_handle.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        _instance_lock_handle.close()
    except Exception:
        pass
    _instance_lock_handle = None

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

    if not _acquire_single_instance_lock():
        return
    logger.info("Starting Medical Bot...")
    logger.info("=" * 50)
    
    if not BOT_TOKEN:
        logger.error("ERROR: No BOT_TOKEN!")
        return
    
    logger.info("Token found")
    
    # Create application with increased timeouts
    from telegram.ext import ApplicationBuilder
    from config.settings import TIMEZONE
    import pytz
    
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

    # ✅ إعداد المجدول الزمني (JobQueue)
    if app.job_queue:
        from services.notification_service import send_daily_appointments_reminder
        from db.maintenance import run_scheduled_maintenance
        from datetime import time as dt_time
        
        # ⏰ 1. تنبيه المواعيد اليومي (الساعة 8:00 مساءً)
        # ملاحظة: يتم استخدام المنطقة الزمنية المحددة في الإعدادات
        tz = pytz.timezone(TIMEZONE)
        app.job_queue.run_daily(
            lambda context: send_daily_appointments_reminder(context.application),
            time=dt_time(hour=20, minute=0, tzinfo=tz),
            name="daily_appointments_reminder"
        )
        logger.info(f"📅 Scheduled daily appointments reminder at 20:00 ({TIMEZONE})")
        
        # 🔧 2. الصيانة اليومية (الساعة 3:00 صباحاً)
        app.job_queue.run_daily(
            lambda context: asyncio.create_task(asyncio.to_thread(run_scheduled_maintenance)),
            time=dt_time(hour=3, minute=0, tzinfo=tz),
            name="daily_maintenance"
        )
        logger.info(f"🔧 Scheduled daily maintenance at 03:00 ({TIMEZONE})")
    else:
        logger.warning("⚠️ JobQueue is not available! Scheduled tasks will not run.")
    
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
    try:
        while True:
            await asyncio.sleep(3600)  # Sleep for 1 hour to reduce CPU usage
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