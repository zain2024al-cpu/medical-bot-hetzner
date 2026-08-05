# =============================
# bot/handlers/user/user_search_basic.py
# 🔍 البحث في التقارير - Inline Search
# =============================

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    filters,
)
from bot.shared_auth import ensure_approved
from db.session import SessionLocal
from db.models import Report, Patient, Hospital, Department, Doctor
from datetime import datetime
import hashlib

SELECT_FIELD, ENTER_QUERY, SHOW_RESULTS = range(3)


def _cancel_inline():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ إلغاء المحادثة", callback_data="abort")]]
    )


async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """البحث معطل مؤقتاً"""
    if not await ensure_approved(update, context):
        return ConversationHandler.END
    
    await update.message.reply_text(
        "⚠️ **البحث عن حالة**\n\n"
        "📋 هذه الميزة معطلة مؤقتاً\n"
        "🔧 يتم العمل على تحسينها\n\n"
        "💡 يمكنك استخدام:\n"
        "   • طباعة التقارير من القائمة الرئيسية\n"
        "   • تحليل البيانات",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


async def handle_view_patient_reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معطل مؤقتاً"""
    if not await ensure_approved(update, context):
        return
    
    try:
        await update.effective_message.reply_text(
            "⚠️ **البحث عن حالة معطل مؤقتاً**\n\n"
            "📋 يرجى استخدام طباعة التقارير من القائمة الرئيسية",
            parse_mode="Markdown"
        )
    except Exception:
        pass


async def handle_cancel_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء البحث"""
    query = update.callback_query
    await query.answer()
    
    context.user_data.pop("mode", None)
    
    await query.edit_message_text("❌ تم إلغاء البحث")
    return ConversationHandler.END


# تم إزالة الدوال القديمة - النظام الآن inline بالكامل ✅


def register(app):
    # تسجيل زر البحث
    app.add_handler(MessageHandler(filters.Regex("^🔍 بحث عن حالة$"), start_search))
    
    # تسجيل command لعرض تقارير المريض
    app.add_handler(CommandHandler("view_patient_reports", handle_view_patient_reports))
    
    # تسجيل زر الإلغاء
    app.add_handler(CallbackQueryHandler(handle_cancel_search, pattern="^cancel_search$"))
