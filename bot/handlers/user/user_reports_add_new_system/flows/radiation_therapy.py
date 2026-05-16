# =============================
# flows/radiation_therapy.py
# مسار جلسة إشعاعي - RADIATION THERAPY FLOW
# =============================

import logging
import calendar
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime, date

from ...user_reports_add_helpers import validate_text_input
from ..utils import _nav_buttons, _chunked

logger = logging.getLogger(__name__)

# استيراد الـ states من states.py مباشرة
try:
    from ..states import (
        RADIATION_THERAPY_TYPE,
        RADIATION_THERAPY_SESSION_NUMBER,
        RADIATION_THERAPY_REMAINING,
        RADIATION_THERAPY_NOTES,
        RADIATION_THERAPY_RETURN_DATE,
        RADIATION_THERAPY_RETURN_REASON,
        RADIATION_THERAPY_TRANSLATOR,
        RADIATION_THERAPY_CONFIRM,
    )
except ImportError:
    # Fallback: إذا فشل الاستيراد، نستخدم قيم افتراضية
    logger.warning("⚠️ Cannot import RADIATION_THERAPY states from states.py, using fallback")
    RADIATION_THERAPY_TYPE = 93
    RADIATION_THERAPY_SESSION_NUMBER = 94
    RADIATION_THERAPY_REMAINING = 95
    RADIATION_THERAPY_NOTES = 96
    RADIATION_THERAPY_RETURN_DATE = 97
    RADIATION_THERAPY_RETURN_REASON = 98
    RADIATION_THERAPY_TRANSLATOR = 99
    RADIATION_THERAPY_CONFIRM = 100

MONTH_NAMES_AR = {
    1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل",
    5: "مايو", 6: "يونيو", 7: "يوليو", 8: "أغسطس",
    9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر",
}

WEEKDAYS_AR = ["س", "ح", "ن", "ث", "ر", "خ", "ج"]

def init_states(states_dict):
    """تهيئة الـ states من الملف الرئيسي (deprecated - states يتم استيرادها مباشرة الآن)"""
    pass

# =============================
# Calendar Helper Functions
# =============================

def _build_radiation_calendar_markup(year: int, month: int):
    """بناء تقويم تاريخ الجلسة القادمة"""
    cal = calendar.Calendar(firstweekday=calendar.SATURDAY)
    weeks = cal.monthdayscalendar(year, month)
    today = datetime.now().date()

    keyboard = []

    # تقويم الشهر مع أزرار التنقل
    keyboard.append([
        InlineKeyboardButton("⬅️", callback_data=f"rad_cal_prev:{year}-{month:02d}"),
        InlineKeyboardButton(f"📅 {MONTH_NAMES_AR[month]} {year}", callback_data="noop"),
        InlineKeyboardButton("➡️", callback_data=f"rad_cal_next:{year}-{month:02d}"),
    ])

    # أيام الأسبوع
    keyboard.append([InlineKeyboardButton(d, callback_data="noop") for d in WEEKDAYS_AR])

    # أيام الشهر
    for week in weeks:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="noop"))
            else:
                current_date = date(year, month, day)
                if current_date < today:
                    # أيام ماضية - غير قابلة للاختيار
                    row.append(InlineKeyboardButton(f"·{day}·", callback_data="noop"))
                elif current_date == today:
                    # اليوم الحالي
                    row.append(InlineKeyboardButton(f"[{day}]", callback_data=f"rad_cal_day:{year}-{month:02d}-{day:02d}"))
                else:
                    # أيام مستقبلية
                    row.append(InlineKeyboardButton(str(day), callback_data=f"rad_cal_day:{year}-{month:02d}-{day:02d}"))
        keyboard.append(row)

    # أزرار التنقل
    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    text = (
        f"📅 **تاريخ الجلسة القادمة**\n\n"
        f"اختر تاريخ الجلسة القادمة من التقويم:"
    )

    return text, InlineKeyboardMarkup(keyboard)


async def _render_radiation_calendar(message_or_query, context, year=None, month=None):
    """عرض تقويم تاريخ الجلسة القادمة"""
    data_tmp = context.user_data.setdefault("report_tmp", {})
    if year is None or month is None:
        now = datetime.now()
        year = data_tmp.get("radiation_calendar_year", now.year)
        month = data_tmp.get("radiation_calendar_month", now.month)

    text, markup = _build_radiation_calendar_markup(year, month)
    data_tmp["radiation_calendar_year"] = year
    data_tmp["radiation_calendar_month"] = month

    if hasattr(message_or_query, 'edit_message_text'):
        await message_or_query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await message_or_query.reply_text(text, reply_markup=markup, parse_mode="Markdown")


