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

    # 🚀 إعداد request محسّن للأداء العالي
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(
        connection_pool_size=50,
        read_timeout=300.0,
        write_timeout=300.0,
        connect_timeout=60.0,
        pool_timeout=60.0,
        media_write_timeout=300.0
    )

    app = Application.builder().token(BOT_TOKEN).request(request).build()

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
        poll_interval=0.5,
        timeout=300,
        bootstrap_retries=15,
        read_timeout=600,
        write_timeout=600,
        connect_timeout=120,
        pool_timeout=300,
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
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)