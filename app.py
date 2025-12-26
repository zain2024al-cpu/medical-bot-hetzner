# ================================================
# app.py - البوت الطبي الكامل مع جميع التحديثات
# ================================================

import asyncio
import nest_asyncio
import logging
from telegram import Update
from telegram.ext import Application
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

logger.info("نظام مراقبة الأخطاء مفعّل")

# ================================================
# 🚀 التشغيل الرئيسي
# ================================================
async def main():
    logger.info("="*60)
    logger.info("Starting Medical Reports Bot with ALL Updates...")
    logger.info("="*60)

    # 🔐 التحقق من توكن البوت
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN غير موجود!")
        return

    logger.info("✅ توكن البوت موجود وصالح")

    # 🚀 إعداد request محسّن للأداء العالي - يدعم 20+ مستخدم متزامن
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(
        connection_pool_size=100,  # زيادة pool size لدعم 20+ مستخدم
        read_timeout=600.0,  # 10 دقائق - timeout عالي للمستخدمين
        write_timeout=600.0,  # 10 دقائق
        connect_timeout=120.0,  # 2 دقيقة
        pool_timeout=120.0,  # 2 دقيقة
        media_write_timeout=600.0  # 10 دقائق للملفات الكبيرة
    )

    # 🚀 إعداد Application مع معالج قوي للضغط العالي
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .request(request)
        .concurrent_updates(True)  # ✅ تفعيل المعالجة المتزامنة - يدعم 20+ مستخدم
        .build()
    )

    # 🚀 بدء معالج الطلبات القوي (للضغط العالي)
    try:
        from services.request_processor import start_request_processor
        await start_request_processor()
        logger.info("✅ تم بدء معالج الطلبات القوي")
    except Exception as e:
        logger.warning(f"⚠️ فشل بدء معالج الطلبات: {e} - سيتم المتابعة بدون queue system")
    
    # 📊 بدء مراقبة الأداء
    try:
        from services.performance_monitor import start_performance_monitoring
        asyncio.create_task(start_performance_monitoring(interval=300))  # كل 5 دقائق
        logger.info("✅ تم بدء مراقبة الأداء")
    except Exception as e:
        logger.warning(f"⚠️ فشل بدء مراقبة الأداء: {e}")

    # 🛡️ تهيئة نظام المرونة والاستقرار
    try:
        from services.resilience_manager import initialize_resilience_system
        await initialize_resilience_system()
        logger.info("✅ تم تهيئة نظام المرونة والاستقرار")
    except Exception as e:
        logger.warning(f"⚠️ فشل تهيئة نظام المرونة: {e}")
    
    # 🛡️ إضافة معالج أخطاء شامل
    try:
        from services.error_handler import comprehensive_error_handler
        app.add_error_handler(comprehensive_error_handler)
        logger.info("✅ تم تفعيل معالج الأخطاء الشامل")
    except Exception as e:
        logger.warning(f"⚠️ فشل تفعيل معالج الأخطاء: {e}")

    # 📌 تسجيل جميع الهاندلرز المحدثة
    logger.info("📋 تسجيل الهاندلرز المحدثة...")
    register_all_handlers(app)
    logger.info("✅ تم تسجيل جميع الهاندلرز")

    # 🖥️ POLLING MODE (Local Development)
    logger.info("💻 Running in POLLING mode")
    logger.info("="*60)

    await app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        poll_interval=0.3,  # استعلام أسرع للاستجابة الفورية
        timeout=300,  # 5 دقائق - timeout محسّن
        bootstrap_retries=20,  # محاولات أكثر للاتصال
        close_loop=False,  # عدم إغلاق الـ loop عند الأخطاء
        stop_signals=None,  # عدم التوقف عند الإشارات
    )

# ================================================
# 🧠 نقطة التشغيل الرئيسية
# ================================================
if __name__ == "__main__":
    # ⚙️ السماح بـ nested event loops
    nest_asyncio.apply()

    # 🖥️ Local mode
    logger.info("💻 Starting in local polling mode")
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("⚠️ Bot stopped manually")
        # إيقاف معالج الطلبات
        try:
            from services.request_processor import stop_request_processor
            loop = asyncio.get_event_loop()
            loop.run_until_complete(stop_request_processor())
        except:
            pass
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        # إيقاف معالج الطلبات
        try:
            from services.request_processor import stop_request_processor
            loop = asyncio.get_event_loop()
            loop.run_until_complete(stop_request_processor())
        except:
            pass
