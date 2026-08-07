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
import re
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

class _RedactSecretsFilter(logging.Filter):
    """
    Redact Telegram bot tokens from any log message.
    Prevents accidental token leakage via pm2 logs, screenshots, copy/paste, etc.
    """

    _tg_token_re = re.compile(r"(https?://api\\.telegram\\.org/bot)(\\d+:)[^/\\s]+", re.IGNORECASE)

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
            if msg:
                redacted = self._tg_token_re.sub(r"\\1\\2***REDACTED***", msg)
                if redacted != msg:
                    record.msg = redacted
                    record.args = ()
        except Exception:
            # Never break logging
            logger.debug("تم تجاهل استثناء في filter", exc_info=True)
        return True


def _harden_logging():
    # Reduce noisy/unsafe third-party logs (these are the lines that leak the token)
    for name in (
        "telegram",
        "telegram.ext",
        "telegram.request",
        "telegram._bot",
        "telegram._utils",
        "httpx",
        "httpcore",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)

    root = logging.getLogger()
    flt = _RedactSecretsFilter()
    try:
        root.addFilter(flt)
    except Exception:
        logger.debug("تم تجاهل استثناء في _harden_logging", exc_info=True)
    for h in list(root.handlers):
        try:
            h.addFilter(flt)
        except Exception:
            logger.debug("تم تجاهل استثناء في _harden_logging", exc_info=True)


