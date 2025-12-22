# =============================
# bot/handlers/admin/admin_notes.py
# 📝 ملاحظات إدارية — بسيط + زر إلغاء Inline
# =============================
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
)
from db.session import SessionLocal
from db.models import AdminNote

ASK_NOTE = 800

def _cancel_inline():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ إلغاء المحادثة", callback_data="admin_cancel")]]
    )

async def start_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✍️ أرسل الملاحظة الإدارية:", reply_markup=_cancel_inline())
    return ASK_NOTE

async def receive_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if not txt:
        await update.message.reply_text("⚠️ أرسل نصًا صالحًا.", reply_markup=_cancel_inline())
        return ASK_NOTE

    with SessionLocal() as s:
        s.add(AdminNote(note_text=txt))
        s.commit()

    await update.message.reply_text("✅ تمت إضافة الملاحظة.")
    return ConversationHandler.END

async def admin_cancel_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("❌ تم إلغاء المحادثة.")
    return ConversationHandler.END

def register(app):
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📝 ملاحظات إدارية$"), start_notes)],
        states={
            ASK_NOTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_note),
                CallbackQueryHandler(admin_cancel_inline, pattern="^admin_cancel$"),
            ]
        },
        fallbacks=[CallbackQueryHandler(admin_cancel_inline, pattern="^admin_cancel$")],
        name="admin_notes_conv",
        per_chat=True,
        per_user=True,
        per_message=True,  # ✅ تفعيل per_message لتجنب التحذيرات
    )
    app.add_handler(conv)
