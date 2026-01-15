# ================================================
# bot/admin_interface.py
# 🔹 واجهة الأدمن المنفصلة
# ================================================

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from bot.shared_auth import is_admin
from bot.keyboards import admin_main_kb
from bot.broadcast_control import toggle_broadcast, is_broadcast_enabled
# زر تفعيل/إيقاف إرسال التقارير
async def handle_toggle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("🚫 هذه الخاصية مخصصة للإدمن فقط.")
        return
    new_status = toggle_broadcast()
    status_text = "🟢 تم تفعيل إرسال التقارير للمجموعة" if new_status else "🔴 تم إيقاف إرسال التقارير للمجموعة"
    await update.message.reply_text(status_text, reply_markup=admin_main_kb())
from db.session import SessionLocal
from db.models import Translator


# 🟣 أمر /admin لفتح لوحة تحكم الأدمن
async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("🚫 هذه الخاصية مخصصة للإدمن فقط.")
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
            s.delete(translator)
            s.commit()
            await query.edit_message_text(f"🚫 تم رفض المستخدم: {translator.full_name}")

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
    
    await query.edit_message_text(
        f"👑 أهلاً {user.first_name}! لوحة التحكم جاهزة.",
        reply_markup=admin_main_kb()
    )

# دالة تحديث الصفحة للأدمن
async def admin_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تحديث الصفحة للأدمن"""
    user = update.effective_user
    
    # إذا لم يكن أدمن، لا ترسل رسالة - دع handler المستخدم يتولى الأمر
    if not is_admin(user.id):
        return
    
    await update.message.reply_text(
        "✅ تم تحديث الصفحة",
        reply_markup=admin_main_kb()
    )


# 🧩 تسجيل الهاندلرز الخاصة بلوحة التحكم
def register_admin_handlers(app):
    app.add_handler(CommandHandler("admin", admin_start))
    app.add_handler(MessageHandler(filters.Regex(r"^(🟢 تفعيل إرسال التقارير|🔴 إيقاف إرسال التقارير)$"), handle_toggle_broadcast))
    app.add_handler(CallbackQueryHandler(handle_user_approval, pattern="^(approve|reject):"))
    app.add_handler(CallbackQueryHandler(handle_back_to_main, pattern="^back_to_main$"))
