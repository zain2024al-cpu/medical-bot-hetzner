# ================================================
# bot/handlers/admin/admin_start.py
# 🔹 لوحة تحكم الأدمن + نظام الموافقة على المستخدمين
# ================================================

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from bot.shared_auth import is_admin
from bot.keyboards import admin_main_kb
from db.session import SessionLocal
from db.models import Translator
from datetime import datetime


# 🟣 أمر /admin لفتح لوحة تحكم الأدمن
async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return
    await update.message.reply_text(
        f"👑 أهلاً {user.first_name}! لوحة التحكم جاهزة.",
        reply_markup=admin_main_kb()
    )


# ✅ دالة لمعالجة زر القبول / الرفض للمستخدمين الجدد
async def handle_user_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    action, user_id_str = data.split(":")
    user_id = int(user_id_str)

    with SessionLocal() as s:
        translator = s.query(Translator).filter_by(tg_user_id=user_id).first()
        if not translator:
            await query.edit_message_text("❌ لم يتم العثور على المستخدم في قاعدة البيانات.")
            return

        if action == "approve":
            translator.is_approved = True
            translator.updated_at = datetime.now()
            # حفظ في SQLite
            s.commit()
            await query.edit_message_text(f"✅ تم قبول المستخدم: {translator.full_name}")

            # إرسال إشعار للمستخدم المقبول
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="✅ تم قبولك! يمكنك الآن استخدام النظام."
                )
            except Exception:
                pass

        elif action == "reject":
            # حذف من SQLite
            user_name = translator.full_name
            s.delete(translator)
            s.commit()
            await query.edit_message_text(f"🚫 تم رفض المستخدم: {user_name}")

            # إرسال إشعار للمستخدم المرفوض
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="❌ تم رفض طلبك. يرجى التواصل مع الإدارة لمزيد من التفاصيل."
                )
            except Exception:
                pass


# دالة معالجة العودة للقائمة الرئيسية
async def handle_back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة زر العودة للقائمة الرئيسية"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    if not is_admin(user.id):
        await query.edit_message_text("🚫 هذه الخاصية مخصصة للإدمن فقط.")
        return
    
    # لا يمكن استخدام edit_message_text مع ReplyKeyboardMarkup
    # لذلك نرسل رسالة جديدة
    await query.message.reply_text(
        f"👑 أهلاً {user.first_name}! لوحة التحكم جاهزة.",
        reply_markup=admin_main_kb()
    )
    # محاولة حذف الرسالة القديمة
    try:
        await query.message.delete()
    except:
        pass


# 🧩 تسجيل الهاندلرز الخاصة بلوحة التحكم
def register(app):
    app.add_handler(CommandHandler("admin", admin_start))
    app.add_handler(MessageHandler(filters.Regex("^ℹ️ مساعدة$"), admin_start))
    app.add_handler(CallbackQueryHandler(handle_user_approval, pattern="^(approve|reject):"))
    app.add_handler(CallbackQueryHandler(handle_back_to_main, pattern="^back_to_main$"))
