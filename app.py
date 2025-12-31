# ================================================
# app.py - البوت الطبي الكامل مع جميع التحديثات
# ✅ نسخة محسّنة للعمل بدون توقف
# ================================================

# Fix Unicode encoding on Windows
import sys
import os
if sys.platform == 'win32':
    # Set console encoding to UTF-8
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    # Set environment variable for Python
    os.environ['PYTHONIOENCODING'] = 'utf-8'

import asyncio
import nest_asyncio
import logging
import os
from telegram import Update
from telegram.ext import Application, PicklePersistence, Defaults
from telegram.constants import ParseMode
from config.settings import BOT_TOKEN

# 🔧 استيراد نظام تسجيل الهاندلرز الجديد
from bot.handlers_registry import register_all_handlers

# 🔧 تكوين نظام Logging الشامل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# تقليل ضوضاء logging للمكتبات الخارجية
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger.info("نظام مراقبة الأخطاء مفعّل")

# ================================================
# 🛡️ معالج الأخطاء العام - يمنع توقف البوت
# ================================================
async def error_handler(update: object, context) -> None:
    """معالج الأخطاء - يسجل الخطأ ويمنع توقف البوت"""
    import traceback
    
    # تجاهل أخطاء الشبكة المؤقتة
    error_str = str(context.error).lower()
    network_errors = ['timed out', 'network', 'connection', 'read error', 'write error', 'httpx']
    
    if any(err in error_str for err in network_errors):
        logger.warning(f"⚠️ خطأ شبكة مؤقت (متجاهل): {context.error}")
        return
    
    # تسجيل الأخطاء الأخرى
    logger.error(f"❌ خطأ: {context.error}")
    
    # محاولة إرسال رسالة للمستخدم
    if update and hasattr(update, 'effective_message') and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ حدث خطأ مؤقت، يرجى المحاولة مرة أخرى.\n"
                "إذا استمرت المشكلة، اضغط /start للبدء من جديد."
            )
        except:
            pass  # تجاهل إذا فشل الإرسال

# ================================================
# 🚀 التشغيل الرئيسي
# ================================================
async def main():
    logger.info("="*60)
    logger.info("Starting Medical Reports Bot - Enhanced Version...")
    logger.info("="*60)

    # 🔐 التحقق من توكن البوت
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN غير موجود!")
        return

    logger.info("✅ توكن البوت موجود وصالح")

    # 📁 إنشاء مجلد للبيانات المحفوظة
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    os.makedirs(data_dir, exist_ok=True)
    persistence_path = os.path.join(data_dir, 'bot_persistence.pickle')

    # 💾 إعداد Persistence لحفظ حالة المحادثات
    persistence = PicklePersistence(
        filepath=persistence_path,
        update_interval=30  # حفظ كل 30 ثانية
    )
    logger.info(f"💾 Persistence مفعّل: {persistence_path}")

    # ⚙️ إعدادات افتراضية للبوت
    defaults = Defaults(
        parse_mode=ParseMode.MARKDOWN,
        link_preview_options=None,  # تعطيل معاينة الروابط
        block=False  # عدم حظر الـ handlers - للاستجابة السريعة
    )

    # 🚀 إعداد request محسّن للأداء العالي والاستقرار
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(
        connection_pool_size=100,  # زيادة حجم الـ pool
        read_timeout=60.0,
        write_timeout=60.0,
        connect_timeout=30.0,
        pool_timeout=30.0,
        media_write_timeout=120.0
    )

    # 🏗️ بناء التطبيق مع جميع التحسينات
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .request(request)
        .persistence(persistence)
        .defaults(defaults)
        .concurrent_updates(True)  # معالجة متعددة للتحديثات
        .build()
    )

    # 🛡️ إضافة معالج الأخطاء
    app.add_error_handler(error_handler)

    # 📌 تسجيل جميع الهاندلرز المحدثة
    logger.info("📋 تسجيل الهاندلرز المحدثة...")
    register_all_handlers(app)
    logger.info("✅ تم تسجيل جميع الهاندلرز")

    # 🖥️ POLLING MODE مع إعدادات محسّنة للاستقرار
    logger.info("💻 Running in POLLING mode (Enhanced)")
    logger.info("="*60)

    await app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        poll_interval=0.3,  # استجابة أسرع
        timeout=60,  # timeout أقل لاكتشاف المشاكل أسرع
    )

# ================================================
# 🧠 نقطة التشغيل الرئيسية
# ================================================
if __name__ == "__main__":
    # ⚙️ السماح بـ nested event loops
    nest_asyncio.apply()

    # 🖥️ Local mode
    logger.info("💻 Starting in local polling mode (Enhanced)")
    
    while True:  # حلقة لإعادة التشغيل التلقائي
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(main())
        except KeyboardInterrupt:
            logger.info("⚠️ Bot stopped manually")
            break
        except Exception as e:
            logger.error(f"❌ Fatal error: {e}", exc_info=True)
            logger.info("🔄 إعادة تشغيل البوت خلال 5 ثواني...")
            import time
            time.sleep(5)
            continue  # إعادة المحاولة