# ================================================
# bot/handlers/shared/shared_refresh.py
# 🔄 زر تحديث الصفحة المشترك (للجميع)
# ================================================

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from bot.shared_auth import is_admin, is_user_approved


async def handle_refresh_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    تحديث الصفحة وإلغاء أي عملية جارية
    يعمل للأدمن والمستخدمين العاديين
    """
    user = update.effective_user
    tg_id = user.id
    
    # مسح جميع البيانات المؤقتة
    context.user_data.clear()
    
    # التحقق من نوع المستخدم
    if is_admin(tg_id):
        # للأدمن — لوحة المفاتيح السفلية فقط
        context.chat_data.clear()
        from bot.handlers.admin.admin_start import send_admin_panel

        await send_admin_panel(
            update,
            first_text=(
                "🔄 تم تحديث الصفحة بنجاح!\n\n"
                "✅ تم إلغاء جميع العمليات الجارية.\n"
                "✅ تم مسح جميع البيانات المؤقتة.\n\n"
                "اختر خياراً جديداً:"
            ),
        )
    else:
        # للمستخدمين العاديين
        if not is_user_approved(tg_id):
            await update.message.reply_text(
                "⏳ **بانتظار الموافقة**\n\n"
                "طلبك قيد المراجعة من قبل الإدارة.",
                parse_mode="Markdown"
            )
            return
        
        from bot.keyboards import user_main_kb
        
        await update.message.reply_text(
            "🔄 **تم تحديث الصفحة بنجاح!**\n\n"
            "✅ تم إلغاء جميع العمليات الجارية.\n"
            "✅ الصفحة نظيفة الآن.\n\n"
            "اختر خياراً جديداً:",
            reply_markup=user_main_kb(),
            parse_mode="Markdown"
        )


def register(app):
    """تسجيل handler زر التحديث"""
    app.add_handler(MessageHandler(filters.Regex("^🔄 تحديث الصفحة$"), handle_refresh_page))


































