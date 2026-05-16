# -*- coding: utf-8 -*-
"""
Discharge Flow Handlers
مسار خروج من المستشفى

يحتوي على:
- start_discharge_flow: بدء مسار خروج
- handle_discharge_type: معالجة نوع الخروج
- handle_discharge_admission_summary: معالجة ملخص الرقود
- handle_discharge_operation_details: معالجة تفاصيل العملية
- handle_discharge_operation_name_en: معالجة اسم العملية بالإنجليزي
- handle_discharge_followup_date_text: معالجة تاريخ العودة
- handle_discharge_followup_reason: معالجة سبب العودة
"""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

# Import states
from ..states import (
    DISCHARGE_TYPE, DISCHARGE_ADMISSION_SUMMARY, DISCHARGE_OPERATION_DETAILS,
    DISCHARGE_OPERATION_NAME_EN, DISCHARGE_FOLLOWUP_DATE, DISCHARGE_FOLLOWUP_REASON,
    DISCHARGE_TRANSLATOR
)

# Import utilities
from ..utils import _nav_buttons
from ...user_reports_add_helpers import validate_text_input, validate_english_only

# Import shared functions
from .shared import show_translator_selection

# Import calendar rendering function
from .new_consult import _render_followup_calendar

logger = logging.getLogger(__name__)

# =============================
# Flow Start Function
# =============================

async def start_discharge_flow(message, context):
    """بدء مسار خروج من المستشفى - اختيار النوع"""
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "خروج من المستشفى"
    context.user_data["report_tmp"]["current_flow"] = "discharge"
    context.user_data['_conversation_state'] = DISCHARGE_TYPE
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛏️ خروج بعد رقود طبي", callback_data="discharge_type:admission")],
        [InlineKeyboardButton("⚕️ خروج بعد عملية", callback_data="discharge_type:operation")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])

    await message.reply_text(
        "🏠 **خروج من المستشفى**\n\n"
        "اختر نوع الخروج:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    
    return DISCHARGE_TYPE


# =============================
# Handlers
# =============================

async def handle_discharge_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة نوع الخروج"""
    query = update.callback_query
    await query.answer()

    discharge_type = query.data.split(":", 1)[1]
    context.user_data["report_tmp"]["discharge_type"] = discharge_type

    if discharge_type == "admission":
        await query.edit_message_text("✅ اخترت: خروج بعد رقود طبي")
        await query.message.reply_text(
            "📋 **أبرز ما تم للحالة أثناء الرقود**\n\n"
            "يرجى إدخال ملخص ما تم للحالة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return DISCHARGE_ADMISSION_SUMMARY

    elif discharge_type == "operation":
        await query.edit_message_text("✅ اخترت: خروج بعد عملية")
        await query.message.reply_text(
            "⚕️ **تفاصيل العملية التي تمت للحالة**\n\n"
            "يرجى إدخال تفاصيل العملية:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return DISCHARGE_OPERATION_DETAILS


# فرع 1: خروج بعد رقود
async def handle_discharge_admission_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خروج بعد رقود - الحقل 1: ملخص الرقود"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=5, max_length=1000)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال ملخص ما تم للحالة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return DISCHARGE_ADMISSION_SUMMARY

    context.user_data["report_tmp"]["admission_summary"] = text

    # عرض تقويم تاريخ العودة (اختياري)
    await _render_followup_calendar(update.message, context)

    return DISCHARGE_FOLLOWUP_DATE


# فرع 2: خروج بعد عملية
async def handle_discharge_operation_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خروج بعد عملية - الحقل 1: تفاصيل العملية"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=5, max_length=1000)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال تفاصيل العملية:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return DISCHARGE_OPERATION_DETAILS

    context.user_data["report_tmp"]["operation_details"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "🔤 **اسم العملية بالإنجليزي**\n\n"
        "يرجى إدخال اسم العملية بالإنجليزي:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return DISCHARGE_OPERATION_NAME_EN


async def handle_discharge_operation_name_en(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خروج بعد عملية - الحقل 2: اسم العملية بالإنجليزي"""
    text = update.message.text.strip()
    valid, msg = validate_english_only(text, min_length=3, max_length=200)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال اسم العملية بالإنجليزي فقط:\n"
            f"مثال: Appendectomy",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return DISCHARGE_OPERATION_NAME_EN

    context.user_data["report_tmp"]["operation_name_en"] = text

    # عرض تقويم تاريخ العودة (بدلاً من الإدخال النصي)
    await _render_followup_calendar(update.message, context)

    return DISCHARGE_FOLLOWUP_DATE


async def handle_discharge_followup_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خروج (كلا الفرعين) - تاريخ ووقت العودة مدمج"""
    text = update.message.text.strip()

    try:
        dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
        context.user_data["report_tmp"]["followup_date"] = dt.date()
        context.user_data["report_tmp"]["followup_time"] = dt.strftime("%H:%M")
    except ValueError:
        await update.message.reply_text(
            "⚠️ **صيغة غير صحيحة!**\n\n"
            "يرجى استخدام الصيغة الصحيحة:\n"
            "YYYY-MM-DD HH:MM\n"
            "مثال: 2025-11-10 10:00",
            reply_markup=_nav_buttons(show_back=True)
        )
        return DISCHARGE_FOLLOWUP_DATE

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "✍️ **سبب العودة**\n\n"
        "يرجى إدخال سبب العودة:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return DISCHARGE_FOLLOWUP_REASON


async def handle_discharge_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خروج (كلا الفرعين) - سبب العودة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return DISCHARGE_FOLLOWUP_REASON

    context.user_data["report_tmp"]["followup_reason"] = text

    await update.message.reply_text("✅ تم الحفظ")
    gate_result = await show_translator_selection(update.message, context, "discharge")
    if gate_result == "MEDICAL_REPORT_ASK":
        return gate_result
    return DISCHARGE_TRANSLATOR
