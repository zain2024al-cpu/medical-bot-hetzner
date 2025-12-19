# =============================
# bot/handlers/admin/admin_users.py
# 👑 أزرار قبول ورفض المستخدمين
# =============================
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler
from db.session import SessionLocal
from db.models import Translator
from datetime import datetime

async def handle_user_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = int(data.split(":")[1])

    with SessionLocal() as s:
        tr = s.query(Translator).filter_by(tg_user_id=user_id).first()

        if not tr:
            await query.edit_message_text("⚠️ المستخدم لم يعد موجوداً في قاعدة البيانات.")
            return

        if data.startswith("approve:"):
            tr.is_approved = True
            tr.updated_at = datetime.now()
            # حفظ في SQLite
            s.commit()
            await query.edit_message_text(f"✅ تم قبول المستخدم: {tr.full_name}")

            # إخطار المستخدم بأنه تم قبوله
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="🎉 تم قبولك من قبل الإدارة! يمكنك الآن استخدام النظام."
                )
            except Exception:
                pass

        elif data.startswith("reject:"):
            # حذف من SQLite
            user_name = tr.full_name
            s.delete(tr)
            s.commit()
            await query.edit_message_text(f"❌ تم رفض المستخدم: {user_name}")

def register(app):
    app.add_handler(CallbackQueryHandler(handle_user_approval, pattern="^(approve|reject):"))
