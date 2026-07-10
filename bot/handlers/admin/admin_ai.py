from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from services.ai_engine import analyze_reports
from db.models import Report, Patient, Hospital  # ✅ إزالة Case واستبدال بـ Report
from bot.shared_utils import summarize_text
from bot.handlers.admin.decorators import require_admin

# ==========================================
# 📊 تحليل التقارير الطبية عبر الذكاء الاصطناعي
# ==========================================

ASK_QUERY = range(1)

@require_admin
async def start_ai_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 أرسل النص أو التقرير الطبي الذي تريد تحليله:")
    return ASK_QUERY


@require_admin
async def process_ai_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text

    await update.message.reply_text("🔍 جاري تحليل النص...")

    # ✅ تحليل النص باستخدام وحدة الذكاء الاصطناعي
    result = await analyze_reports(user_input)

    # ✅ تلخيص النتيجة إذا كانت طويلة
    summary = summarize_text(result, max_length=600)

    await update.message.reply_text(f"🧠 **نتيجة التحليل:**\n{summary}")
    return ConversationHandler.END


@require_admin
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 تم إلغاء التحليل.")
    return ConversationHandler.END


def register(app):
    conv = ConversationHandler(
        entry_points=[CommandHandler("ai", start_ai_analysis)],
        states={
            ASK_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_ai_analysis)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv)
