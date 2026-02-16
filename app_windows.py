# ================================================
# app_windows.py - نسخة محسّنة للـ Windows
# ✅ يعمل بدون مشاكل الترميز
# ================================================

# Fix Windows encoding
import sys
import os
if sys.platform == 'win32':
    import locale
    try:
        os.system('chcp 65001 >nul')
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass
    os.environ['PYTHONIOENCODING'] = 'utf-8'

import asyncio
import nest_asyncio
import logging
import warnings
import os
import time
from telegram import Update
from telegram.ext import Application, PicklePersistence, Defaults
from telegram.constants import ParseMode
from config.settings import BOT_TOKEN

# تجاهل تحذيرات PTBUserWarning
warnings.filterwarnings("ignore", category=UserWarning, message=".*per_.*settings.*")

# 🔧 استيراد نظام تسجيل الهاندلرز الجديد
from bot.handlers_registry import register_all_handlers

# 🔧 تكوين نظام Logging الشامل
try:
    logging.basicConfig(
        filename='logs/bot.log',
        filemode='a',
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.DEBUG,
        encoding='utf-8'
    )
except:
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.DEBUG
    )

logger = logging.getLogger(__name__)

# تفعيل وضع WAL في قاعدة البيانات
import sqlite3
db_path = os.path.join('db', 'medical_reports.db')
try:
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.close()
    logger.info('تم تفعيل وضع WAL في قاعدة البيانات بنجاح.')
except Exception as e:
    logger.error(f'فشل تفعيل وضع WAL: {e}')

# تقليل ضوضاء logging للمكتبات الخارجية
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# تسجيل جميع الاستثناءات غير الملتقطة
import traceback
def log_uncaught_exceptions(exctype, value, tb):
    logger.error("Uncaught exception:", exc_info=(exctype, value, tb))
    print('Uncaught exception:', value)
    traceback.print_exception(exctype, value, tb)
sys.excepthook = log_uncaught_exceptions

logger.info("نظام مراقبة الأخطاء مفعّل")

# ================================================
# 🛡️ معالج الأخطاء العام
# ================================================
async def error_handler(update: object, context) -> None:
    """معالج الأخطاء - يسجل الخطأ ويمنع توقف البوت"""
    import traceback
    
    # تجاهل أخطاء الشبكة المؤقتة
    error_str = str(context.error).lower()
    network_errors = ['timed out', 'network', 'connection', 'read error', 'write error', 'httpx']
    
    if any(err in error_str for err in network_errors):
        logger.warning(f"Network error (ignored): {context.error}")
        return
    
    # تسجيل الأخطاء الأخرى
    logger.error(f"Error: {context.error}")
    
    # محاولة إرسال رسالة للمستخدم
    if update and hasattr(update, 'effective_message') and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "حدث خطأ مؤقت، يرجى المحاولة مرة أخرى.\n"
                "إذا استمرت المشكلة، اضغط /start للبدء من جديد."
            )
        except Exception:
            pass  # تجاهل إذا فشل الإرسال

# ================================================
# 🚀 التشغيل الرئيسي
# ================================================
async def main():
    logger.info("="*60)
    logger.info("Starting Medical Reports Bot - Windows Version...")
    logger.info("="*60)

    # 🔐 التحقق من توكن البوت
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found!")
        return

    logger.info("Bot token found and valid")

    # 💾 تهيئة نظام النسخ الاحتياطي
    try:
        from services.database_backup import initialize_backup_system
        backup_path = initialize_backup_system()
        if backup_path:
            logger.info(f"Backup initialized: {backup_path}")
    except Exception as e:
        logger.warning(f"Backup system error: {e}")

    # 📁 إنشاء مجلد للبيانات المحفوظة
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    os.makedirs(data_dir, exist_ok=True)
    persistence_path = os.path.join(data_dir, 'bot_persistence.pickle')

    # 💾 إعداد Persistence
    if os.path.exists(persistence_path):
        try:
            import pickle
            with open(persistence_path, 'rb') as _f:
                first = _f.read(1)
                if not first:
                    raise EOFError("empty file")
                _f.seek(0)
                pickle.load(_f)
        except Exception as ex:
            logger.warning(f"Corrupted persistence file detected: {ex}")
            try:
                bak = f"{persistence_path}.corrupt_{int(time.time())}"
                os.rename(persistence_path, bak)
                logger.info(f"Corrupted file moved to: {bak}")
            except Exception as ren_err:
                logger.warning(f"Failed to backup corrupted file: {ren_err}")

    persistence = PicklePersistence(
        filepath=persistence_path,
        update_interval=30
    )
    logger.info(f"Persistence enabled: {persistence_path}")

    # ⚙️ إعدادات افتراضية للبوت
    defaults = Defaults(
        parse_mode=ParseMode.MARKDOWN,
        link_preview_options=None,
        block=False
    )

    # 🚀 إعداد request محسّن
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(
        connection_pool_size=100,
        read_timeout=60.0,
        write_timeout=60.0,
        connect_timeout=30.0,
        pool_timeout=30.0,
        media_write_timeout=120.0
    )

    # 🏗️ بناء التطبيق
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .request(request)
        .persistence(persistence)
        .defaults(defaults)
        .concurrent_updates(True)
        .build()
    )

    # 🛡️ إضافة معالج الأخطاء
    app.add_error_handler(error_handler)

    # 📌 تسجيل جميع الهاندلرز
    logger.info("Registering handlers...")
    register_all_handlers(app)
    logger.info("All handlers registered")

    # 🖥️ POLLING MODE
    logger.info("Starting in POLLING mode (Windows Version)")
    logger.info("="*60)

    try:
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            poll_interval=0.3,
            timeout=60,
        )
    except KeyboardInterrupt:
        logger.info("Bot stopped manually")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise

# ================================================
# 🧠 نقطة التشغيل الرئيسية
# ================================================
if __name__ == "__main__":
    # ⚙️ السماح بـ nested event loops
    nest_asyncio.apply()

    # 🖥️ Windows mode
    logger.info("Starting in Windows polling mode")
    
    while True:
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(main())
        except KeyboardInterrupt:
            logger.info("Bot stopped manually")
            break
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            logger.info("Restarting bot in 5 seconds...")
            time.sleep(5)
            continue