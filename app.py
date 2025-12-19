# ================================================
# app.py
# 🔹 نقطة التشغيل الرئيسية للبوت الطبي
# ================================================

import asyncio
import nest_asyncio
import logging
from telegram import Update
from telegram.ext import Application
from config.settings import BOT_TOKEN
from services.scheduler import start_scheduler

# 🔧 استيراد نظام تسجيل الهاندلرز الجديد
from bot.handlers_registry import register_all_handlers

# 🔧 تكوين نظام Logging الشامل
from services.error_monitoring import setup_logging, comprehensive_error_handler, error_monitor
root_logger = setup_logging()

# تقليل ضوضاء logging للمكتبات الخارجية (تأكيد إضافي)
external_loggers = [
    "matplotlib", "matplotlib.font_manager",
    "httpcore", "httpcore.connection", "httpcore.http11",
    "httpx",
    "telegram", "telegram.ext", "telegram.ext.ExtBot", 
    "telegram.ext.Updater", "telegram.ext.Application",
    "apscheduler", "apscheduler.scheduler",
]
for logger_name in external_loggers:
    logging.getLogger(logger_name).setLevel(logging.WARNING)
    logging.getLogger(logger_name).propagate = False

logger = logging.getLogger(__name__)
logger.info("نظام مراقبة الأخطاء مفعّل")

# ================================================
# 🚀 التشغيل الرئيسي
# ================================================
async def main():
    logger.info("="*60)
    logger.info("Starting Medical Reports Bot...")
    logger.info("="*60)

    # 🔐 التحقق من توكن البوت (مهم جداً للاستضافة السحابية)
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN غير موجود! تأكد من إعداد متغيرات البيئة")
        logger.error("   في الاستضافة السحابية: أضف BOT_TOKEN في متغيرات البيئة")
        logger.error("   محلياً: أضف BOT_TOKEN في ملف config.env")
        return

    logger.info("✅ توكن البوت موجود وصالح")

    # 🔧 تهيئة قاعدة البيانات وأسماء المرضى
    try:
        from db.online_hosting_config import init_online_hosting_config, OnlineHostingConfig
        from db.patient_names_loader import init_patient_names
        from db.session import init_database

        # تهيئة إعدادات الاستضافة الإلكترونية
        init_online_hosting_config()

        # 🔄 استعادة قاعدة البيانات من Google Cloud Storage إذا كان مفعلاً
        if OnlineHostingConfig.AUTO_RESTORE_ON_STARTUP:
            try:
                from db.persistent_storage import restore_database_on_startup
                if restore_database_on_startup():
                    logger.info("✅ تم استعادة قاعدة البيانات من Google Cloud Storage")
                else:
                    logger.info("ℹ️ لا توجد نسخة احتياطية سابقة، سيتم إنشاء قاعدة بيانات جديدة")
            except Exception as restore_error:
                logger.warning(f"⚠️ فشل في استعادة قاعدة البيانات من السحابة: {restore_error}")
                logger.info("ℹ️ سيتم إنشاء قاعدة بيانات جديدة محلياً")

        # تهيئة قاعدة البيانات (سيحمل من medical_reports_initial.db إذا لزم الأمر)
        init_database()

        # تهيئة أسماء المرضى من قاعدة البيانات (بعد تحميل قاعدة البيانات)
        init_patient_names()
    except Exception as e:
        logger.error(f"❌ خطأ في تهيئة قاعدة البيانات: {e}")
        import traceback
        traceback.print_exc()

    # 🤖 Telegram App + Persistence
    from telegram.ext import DictPersistence
    persistence = DictPersistence()
    app = Application.builder().token(BOT_TOKEN).persistence(persistence).build()

    # 🕐 Scheduler
    start_scheduler(app)

    # 📌 Handlers
    register_all_handlers(app)

    # 🧯 Error Handler - نظام مراقبة شامل
    app.add_error_handler(comprehensive_error_handler)
    logger.info("نظام معالجة الأخطاء الشامل مفعّل")

    logger.info("Handlers loaded")
    logger.info("="*60)

    # 🔧 Cloud Run / Render / Polling detection
    import os
    # Render uses RENDER_EXTERNAL_URL, Cloud Run uses SERVICE_URL
    SERVICE_URL = os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("SERVICE_URL", "")
    # PORT must be read from environment (Cloud Run/Render sets this)
    PORT = int(os.environ.get("PORT", 8080))

    # 🚀 WEBHOOK MODE (Cloud Run / Render)
    if SERVICE_URL:
        webhook_url = f"{SERVICE_URL}/{BOT_TOKEN}"
        logger.info(f"🌐 Webhook URL: {webhook_url}")
        logger.info(f"🔌 Port: {PORT}")
        logger.info("📡 Running in WEBHOOK mode...")
        logger.info("="*60)

        # Start webhook server - must listen on PORT for Cloud Run/Render
        # In python-telegram-bot 20.x, we need to initialize and start manually
        logger.info("✅ Initializing application...")
        await app.initialize()
        
        logger.info("✅ Starting application...")
        await app.start()
        
        logger.info("✅ Starting webhook server...")
        # start_webhook() starts the webhook server
        await app.updater.start_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=webhook_url,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )
        
        logger.info("✅ Webhook started successfully")
        
        # Keep the application running
        # In Render, the service stays alive as long as the process is running
        # We use a simple infinite loop to keep the process alive
        try:
            while True:
                await asyncio.sleep(3600)  # Sleep for 1 hour
        except (KeyboardInterrupt, SystemExit):
            logger.info("🛑 Shutting down...")
            await app.stop()
            await app.shutdown()

    # 🖥️ POLLING MODE (Local Development)
    else:
        logger.info("💻 Running in POLLING mode")
        logger.info("="*60)
        await app.run_polling(allowed_updates=Update.ALL_TYPES)


