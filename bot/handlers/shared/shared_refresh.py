# ================================================
# bot/handlers/shared/shared_refresh.py
# 🔄 زر تحديث الصفحة المشترك (للجميع)
# ================================================

import logging
from telegram import Update
from telegram.error import TimedOut, NetworkError
from telegram.ext import ContextTypes, MessageHandler, filters
from bot.shared_auth import is_admin, is_user_approved

logger = logging.getLogger(__name__)


async def handle_refresh_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    تحديث الصفحة وإلغاء أي عملية جارية
    يعمل للأدمن والمستخدمين العاديين
    """
    try:
        user = update.effective_user
        tg_id = user.id
        
        # مسح جميع البيانات المؤقتة
        context.user_data.clear()
        
        # التحقق من نوع المستخدم
        if is_admin(tg_id):
            # للأدمن
            context.chat_data.clear()
            from bot.keyboards import admin_main_kb
            
            try:
                await update.message.reply_text(
                    "🔄 **تم تحديث الصفحة بنجاح!**\n\n"
                    "✅ تم إلغاء جميع العمليات الجارية.\n"
                    "✅ تم مسح جميع البيانات المؤقتة.\n\n"
                    "اختر خياراً جديداً:",
                    reply_markup=admin_main_kb(),
                    parse_mode="Markdown"
                )
            except (TimedOut, NetworkError) as e:
                logger.warning(f"⚠️ Timeout عند إرسال رسالة refresh للأدمن: {e}")
                # محاولة بدون keyboard
                try:
                    await update.message.reply_text(
                        "🔄 **تم تحديث الصفحة بنجاح!**\n\n"
                        "✅ تم إلغاء جميع العمليات الجارية.\n"
                        "✅ تم مسح جميع البيانات المؤقتة.",
                        parse_mode="Markdown"
                    )
                except:
                    pass
        else:
            # للمستخدمين العاديين
            if not is_user_approved(tg_id):
                try:
                    await update.message.reply_text(
                        "⏳ **بانتظار الموافقة**\n\n"
                        "طلبك قيد المراجعة من قبل الإدارة.",
                        parse_mode="Markdown"
                    )
                except (TimedOut, NetworkError) as e:
                    logger.warning(f"⚠️ Timeout عند إرسال رسالة approval: {e}")
                return
            
            from bot.keyboards import user_main_kb
            
            try:
                await update.message.reply_text(
                    "🔄 **تم تحديث الصفحة بنجاح!**\n\n"
                    "✅ تم إلغاء جميع العمليات الجارية.\n"
                    "✅ الصفحة نظيفة الآن.\n\n"
                    "اختر خياراً جديداً:",
                    reply_markup=user_main_kb(),
                    parse_mode="Markdown"
                )
            except (TimedOut, NetworkError) as e:
                logger.warning(f"⚠️ Timeout عند إرسال رسالة refresh للمستخدم: {e}")
                # محاولة بدون keyboard
                try:
                    await update.message.reply_text(
                        "🔄 **تم تحديث الصفحة بنجاح!**\n\n"
                        "✅ تم إلغاء جميع العمليات الجارية.\n"
                        "✅ الصفحة نظيفة الآن.",
                        parse_mode="Markdown"
                    )
                except:
                    pass
    except Exception as e:
        logger.error(f"❌ خطأ في handle_refresh_page: {e}", exc_info=True)
        # محاولة إرسال رسالة بسيطة فقط
        try:
            if update and update.message:
                await update.message.reply_text(
                    "⚠️ حدث خطأ. يرجى المحاولة مرة أخرى.",
                    parse_mode="Markdown"
                )
        except:
            pass


def register(app):
    """تسجيل handler زر التحديث"""
    app.add_handler(MessageHandler(filters.Regex("^🔄 تحديث الصفحة$"), handle_refresh_page))


































