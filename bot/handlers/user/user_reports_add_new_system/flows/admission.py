# -*- coding: utf-8 -*-
"""
Admission Flow Handlers
مسار الترقيد

يحتوي على:
- start_admission_flow: بدء مسار ترقيد
- handle_admission_reason: معالجة سبب الرقود
- handle_admission_room: معالجة رقم الغرفة
- handle_admission_notes: معالجة الملاحظات
- handle_admission_followup_date_text: معالجة تاريخ العودة
- handle_admission_followup_reason: معالجة سبب العودة
"""

import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

# Import states
from ..states import (
    ADMISSION_REASON, ADMISSION_ROOM, ADMISSION_NOTES,
    ADMISSION_FOLLOWUP_DATE, ADMISSION_FOLLOWUP_REASON, ADMISSION_TRANSLATOR
)

# Import utilities
from ..utils import _nav_buttons
from ...user_reports_add_helpers import validate_text_input

# Import shared functions
from .shared import show_translator_selection

# Import calendar rendering function
from .new_consult import _render_followup_calendar

logger = logging.getLogger(__name__)

# =============================
# Flow Start Function
# =============================

async def start_admission_flow(message, context):
    """بدء مسار ترقيد - الحقل 1: سبب الرقود"""
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "ترقيد"
    context.user_data["report_tmp"]["current_flow"] = "admission"
    context.user_data['_conversation_state'] = ADMISSION_REASON
    
    await message.reply_text(
        "🛏️ **سبب الرقود**\n\n"
        "يرجى إدخال سبب رقود المريض:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )
    
    return ADMISSION_REASON


# =============================
# Handlers
# =============================

async def handle_admission_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 1: سبب الرقود"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال سبب الرقود:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return ADMISSION_REASON

    context.user_data["report_tmp"]["admission_reason"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "🚪 **رقم الغرفة**\n\n"
        "يرجى إدخال رقم الغرفة:\n"
        "(أو اكتب 'لم يتم التحديد' إذا لم يتم تحديدها بعد)",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return ADMISSION_ROOM


async def handle_admission_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 2: رقم الغرفة"""
    text = update.message.text.strip()

    if text.lower() in ['لم يتم التحديد', 'لا يوجد', 'لا', 'no']:
        text = "لم يتم التحديد"

    context.user_data["report_tmp"]["room_number"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "📝 **ملاحظات**\n\n"
        "يرجى إدخال أي ملاحظات إضافية:\n"
        "(أو اكتب 'لا يوجد')",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return ADMISSION_NOTES


async def handle_admission_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 3: ملاحظات"""
    text = update.message.text.strip()

    if text.lower() in ['لا يوجد', 'لا', 'no', 'none']:
        text = "لا يوجد"

    context.user_data["report_tmp"]["notes"] = text

    # عرض تقويم تاريخ العودة (اختياري)
    await _render_followup_calendar(update.message, context)

    return ADMISSION_FOLLOWUP_DATE


async def handle_admission_followup_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 4: تاريخ ووقت العودة مدمج"""
    text = update.message.text.strip()

    # parse التاريخ والوقت معاً
    try:
        dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
        context.user_data["report_tmp"]["followup_date"] = dt.date()
        context.user_data["report_tmp"]["followup_time"] = dt.strftime("%H:%M")
    except ValueError:
        await update.message.reply_text(
            "⚠️ **صيغة غير صحيحة!**\n\n"
            "يرجى استخدام الصيغة الصحيحة:\n"
            "YYYY-MM-DD HH:MM\n"
            "مثال: 2025-10-30 10:00",
            reply_markup=_nav_buttons(show_back=True)
        )
        return ADMISSION_FOLLOWUP_DATE

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "✍️ **سبب العودة**\n\n"
        "يرجى إدخال سبب العودة:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return ADMISSION_FOLLOWUP_REASON


async def handle_admission_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 5: سبب العودة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return ADMISSION_FOLLOWUP_REASON

    context.user_data["report_tmp"]["followup_reason"] = text

    await update.message.reply_text("✅ تم الحفظ")
    await show_translator_selection(update.message, context, "admission")

    return ADMISSION_TRANSLATOR
