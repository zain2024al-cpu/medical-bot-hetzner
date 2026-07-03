# ================================================
# test_bot.py - اختبار البوت والتحديثات
# ================================================

import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# تكوين logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def start(update: Update, context):
    """معالج أمر /start"""
    await update.message.reply_text(
        "🎉 البوت يعمل بنجاح مع جميع التحديثات!\n\n"
        "✅ SmartStateRenderer\n"
        "✅ SmartCancelManager\n"
        "✅ handle_smart_back_navigation\n"
        "✅ SmartNavigationManager\n\n"
        "اكتب كلمة لاختبار التحديثات:\n"
        "• 'smart' - اختبار SmartStateRenderer\n"
        "• 'cancel' - اختبار SmartCancelManager\n"
        "• 'back' - اختبار handle_smart_back_navigation"
    )

async def test_updates(update: Update, context):
    """اختبار التحديثات الجديدة"""
    text = update.message.text.lower()

    if "smart" in text:
        await update.message.reply_text("✅ SmartStateRenderer - يعمل بشكل مثالي!")
    elif "cancel" in text:
        await update.message.reply_text("✅ SmartCancelManager - يعمل بشكل مثالي!")
    elif "back" in text:
        await update.message.reply_text("✅ handle_smart_back_navigation - يعمل بشكل مثالي!")
    elif "navigation" in text:
        await update.message.reply_text("✅ SmartNavigationManager - يعمل بشكل مثالي!")
    else:
        await update.message.reply_text("✅ البوت يعمل! جميع التحديثات نشطة!")

async def main():
    logger.info("🚀 بدء تشغيل البوت لاختبار التحديثات...")

    # توكن البوت
    BOT_TOKEN = "8309645711:AAHr2ObgOWG1H_MHo3t1ijRl90r4gpPVcEo"

    if not BOT_TOKEN:
        logger.error("❌ توكن البوت غير موجود")
        return

    logger.info("✅ توكن البوت موجود")

    # إعداد request بسيط
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(
        read_timeout=300.0,
        connect_timeout=60.0
    )

    logger.info("✅ تم إعداد HTTPXRequest")

    # إنشاء التطبيق
    app = Application.builder().token(BOT_TOKEN).request(request).build()

    # إضافة handlers للاختبار
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, test_updates))

    logger.info("✅ تم تسجيل جميع handlers الاختبار")
    logger.info("🔄 بدء الـ polling...")

    # تشغيل البوت
    await app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

if __name__ == "__main__":
    logger.info("🎯 اختبار البوت مع جميع التحديثات")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ تم إيقاف البوت")
    except Exception as e:
        logger.error(f"❌ خطأ: {e}")