# =============================
# flows/app_reschedule.py
# مسار تأجيل موعد - APPOINTMENT RESCHEDULE FLOW
# =============================

import logging
import calendar
from datetime import datetime, date
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from ..states import APP_RESCHEDULE_REASON, APP_RESCHEDULE_RETURN_DATE, APP_RESCHEDULE_RETURN_REASON, APP_RESCHEDULE_TRANSLATOR
from ..utils import _nav_buttons, MONTH_NAMES_AR, WEEKDAYS_AR
from ...user_reports_add_helpers import validate_text_input
from .shared import show_translator_selection

logger = logging.getLogger(__name__)

TIMEZONE = 'Asia/Kolkata'


async def start_appointment_reschedule_flow(message, context):
    """بدء مسار تأجيل موعد"""
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "تأجيل موعد"
    context.user_data["report_tmp"]["current_flow"] = "appointment_reschedule"
    context.user_data['_conversation_state'] = APP_RESCHEDULE_REASON

    await message.reply_text(
        "📅 **تأجيل موعد**\n\n"
        "يرجى إدخال سبب تأجيل الموعد:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return APP_RESCHEDULE_REASON


async def handle_app_reschedule_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج سبب تأجيل الموعد"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال سبب تأجيل الموعد:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return APP_RESCHEDULE_REASON

    context.user_data.setdefault("report_tmp", {})
    context.user_data["report_tmp"]["app_reschedule_reason"] = text
    context.user_data["report_tmp"]["current_flow"] = "appointment_reschedule"
    context.user_data["report_tmp"]["medical_action"] = "تأجيل موعد"

    logger.info(f"💾 تم حفظ app_reschedule_reason: {text}")

    await update.message.reply_text("✅ تم الحفظ")
    await _show_reschedule_calendar(update.message, context)

    context.user_data['_conversation_state'] = APP_RESCHEDULE_RETURN_DATE
    return APP_RESCHEDULE_RETURN_DATE


async def _show_reschedule_calendar(message, context, year=None, month=None):
    """عرض تقويم لاختيار تاريخ العودة — ✅ شكل موحَّد تماماً مع بقية شاشات
    "تاريخ العودة" في كل المسارات (نفس رأس الشهر بالأسهم، نفس مسمّيات أيام
    الأسبوع، علامة 📍 لليوم، أرقام بصفر، إخفاء الأيام الماضية). مُعرّفات
    الاستدعاء (reschedule_cal_day / reschedule_cal_nav) لم تتغيّر إطلاقاً."""
    now = datetime.now(ZoneInfo(TIMEZONE))
    today = now.date()
    year = year or now.year
    month = month or now.month

    cal = calendar.Calendar(firstweekday=calendar.SATURDAY)
    weeks = cal.monthdayscalendar(year, month)

    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1

    keyboard = []
    keyboard.append([
        InlineKeyboardButton("⬅️", callback_data=f"reschedule_cal_nav:prev:{prev_year}:{prev_month}"),
        InlineKeyboardButton(f"{MONTH_NAMES_AR.get(month, month)} {year}", callback_data="noop"),
        InlineKeyboardButton("➡️", callback_data=f"reschedule_cal_nav:next:{next_year}:{next_month}"),
    ])
    keyboard.append([InlineKeyboardButton(d, callback_data="noop") for d in WEEKDAYS_AR])

    for week in weeks:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="noop"))
            else:
                current_date = date(year, month, day)
                date_str = f"{year}-{month:02d}-{day:02d}"
                if current_date < today:
                    row.append(InlineKeyboardButton(" ", callback_data="noop"))
                elif current_date == today:
                    row.append(InlineKeyboardButton(f"📍{day:02d}", callback_data=f"reschedule_cal_day:{date_str}"))
                else:
                    row.append(InlineKeyboardButton(f"{day:02d}", callback_data=f"reschedule_cal_day:{date_str}"))
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel"),
    ])

    text = f"📅 **تاريخ العودة**\n\n{MONTH_NAMES_AR.get(month, str(month))} {year}\n\nاختر التاريخ من التقويم:"
    await message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def handle_reschedule_calendar_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج التنقل في تقويم تأجيل الموعد"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    direction = parts[1]
    year = int(parts[2])
    month = int(parts[3])

    await query.delete_message()
    await _show_reschedule_calendar(query.message, context, year, month)

    return APP_RESCHEDULE_RETURN_DATE


