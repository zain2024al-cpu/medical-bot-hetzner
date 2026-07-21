# =============================
# flows/radiology.py
# مسار أشعة وفحوصات - RADIOLOGY FLOW
# =============================

import logging
import calendar
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from ..states import RADIOLOGY_TYPE, RADIOLOGY_DELIVERY_DATE, RADIOLOGY_TRANSLATOR
from ..utils import _nav_buttons, MONTH_NAMES_AR, WEEKDAYS_AR
from ...user_reports_add_helpers import validate_text_input
from .shared import show_translator_selection

logger = logging.getLogger(__name__)


def _build_radiology_calendar_markup(year: int, month: int):
    """بناء تقويم تاريخ تسليم نتائج الأشعة"""
    cal = calendar.Calendar(firstweekday=calendar.SATURDAY)
    weeks = cal.monthdayscalendar(year, month)
    today = datetime.now().date()

    keyboard = []
    keyboard.append([
        InlineKeyboardButton("⬅️", callback_data=f"radiology_cal_prev:{year}-{month:02d}"),
        InlineKeyboardButton(f"{MONTH_NAMES_AR.get(month, month)} {year}", callback_data="noop"),
        InlineKeyboardButton("➡️", callback_data=f"radiology_cal_next:{year}-{month:02d}"),
    ])
    keyboard.append([InlineKeyboardButton(day, callback_data="noop") for day in WEEKDAYS_AR])

    for week in weeks:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="noop"))
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                    if date_obj < today:
                        row.append(InlineKeyboardButton(" ", callback_data="noop"))
                    elif date_obj == today:
                        row.append(InlineKeyboardButton(f"📍{day:02d}", callback_data=f"radiology_cal_day:{date_str}"))
                    else:
                        row.append(InlineKeyboardButton(f"{day:02d}", callback_data=f"radiology_cal_day:{date_str}"))
                except Exception:
                    row.append(InlineKeyboardButton(" ", callback_data="noop"))
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    text = f"📅 **تاريخ العودة**\n\n{MONTH_NAMES_AR.get(month, str(month))} {year}\n\nاختر التاريخ من التقويم:"
    return text, InlineKeyboardMarkup(keyboard)


async def _render_radiology_calendar(message_or_query, context, year=None, month=None):
    """عرض تقويم تاريخ تسليم نتائج الأشعة"""
    data_tmp = context.user_data.setdefault("report_tmp", {})
    if year is None or month is None:
        now = datetime.now()
        year = now.year
        month = now.month

    text, markup = _build_radiology_calendar_markup(year, month)
    data_tmp["radiology_calendar_year"] = year
    data_tmp["radiology_calendar_month"] = month

    if hasattr(message_or_query, 'edit_message_text'):
        await message_or_query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await message_or_query.reply_text(text, reply_markup=markup, parse_mode="Markdown")


async def start_radiology_flow(message, context):
    """بدء مسار أشعة وفحوصات"""
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "أشعة وفحوصات"
    context.user_data["report_tmp"]["current_flow"] = "radiology"
    context.user_data['_conversation_state'] = RADIOLOGY_TYPE

    await message.reply_text(
        "🔬 **نوع الأشعة والفحوصات**\n\n"
        "يرجى إدخال نوع الأشعة أو الفحوصات:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return RADIOLOGY_TYPE


async def handle_radiology_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 1: نوع الأشعة"""
    context.user_data['_conversation_state'] = RADIOLOGY_TYPE

    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال نوع الأشعة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return RADIOLOGY_TYPE

    context.user_data.setdefault("report_tmp", {})["radiology_type"] = text
    context.user_data["report_tmp"]["current_flow"] = "radiology"
    context.user_data["report_tmp"]["medical_action"] = "أشعة وفحوصات"

    await update.message.reply_text("✅ تم الحفظ")
    await _render_radiology_calendar(update.message, context)

    context.user_data['_conversation_state'] = RADIOLOGY_DELIVERY_DATE
    return RADIOLOGY_DELIVERY_DATE


async def handle_radiology_calendar_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج التنقل في تقويم radiology"""
    query = update.callback_query
    await query.answer()
    prefix, ym = query.data.split(":", 1)
    year, month = map(int, ym.split("-"))
    if prefix == "radiology_cal_prev":
        month -= 1
        if month < 1:
            month = 12
            year -= 1
    elif prefix == "radiology_cal_next":
        month += 1
        if month > 12:
            month = 1
            year += 1
    await _render_radiology_calendar(query.message, context, year, month)
    context.user_data['_conversation_state'] = RADIOLOGY_DELIVERY_DATE
    return RADIOLOGY_DELIVERY_DATE


async def handle_radiology_calendar_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار تاريخ تسليم نتائج الأشعة"""
    query = update.callback_query
    await query.answer()
    date_str = query.data.split(":", 1)[1]
    try:
        delivery_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        context.user_data.setdefault("report_tmp", {})["radiology_delivery_date"] = delivery_date
        context.user_data["report_tmp"]["followup_date"] = delivery_date
        context.user_data["report_tmp"]["followup_reason"] = "تسليم نتائج الأشعة والفحوصات"

        days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
        day_name = days_ar.get(delivery_date.weekday(), '')
        date_display = f"📅 {delivery_date.strftime('%d')} {MONTH_NAMES_AR.get(delivery_date.month, delivery_date.month)} {delivery_date.year} ({day_name})"

        await query.edit_message_text(
            f"✅ **تم اختيار التاريخ**\n\n"
            f"📅 **تاريخ التسليم:**\n"
            f"{date_display}"
        )
        await show_translator_selection(query.message, context, "radiology")

        context.user_data['_conversation_state'] = RADIOLOGY_TRANSLATOR
        return RADIOLOGY_TRANSLATOR
    except ValueError:
        await query.answer("صيغة غير صالحة", show_alert=True)
        return RADIOLOGY_DELIVERY_DATE


__all__ = [
    'start_radiology_flow',
    'handle_radiology_type',
    'handle_radiology_calendar_nav',
    'handle_radiology_calendar_day',
    '_render_radiology_calendar',
    '_build_radiology_calendar_markup',
]
