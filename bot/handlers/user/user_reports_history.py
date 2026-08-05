# =============================
# bot/handlers/user/user_reports_history.py
# 📜 عرض سجل التقارير السابقة (مع زر إلغاء inline)
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
from db.models import Report, Patient, Hospital
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

SELECT_PERIOD = range(1)


def _cancel_inline():
    """زر الإلغاء inline"""
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء المحادثة", callback_data="abort")]])


def _period_kb():
    """خيارات الفترات الزمنية"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 اليوم", callback_data="period:today")],
        [InlineKeyboardButton("🗓 هذا الأسبوع", callback_data="period:week")],
        [InlineKeyboardButton("📆 هذا الشهر", callback_data="period:month")],
        [InlineKeyboardButton("📄 كل التقارير", callback_data="period:all")],
        [InlineKeyboardButton("❌ إلغاء المحادثة", callback_data="abort")],
    ])


async def start_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء استعراض السجل"""
    if not await ensure_approved(update, context):
        return ConversationHandler.END

    await update.message.reply_text("📜 اختر الفترة الزمنية لعرض التقارير:", reply_markup=_period_kb())
    return SELECT_PERIOD


async def handle_period_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض التقارير حسب الفترة"""
    q = update.callback_query
    await q.answer()

    if q.data == "abort":
        await q.edit_message_text("❌ تم إلغاء المحادثة.")
        return ConversationHandler.END

    period = q.data.split(":")[1]
    user = update.effective_user
    now = datetime.now()

    start_date = None
    if period == "today":
        start_date = datetime(now.year, now.month, now.day)
    elif period == "week":
        start_date = datetime(now.year, now.month, now.day - 7)
    elif period == "month":
        start_date = datetime(now.year, now.month, 1)
    elif period == "all":
        start_date = None

    with SessionLocal() as s:
        # البحث عن المترجم أولاً
        translator = s.query(Translator).filter_by(tg_user_id=user.id).first()
        if not translator:
            await q.edit_message_text("⚠️ لم يتم العثور على بيانات المترجم.")
            return ConversationHandler.END
        
        q_reports = s.query(Report).filter(Report.translator_id == translator.id)
        if start_date:
            q_reports = q_reports.filter(Report.report_date >= start_date)
        reports = q_reports.order_by(Report.report_date.desc()).limit(20).all()

        if not reports:
            await q.edit_message_text("⚠️ لا توجد تقارير في هذه الفترة.", reply_markup=_cancel_inline())
            return ConversationHandler.END

        text = "📜 <b>سجل التقارير:</b>\n\n"
        MONTH_NAMES_AR = {1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل", 5: "مايو", 6: "يونيو", 7: "يوليو", 8: "أغسطس", 9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر"}
        days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
        
        for r in reports:
            p_name = s.get(Patient, r.patient_id).full_name if r.patient_id else "—"
            h_name = s.get(Hospital, r.hospital_id).name if r.hospital_id else "—"
            
            # تنسيق التاريخ والوقت بصيغة 12 ساعة
            if r.report_date:
                date_obj = r.report_date
                hour = date_obj.hour
                minute = date_obj.minute
                if hour == 0:
                    time_str = f"12:{minute:02d} صباحاً"
                elif hour < 12:
                    time_str = f"{hour}:{minute:02d} صباحاً"
                elif hour == 12:
                    time_str = f"12:{minute:02d} ظهراً"
                else:
                    time_str = f"{hour-12}:{minute:02d} مساءً"
                
                day_name = days_ar.get(date_obj.weekday(), '')
                date_str = f"{date_obj.strftime('%d')} {MONTH_NAMES_AR.get(date_obj.month, date_obj.month)} {date_obj.year} ({day_name}) - {time_str}"
            else:
                date_str = "—"
            
            text += (
                f"📅🕐 {date_str}\n"
                f"👤 {p_name}\n"
                f"🏥 {h_name}\n"
                f"💬 {r.complaint_text or '—'}\n"
                f"🧾 {r.doctor_decision or '—'}\n\n"
            )

        await q.edit_message_text(text, parse_mode="HTML")

    context.user_data.clear()
    return ConversationHandler.END


async def handle_abort_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """زر الإلغاء inline"""
    q = update.callback_query
    await q.answer()
    context.user_data.clear()
    try:
        await q.edit_message_text("❌ تم إلغاء المحادثة.")
    except Exception:
        logger.debug("تم تجاهل استثناء في handle_abort_callback", exc_info=True)
    return ConversationHandler.END


async def cancel_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء المحادثة عند كتابة /cancel"""
    context.user_data.clear()
    await update.message.reply_text("❌ تم إلغاء المحادثة.")
    return ConversationHandler.END


def register(app):
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📜 سجل التقارير$"), start_history)],
        states={
            SELECT_PERIOD: [
                CallbackQueryHandler(handle_period_choice, pattern=r"^period:"),
                CallbackQueryHandler(handle_abort_callback, pattern="^abort$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_text)],
        name="user_history_conv",
        per_chat=True,
        per_user=True,
        per_message=False,  # ✅ False لأن entry point هو MessageHandler
    )
    app.add_handler(conv)