_harden_logging()

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
            logger.debug("تم تجاهل استثناء في _acquire_single_instance_lock", exc_info=True)
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
        logger.debug("تم تجاهل استثناء في _release_single_instance_lock", exc_info=True)
    try:
        _instance_lock_handle.close()
    except Exception:
        logger.debug("تم تجاهل استثناء في _release_single_instance_lock", exc_info=True)
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

    # ✅ رفضٌ حميد من تيليجرام لتعديل رسالة — ليس خطأً بأي معنى مفيد:
    # "Message is not modified" تعني أن الشاشة **تعرض بالفعل** ما أردنا
    # عرضه (ضغطة مكرَّرة على نفس الزر، أو إعادة رسم نفس الشاشة)، وبقيّة
    # الحالات تعني أن الرسالة المستهدفة لم تعد قابلة للتعديل (قديمة/محذوفة).
    # كانت تصل إلى logger.error أدناه فتظهر في تقرير الأخطاء اليومي وتزاحم
    # الأعطال الحقيقية. وهي معالَجة محلياً في 8 مواضع أصلاً، لكن مئات
    # استدعاءات edit_message_text الأخرى غير محميّة — فالمكان الصحيح
    # للحارس هو هنا مركزياً لا تكرار الحماية في كل موضع.
    benign_edit_rejections = [
        'message is not modified',
        "message can't be edited",
        'message to edit not found',
        'message_id_invalid',
        'query is too old',
    ]
    if any(err in error_str for err in benign_edit_rejections):
        logger.debug(f"Benign Telegram edit rejection (ignored): {error}")
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

    # ✅ تهيئة/ترحيل قاعدة البيانات — يجب أن يعمل هذا فعلياً في كل إقلاع حقيقي
    # للبوت، وليس فقط في سكربتات اختبار منفصلة. كان هذا الاستدعاء غائباً
    # تماماً عن app.py سابقاً، فكانت أي عمود جديد (مثل patient_type) يُضاف
    # في db/models.py لا يصل أبداً لقاعدة البيانات الفعلية مهما أُعيد تشغيل
    # البوت — لأن الدالة التي تضيفه (init_database/check_db_health_startup)
    # لم تكن تُستدعى من أي مكان في المسار الحقيقي للتشغيل. آمنة للاستدعاء
    # في كل مرة (create_all لا يكرر الجداول الموجودة، وفحص كل عمود مستقل
    # ومتحقق من وجوده أولاً قبل أي ALTER).
    try:
        from db.session import init_database
        if init_database():
            logger.info("✅ Database initialized/verified successfully.")
        else:
            logger.error("❌ Database initialization reported failure — check logs above.")
    except Exception as db_init_error:
        logger.critical(f"❌ Database initialization crashed: {db_init_error}", exc_info=True)

    # Create application with increased timeouts
    from telegram.ext import ApplicationBuilder
    from config.settings import TIMEZONE
    import pytz
    
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(15.0)
        .read_timeout(60.0)   # وقت أطول لاستقبال الملفات الكبيرة
        .write_timeout(60.0)  # وقت أطول لرفع الملفات
        .pool_timeout(15.0)
        .build()
    )
    app.add_error_handler(error_handler)

    # 🧾 مراقب السجلات — يلتقط كل ERROR فأعلى من أي ملف في المشروع ويكتبه
    # في ملف اليوم، ليُرسَل ملخّصاً للأدمن آخر اليوم. يُركَّب هنا مبكراً حتى
    # يلتقط أخطاء التسجيل والإقلاع نفسها.
    from services.error_digest import install as install_error_digest
    install_error_digest()

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

        # 🔔 3. تنبيه انتهاء الإقامات/الجوازات (الساعة 9:00 صباحاً)
        # صباحاً عمداً — تنبيه إجرائي يحتاج وقت عمل للتصرّف فيه، بخلاف
        # تنبيه المواعيد المسائي الذي يخص اليوم التالي.
        from services.residency_alerts_service import send_daily_residency_alerts
        app.job_queue.run_daily(
            lambda context: send_daily_residency_alerts(context.application),
            time=dt_time(hour=9, minute=0, tzinfo=tz),
            name="daily_residency_alerts"
        )
        logger.info(f"🔔 Scheduled daily residency/passport alerts at 09:00 ({TIMEZONE})")

        # 🧾 4. تقرير أخطاء اليوم (23:55) — آخر اليوم عمداً ليشمله كاملاً.
        # صامت تماماً لو لم يقع أي خطأ، فلا رسالة يومية بلا فائدة.
        from services.error_digest import send_daily_error_report, cleanup_old
        async def _error_report_job(context):
            await send_daily_error_report(context.application)
            cleanup_old(days=30)
        app.job_queue.run_daily(
            _error_report_job,
            time=dt_time(hour=23, minute=55, tzinfo=tz),
            name="daily_error_report",
        )
        logger.info(f"🧾 Scheduled daily error report at 23:55 ({TIMEZONE})")
    else:
        logger.warning("⚠️ JobQueue is not available! Scheduled tasks will not run.")
    
    # Try to add advanced handlers
    try:
        logger.info("Loading advanced handlers...")
        from bot.handlers_registry import register_all_handlers
        register_all_handlers(app)
        logger.info("Advanced handlers loaded successfully!")
    except Exception as e:
        # إظهار سبب الفشل الحقيقي يساعد جدًا في مشكلة "الأزرار لا تستجيب" أونلاين
        logger.exception("Could not load advanced handlers")
        logger.info("Using basic handlers only")
        # ما زلنا نحتاج universal fallback حتى لو فشل تسجيل الهاندلرز المتقدمة
        try:
            from bot.handlers.shared.universal_fallback import register as register_universal_fallback
            register_universal_fallback(app)
            logger.info("Universal fallback registered (advanced handlers failed).")
        except Exception:
            logger.warning("Failed to register universal fallback", exc_info=True)
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

    # ── Startup config verification ───────────────────────────────────────────
    from config.settings import (
        HEALTHCARE_GROUP_ID, GENERAL_SERVICES_GROUP_ID,
        REPORTS_GROUP_ID, ADMIN_IDS,
    )
    logger.info("[startup] ADMIN_IDS              = %s", ADMIN_IDS)
    logger.info("[startup] REPORTS_GROUP_ID        = %r", REPORTS_GROUP_ID)
    logger.info("[startup] HEALTHCARE_GROUP_ID     = %r", HEALTHCARE_GROUP_ID)
    logger.info("[startup] GENERAL_SERVICES_GROUP_ID = %r", GENERAL_SERVICES_GROUP_ID)
    if not HEALTHCARE_GROUP_ID:
        logger.warning("[startup] ⚠️  HEALTHCARE_GROUP_ID is EMPTY — healthcare reports will NOT be sent to a group")
    
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