def _build_radiation_hour_keyboard():
    """بناء لوحة اختيار الساعة — 24 ساعة كاملة، 4 في كل صف"""
    hours = []
    for h in range(24):
        if h == 0:
            label = "12 صباحاً"
        elif h < 12:
            label = f"{h} صباحاً"
        elif h == 12:
            label = "12 ظهراً"
        else:
            label = f"{h - 12} مساءً"
        hours.append((label, f"{h:02d}"))

    keyboard = []
    for i in range(0, len(hours), 4):
        keyboard.append([
            InlineKeyboardButton(label, callback_data=f"rad_time_hour:{val}")
            for label, val in hours[i:i+4]
        ])
    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="rad_cal_back"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])
    return InlineKeyboardMarkup(keyboard)


def _build_radiation_minute_keyboard(hour: str):
    """بناء لوحة اختيار الدقائق"""
    minute_options = ["00", "15", "30", "45"]
    keyboard = []

    hour_int = int(hour)
    if hour_int == 0:
        hour_display = "12"
    elif hour_int < 12:
        hour_display = str(hour_int)
    elif hour_int == 12:
        hour_display = "12"
    else:
        hour_display = str(hour_int - 12)

    for chunk in _chunked(minute_options, 2):
        row = [
            InlineKeyboardButton(
                f"{hour_display}:{min}", callback_data=f"rad_time_minute:{hour}:{min}"
            )
            for min in chunk
        ]
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="rad_time_back"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    return InlineKeyboardMarkup(keyboard)


# =============================
# Flow Start Function
# =============================

async def start_radiation_therapy_flow(message, context):
    """بدء مسار جلسة إشعاعي - الحقل 1: نوع الإشعاعي"""
    logger.info("=" * 80)
    logger.info("start_radiation_therapy_flow CALLED!")
    logger.info(f"RADIATION_THERAPY_TYPE = {RADIATION_THERAPY_TYPE}")
    logger.info("=" * 80)

    # التأكد من حفظ medical_action و current_flow
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "جلسة إشعاعي"
    context.user_data["report_tmp"]["current_flow"] = "radiation_therapy"
    context.user_data['_conversation_state'] = RADIATION_THERAPY_TYPE

    logger.info(f"✅ Set medical_action = 'جلسة إشعاعي'")
    logger.info(f"✅ Set current_flow = 'radiation_therapy'")
    logger.info(f"✅ Set _conversation_state = {RADIATION_THERAPY_TYPE}")

    try:
        await message.reply_text(
            "☢️ **نوع الإشعاعي**\n\n"
            "يرجى إدخال نوع العلاج الإشعاعي:\n"
            "(مثال: External Beam Radiation, Brachytherapy, IMRT, إلخ)",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        logger.info("✅ Sent radiation therapy type message")
    except Exception as e:
        logger.error(f"❌ Error sending message: {e}", exc_info=True)
        raise

    logger.info(f"✅ Returning state: {RADIATION_THERAPY_TYPE}")
    return RADIATION_THERAPY_TYPE


# =============================
# Handlers
# =============================

async def handle_radiation_therapy_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 1: نوع الإشعاعي"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=2)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال نوع الإشعاعي:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return RADIATION_THERAPY_TYPE

    context.user_data.setdefault("report_tmp", {})["radiation_therapy_type"] = text
    context.user_data["report_tmp"]["current_flow"] = "radiation_therapy"
    context.user_data["report_tmp"]["medical_action"] = "جلسة إشعاعي"
    context.user_data['_conversation_state'] = RADIATION_THERAPY_SESSION_NUMBER

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "🔢 **رقم الجلسة**\n\n"
        "يرجى إدخال رقم الجلسة الحالية:\n"
        "(مثال: 5 من 30)",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return RADIATION_THERAPY_SESSION_NUMBER


async def handle_radiation_therapy_session_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 2: رقم الجلسة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=1)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال رقم الجلسة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return RADIATION_THERAPY_SESSION_NUMBER

    session_number = text
    context.user_data.setdefault("report_tmp", {})["radiation_therapy_session_number"] = session_number
    context.user_data['_conversation_state'] = RADIATION_THERAPY_REMAINING

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "📊 **الجلسات المتبقية**\n\n"
        "يرجى إدخال عدد الجلسات المتبقية:\n"
        "(مثال: 25)",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return RADIATION_THERAPY_REMAINING


