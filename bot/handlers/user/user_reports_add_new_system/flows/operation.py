# -*- coding: utf-8 -*-
"""
Operation Flow Handlers
مسار العملية

يحتوي على:
- start_operation_flow: بدء مسار عملية
- handle_operation_details_ar: معالجة تفاصيل العملية بالعربي
- handle_operation_name_en: معالجة اسم العملية بالإنجليزي
- handle_operation_notes: معالجة الملاحظات
- handle_operation_followup_date_text: معالجة تاريخ العودة
- handle_operation_followup_reason: معالجة سبب العودة
"""

import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

# Import states
from ..states import (
    OPERATION_DETAILS_AR, OPERATION_NAME_EN, OPERATION_NOTES,
    OPERATION_FOLLOWUP_DATE, OPERATION_FOLLOWUP_REASON, OPERATION_TRANSLATOR
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

async def start_operation_flow(message, context):
    """بدء مسار عملية - الحقل 1: تفاصيل العملية"""
    medical_action = context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')
    current_flow = context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')
    logger.debug(f"start_operation_flow CALLED! medical_action={repr(medical_action)}, current_flow={repr(current_flow)}")
    
    logger.info("=" * 80)
    logger.info("start_operation_flow CALLED!")
    logger.info(f"medical_action: {context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')}")
    logger.info(f"current_flow: {context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')}")
    logger.info("=" * 80)
    
    # التأكد من حفظ medical_action
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "عملية"
    context.user_data["report_tmp"]["current_flow"] = "operation"
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = OPERATION_DETAILS_AR
    
    await message.reply_text(
        "⚕️ **تفاصيل العملية التي تمت للحالة**\n\n"
        "يرجى إدخال تفاصيل العملية بالعربي:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )
    
    return OPERATION_DETAILS_AR


# =============================
# Handlers
# =============================

async def handle_operation_details_ar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 1: تفاصيل العملية بالعربي"""
    context.user_data['_conversation_state'] = OPERATION_DETAILS_AR
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=5, max_length=1000)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال تفاصيل العملية:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return OPERATION_DETAILS_AR

    context.user_data["report_tmp"]["operation_details"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "🔤 **اسم العملية بالإنجليزي**\n\n"
        "يرجى إدخال اسم العملية بالإنجليزي:\n"
        "مثال: Appendectomy",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return OPERATION_NAME_EN


async def handle_operation_name_en(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 2: اسم العملية بالإنجليزي"""
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
        return OPERATION_NAME_EN

    context.user_data["report_tmp"]["operation_name_en"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "📝 **ملاحظات**\n\n"
        "يرجى إدخال أي ملاحظات إضافية:\n"
        "(أو اكتب 'لا يوجد')",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return OPERATION_NOTES


async def handle_operation_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 3: ملاحظات"""
    text = update.message.text.strip()

    if text.lower() in ['لا يوجد', 'لا', 'no', 'none']:
        text = "لا يوجد"

    context.user_data["report_tmp"]["notes"] = text

    # عرض تقويم تاريخ العودة (اختياري)
    await _render_followup_calendar(update.message, context)

    return OPERATION_FOLLOWUP_DATE


async def handle_operation_followup_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 4: تاريخ ووقت العودة مدمج"""
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
            "مثال: 2025-11-01 09:00",
            reply_markup=_nav_buttons(show_back=True)
        )
        return OPERATION_FOLLOWUP_DATE

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "✍️ **سبب العودة**\n\n"
        "يرجى إدخال سبب العودة:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return OPERATION_FOLLOWUP_REASON


async def handle_operation_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        return OPERATION_FOLLOWUP_REASON

    context.user_data["report_tmp"]["followup_reason"] = text

    await update.message.reply_text("✅ تم الحفظ")
    gate_result = await show_translator_selection(update.message, context, "operation")
    if gate_result == "MEDICAL_REPORT_ASK":
        return gate_result
    return OPERATION_TRANSLATOR