# ================================================
# 🧠 نقطة التشغيل الرئيسية
# ================================================
if __name__ == "__main__":
    import os
    import sys
    
    # 🔍 تحديد نوع الاستضافة وإعداد المتغيرات المناسبة
    # Render uses RENDER_EXTERNAL_URL
    # Railway uses RAILWAY_STATIC_URL
    # Cloud Run uses SERVICE_URL
    SERVICE_URL = (os.environ.get("RENDER_EXTERNAL_URL") or
                   os.environ.get("RAILWAY_STATIC_URL") or
                   os.environ.get("SERVICE_URL", ""))
    PORT = int(os.environ.get("PORT", 8080))

    # Railway specific: تحديد نوع التشغيل
    RAILWAY_ENVIRONMENT = os.environ.get("RAILWAY_ENVIRONMENT", "")
    
    # ⚙️ السماح بـ nested event loops (مطلوب لـ run_webhook في Cloud Run/Render)
    nest_asyncio.apply()
    
    # 🚀 Cloud Run / Render mode: استخدام asyncio.run
    if SERVICE_URL:
        logger.info(f"🌐 Starting in Webhook mode (Cloud Run / Render)")
        logger.info(f"🔌 SERVICE_URL: {SERVICE_URL}")
        logger.info(f"🔌 PORT: {PORT}")
        
        try:
            # بدء البوت بشكل مباشر
            asyncio.run(main())
        except RuntimeError as e:
            if "Cannot close a running event loop" in str(e) or "asyncio.run() cannot be called from a running event loop" in str(e):
                # Cloud Run يدير event loop - استخدام طريقة بديلة
                logger.info("ℹ️ Event loop is managed by Cloud Run, using alternative start method")
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # إنشاء task جديد في loop موجود
                        asyncio.create_task(main())
                    else:
                        loop.run_until_complete(main())
                except Exception as alt_error:
                    logger.error(f"Alternative start method failed: {alt_error}", exc_info=True)
                    sys.exit(1)
            else:
                logger.error(f"Runtime error: {e}", exc_info=True)
                raise
        except Exception as e:
            logger.error(f"Fatal error in Cloud Run mode: {e}", exc_info=True)
            sys.exit(1)
    else:
        # 🖥️ Local mode: استخدام run_until_complete
        logger.info("💻 Starting in local polling mode")
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(main())
        except KeyboardInterrupt:
            logger.info("⚠️ Bot stopped manually")
            try:
                # 💾 حفظ قاعدة البيانات إلى Google Cloud Storage قبل الإغلاق
                from db.online_hosting_config import OnlineHostingConfig
                if OnlineHostingConfig.AUTO_SAVE_ON_SHUTDOWN:
                    try:
                        from db.persistent_storage import save_database_to_cloud
                        if save_database_to_cloud():
                            logger.info("✅ تم حفظ قاعدة البيانات إلى Google Cloud Storage")
                        else:
                            logger.warning("⚠️ فشل في حفظ قاعدة البيانات إلى السحابة")
                    except Exception as save_error:
                        logger.error(f"❌ خطأ في حفظ قاعدة البيانات: {save_error}")

                from db.session import close_connection
                close_connection()
            except Exception as cleanup_error:
                logger.error(f"❌ خطأ في تنظيف الموارد: {cleanup_error}")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