async def handle_radiation_therapy_remaining(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 3: الجلسات المتبقية - ثم عرض التقويم"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=1)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال عدد الجلسات المتبقية:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return RADIATION_THERAPY_REMAINING

    remaining_sessions = text
    context.user_data.setdefault("report_tmp", {})["radiation_therapy_remaining"] = remaining_sessions

    # التحقق من اكتمال الجلسات
    try:
        remaining = int(remaining_sessions)
        if remaining == 0:
            context.user_data["report_tmp"]["radiation_therapy_completed"] = True
        else:
            context.user_data["report_tmp"]["radiation_therapy_completed"] = False
    except ValueError:
        context.user_data["report_tmp"]["radiation_therapy_completed"] = False

    context.user_data['_conversation_state'] = RADIATION_THERAPY_NOTES

    # الانتقال لحقل الملاحظات / التوصيات
    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "📝 **ملاحظات أو توصيات**\n\n"
        "يرجى إدخال أي ملاحظات أو توصيات خاصة بالجلسة:\n"
        "(اختياري - أرسل 'تخطي' للمتابعة)",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return RADIATION_THERAPY_NOTES



async def handle_radiation_therapy_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 4: ملاحظات أو توصيات"""
    text = update.message.text.strip()

    # التحقق من التخطي
    if text.lower() in ["تخطي", "skip", "-"]:
        text = ""

    context.user_data.setdefault("report_tmp", {})["radiation_therapy_recommendations"] = text
    context.user_data['_conversation_state'] = RADIATION_THERAPY_RETURN_DATE

    # عرض التقويم لاختيار تاريخ الجلسة القادمة
    if text:
        await update.message.reply_text("✅ تم الحفظ")
    else:
        await update.message.reply_text("✅ تم التخطي")
    await _render_radiation_calendar(update.message, context)

    return RADIATION_THERAPY_RETURN_DATE

async def handle_radiation_calendar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة callbacks التقويم"""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("rad_cal_prev:"):
        # الشهر السابق
        parts = data.split(":")[1].split("-")
        year, month = int(parts[0]), int(parts[1])
        month -= 1
        if month < 1:
            month = 12
            year -= 1
        await _render_radiation_calendar(query, context, year, month)
        return RADIATION_THERAPY_RETURN_DATE

    elif data.startswith("rad_cal_next:"):
        # الشهر التالي
        parts = data.split(":")[1].split("-")
        year, month = int(parts[0]), int(parts[1])
        month += 1
        if month > 12:
            month = 1
            year += 1
        await _render_radiation_calendar(query, context, year, month)
        return RADIATION_THERAPY_RETURN_DATE

    elif data.startswith("rad_cal_day:"):
        # اختيار يوم
        date_str = data.split(":")[1]
        context.user_data.setdefault("report_tmp", {})["radiation_selected_date"] = date_str

        # عرض اختيار الساعة
        await query.edit_message_text(
            f"📅 **تاريخ الجلسة:** {date_str}\n\n"
            "⏰ **اختر وقت الجلسة:**",
            reply_markup=_build_radiation_hour_keyboard(),
            parse_mode="Markdown"
        )
        return RADIATION_THERAPY_RETURN_DATE

    elif data == "rad_cal_skip":
        # تخطي التقويم - إدخال يدوي
        await query.edit_message_text(
            "📅 **تاريخ الجلسة القادمة**\n\n"
            "يرجى إدخال تاريخ ووقت الجلسة القادمة:\n"
            "(الصيغة: YYYY-MM-DD HH:MM)\n"
            "مثال: 2025-12-15 10:00\n\n"
            "أو أرسل 'تخطي' للمتابعة بدون تحديد موعد",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        context.user_data["report_tmp"]["radiation_manual_date_input"] = True
        return RADIATION_THERAPY_RETURN_DATE

    elif data == "rad_cal_back":
        # الرجوع للتقويم
        await _render_radiation_calendar(query, context)
        return RADIATION_THERAPY_RETURN_DATE

    elif data.startswith("rad_time_hour:"):
        # اختيار الساعة - حفظ الوقت مباشرة بدون اختيار الدقائق
        hour = data.split(":")[1]
        minute = "00"

        date_str = context.user_data.get("report_tmp", {}).get("radiation_selected_date", "")
        time_str = f"{hour}:{minute}"

        # حفظ التاريخ والوقت
        context.user_data.setdefault("report_tmp", {})["followup_date"] = date_str
        context.user_data["report_tmp"]["followup_time"] = time_str
        context.user_data["report_tmp"]["radiation_therapy_return_date"] = f"{date_str} {time_str}"

        context.user_data['_conversation_state'] = RADIATION_THERAPY_RETURN_REASON

        completed = context.user_data.get("report_tmp", {}).get("radiation_therapy_completed", False)

        if completed:
            await query.edit_message_text(
                f"✅ تم اختيار الموعد: {date_str} {time_str}\n\n"
                "📝 **ملاحظات نهائية**\n\n"
                "يرجى إدخال أي ملاحظات نهائية عن اكتمال العلاج:\n"
                "(اختياري - أرسل 'تخطي' للمتابعة)",
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                f"✅ تم اختيار الموعد: {date_str} {time_str}\n\n"
                "📝 **سبب العودة**\n\n"
                "يرجى إدخال سبب العودة للجلسة القادمة:",
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )

        return RADIATION_THERAPY_RETURN_REASON

    elif data == "rad_time_back":
        # الرجوع للتقويم من اختيار الساعة
        await _render_radiation_calendar(query, context)
        return RADIATION_THERAPY_RETURN_DATE

    return RADIATION_THERAPY_RETURN_DATE


async def handle_radiation_therapy_return_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 4: تاريخ العودة والوقت - إدخال يدوي"""
    text = update.message.text.strip()

    # التحقق من التخطي
    if text.lower() in ["تخطي", "skip", "-"]:
        context.user_data.setdefault("report_tmp", {})["followup_date"] = None
        context.user_data["report_tmp"]["followup_time"] = None
        context.user_data["report_tmp"]["radiation_therapy_return_date"] = "غير محدد"
    else:
        # محاولة تحليل التاريخ والوقت
        try:
            dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
            context.user_data.setdefault("report_tmp", {})["followup_date"] = str(dt.date())
            context.user_data["report_tmp"]["followup_time"] = dt.strftime("%H:%M")
            context.user_data["report_tmp"]["radiation_therapy_return_date"] = text
        except ValueError:
            # إذا فشل التحليل، نحفظه كنص
            context.user_data.setdefault("report_tmp", {})["radiation_therapy_return_date"] = text
            context.user_data["report_tmp"]["followup_date"] = text
            context.user_data["report_tmp"]["followup_time"] = None

    context.user_data['_conversation_state'] = RADIATION_THERAPY_RETURN_REASON

    completed = context.user_data.get("report_tmp", {}).get("radiation_therapy_completed", False)

    if completed:
        await update.message.reply_text(
            "✅ تم الحفظ\n\n"
            "📝 **ملاحظات نهائية**\n\n"
            "يرجى إدخال أي ملاحظات نهائية عن اكتمال العلاج:\n"
            "(اختياري - أرسل 'تخطي' للمتابعة)",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "✅ تم الحفظ\n\n"
            "📝 **سبب العودة**\n\n"
            "يرجى إدخال سبب العودة للجلسة القادمة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )

    return RADIATION_THERAPY_RETURN_REASON


async def handle_radiation_therapy_return_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 5: سبب العودة أو الملاحظات النهائية"""
    text = update.message.text.strip()

    completed = context.user_data.get("report_tmp", {}).get("radiation_therapy_completed", False)

    # التحقق من التخطي
    if text.lower() in ["تخطي", "skip", "-"]:
        text = ""

    if completed:
        context.user_data.setdefault("report_tmp", {})["radiation_therapy_final_notes"] = text
        context.user_data["report_tmp"]["followup_reason"] = f"اكتمال العلاج الإشعاعي. ملاحظات: {text}" if text else "اكتمال العلاج الإشعاعي"
    else:
        context.user_data.setdefault("report_tmp", {})["followup_reason"] = text if text else "جلسة إشعاعي"
        context.user_data["report_tmp"]["radiation_therapy_return_reason"] = text

    context.user_data['_conversation_state'] = RADIATION_THERAPY_TRANSLATOR

    await update.message.reply_text("✅ تم الحفظ")

    from .shared import show_translator_selection
    gate_result = await show_translator_selection(update.message, context, "radiation_therapy")
    if gate_result == "MEDICAL_REPORT_ASK":
        return gate_result
    return RADIATION_THERAPY_TRANSLATOR


# =============================
# Export
# =============================

__all__ = [
    'start_radiation_therapy_flow',
    'handle_radiation_therapy_type',
    'handle_radiation_therapy_session_number',
    'handle_radiation_therapy_remaining',
    'handle_radiation_therapy_notes',
    'handle_radiation_therapy_return_date',
    'handle_radiation_therapy_return_reason',
    'handle_radiation_calendar_callback',
    '_render_radiation_calendar',
    'init_states',
]