async def handle_reschedule_calendar_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار تاريخ العودة - يعرض اختيار الوقت بعد التاريخ"""
    query = update.callback_query
    await query.answer()

    date_str = query.data.split(":", 1)[1]
    try:
        return_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        context.user_data["report_tmp"]["app_reschedule_return_date"] = return_date
        context.user_data["report_tmp"]["followup_date"] = return_date
        context.user_data["report_tmp"]["_pending_followup_date"] = return_date

        keyboard = []
        common_morning = [
            ("🌅 8:00 صباحاً", "08"),
            ("🌅 9:00 صباحاً", "09"),
            ("🌅 10:00 صباحاً", "10"),
            ("🌅 11:00 صباحاً", "11"),
        ]
        keyboard.append([InlineKeyboardButton(label,
            callback_data=f"followup_time_hour:{val}") for label, val in common_morning])

        keyboard.append([InlineKeyboardButton("☀️ 12:00 ظهراً", callback_data="followup_time_hour:12")])

        common_afternoon = [
            ("🌆 1:00 مساءً", "13"),
            ("🌆 2:00 مساءً", "14"),
            ("🌆 3:00 مساءً", "15"),
            ("🌆 4:00 مساءً", "16"),
        ]
        keyboard.append([InlineKeyboardButton(label,
            callback_data=f"followup_time_hour:{val}") for label, val in common_afternoon])

        keyboard.append([InlineKeyboardButton("🕐 أوقات أخرى", callback_data="followup_time_hour:more")])
        keyboard.append([
            InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
            InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
        ])

        await query.edit_message_text(
            f"✅ **تم اختيار التاريخ**\n\n"
            f"📅 **التاريخ:**\n"
            f"{date_str}\n\n"
            f"🕐 **الوقت** (اختياري)\n\n"
            f"اختر الساعة:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

        context.user_data['_conversation_state'] = APP_RESCHEDULE_RETURN_DATE
        return APP_RESCHEDULE_RETURN_DATE

    except ValueError:
        await query.answer("صيغة غير صالحة", show_alert=True)
        return APP_RESCHEDULE_RETURN_DATE


async def handle_app_reschedule_return_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج سبب العودة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return APP_RESCHEDULE_RETURN_REASON

    context.user_data["report_tmp"]["app_reschedule_return_reason"] = text
    context.user_data["report_tmp"]["followup_reason"] = text

    await update.message.reply_text("✅ تم الحفظ")
    await show_translator_selection(update.message, context, "appointment_reschedule")

    context.user_data['_conversation_state'] = APP_RESCHEDULE_TRANSLATOR
    return APP_RESCHEDULE_TRANSLATOR


__all__ = [
    'start_appointment_reschedule_flow',
    'handle_app_reschedule_reason',
    '_show_reschedule_calendar',
    'handle_reschedule_calendar_nav',
    'handle_reschedule_calendar_day',
    'handle_app_reschedule_return_reason',
]


async def handle_view_reschedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض سبب تأجيل الموعد عند الضغط على الزر في مجموعة البث."""
    import logging as _logging
    _logger = _logging.getLogger(__name__)
    try:
        query = update.callback_query
        if not query or not query.data:
            return
        await query.answer()
        parts = query.data.split(':', 1)
        if len(parts) < 2:
            await query.message.reply_text("⚠️ لم يتم تحديد التقرير.")
            return
        try:
            report_id = int(parts[1])
        except Exception:
            await query.message.reply_text("⚠️ معرف تقرير غير صالح.")
            return

        from db.session import SessionLocal as _SL
        from db.models import Report as _Report

        with _SL() as s:
            report = s.query(_Report).filter_by(id=report_id).first()
            if not report:
                await query.message.reply_text("⚠️ لم يتم العثور على التقرير.")
                return
            reason = (
                getattr(report, 'app_reschedule_reason', None)
                or getattr(report, 'followup_reason', None)
            )
            if not reason or not str(reason).strip():
                await query.message.reply_text("ℹ️ لا يوجد سبب تأجيل مسجل لهذا التقرير.")
                return
            text = f"📅 **سبب تأجيل الموعد للتقرير #{report_id}:**\n\n{reason}"
            return_date = getattr(report, 'app_reschedule_return_date', None) or getattr(report, 'followup_date', None)
            if return_date:
                date_str = return_date.strftime('%Y-%m-%d') if hasattr(return_date, 'strftime') else str(return_date)
                text += f"\n\n📅 **موعد العودة:** {date_str}"
            return_reason = getattr(report, 'app_reschedule_return_reason', None)
            if return_reason and str(return_reason).strip():
                text += f"\n\n✍️ **سبب العودة:** {return_reason}"
            await query.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        _logger.exception(f"خطأ في handle_view_reschedule_callback: {e}")
        try:
            await update.callback_query.message.reply_text("⚠️ حدث خطأ أثناء جلب بيانات التأجيل.")
        except Exception:
            pass
