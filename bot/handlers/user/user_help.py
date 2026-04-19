# =============================
# bot/handlers/user/user_help.py
# 🔄 تحديث الصفحة للمستخدم والأدمن
# =============================

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from bot.shared_auth import ensure_approved, is_admin
from bot.keyboards import user_main_kb


async def user_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تحديث الصفحة وإعادة عرض القائمة الرئيسية للمستخدم أو الأدمن."""
    user_id = update.effective_user.id
    
    # التحقق إذا كان أدمن
    if is_admin(user_id):
        from bot.handlers.admin.admin_start import send_admin_panel

        await send_admin_panel(update, first_text="✅ تم تحديث الصفحة")
        return
    
    # للمستخدم العادي
    if not await ensure_approved(update, context):
        return
    
    await update.message.reply_text(
        "✅ تم تحديث الصفحة",
        reply_markup=user_main_kb()
    )


def register(app):
    app.add_handler(CommandHandler("refresh", user_refresh))
    # تم حذف معالج زر "تحديث الصفحة" من لوحة المستخدم
    # app.add_handler(MessageHandler(filters.Regex("^🔄 تحديث الصفحة$"), user_refresh))
