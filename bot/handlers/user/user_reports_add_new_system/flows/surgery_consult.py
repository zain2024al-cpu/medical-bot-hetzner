# -*- coding: utf-8 -*-
"""
Surgery Consult Flow Handlers
مسار استشارة مع قرار عملية

يحتوي على:
- start_surgery_consult_flow: بدء مسار استشارة مع قرار عملية
- handle_surgery_consult_diagnosis: معالجة التشخيص
- handle_surgery_consult_decision: معالجة قرار الطبيب
- handle_surgery_consult_name_en: معالجة اسم العملية بالإنجليزي
- handle_surgery_consult_success_rate: معالجة نسبة نجاح العملية
- handle_surgery_consult_benefit_rate: معالجة نسبة الاستفادة
- handle_surgery_consult_tests: معالجة الفحوصات
- handle_surgery_consult_followup_date_text: معالجة تاريخ العودة
- handle_surgery_consult_followup_reason: معالجة سبب العودة
"""

import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

# Import states
from ..states import (
    SURGERY_CONSULT_DIAGNOSIS, SURGERY_CONSULT_DECISION, SURGERY_CONSULT_NAME_EN,
    SURGERY_CONSULT_SUCCESS_RATE, SURGERY_CONSULT_BENEFIT_RATE, SURGERY_CONSULT_TESTS,
    SURGERY_CONSULT_FOLLOWUP_DATE, SURGERY_CONSULT_FOLLOWUP_REASON, SURGERY_CONSULT_TRANSLATOR
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

async def start_surgery_consult_flow(message, context):
    """بدء مسار استشارة مع قرار عملية - الحقل 1: التشخيص"""
    medical_action = context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')
    current_flow = context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')
    logger.debug(f"start_surgery_consult_flow CALLED! medical_action={repr(medical_action)}, current_flow={repr(current_flow)}, state={SURGERY_CONSULT_DIAGNOSIS}")
    
    logger.info("=" * 80)
    logger.info("start_surgery_consult_flow CALLED!")
    logger.info(f"medical_action: {context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')}")
    logger.info(f"current_flow: {context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')}")
    logger.info("=" * 80)
    
    # التأكد من حفظ medical_action
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "استشارة مع قرار عملية"
    context.user_data["report_tmp"]["current_flow"] = "surgery_consult"
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = SURGERY_CONSULT_DIAGNOSIS
    
    await message.reply_text(
        "🔬 **التشخيص الطبي**\n\n"
        "يرجى إدخال التشخيص الطبي:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )
    
    return SURGERY_CONSULT_DIAGNOSIS


# =============================
# Handlers
# =============================

async def handle_surgery_consult_diagnosis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 1: التشخيص"""
    context.user_data.setdefault("report_tmp", {})
    context.user_data['_conversation_state'] = SURGERY_CONSULT_DIAGNOSIS
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال التشخيص:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return SURGERY_CONSULT_DIAGNOSIS

    context.user_data["report_tmp"]["diagnosis"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "📝 **قرار الطبيب وتفاصيل العملية**\n\n"
        "يرجى إدخال قرار الطبيب وتفاصيل العملية المقترحة:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return SURGERY_CONSULT_DECISION


async def handle_surgery_consult_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 2: قرار الطبيب وتفاصيل العملية"""
    context.user_data.setdefault("report_tmp", {})
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=1000)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال قرار الطبيب وتفاصيل العملية:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return SURGERY_CONSULT_DECISION

    context.user_data["report_tmp"]["decision"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "🔤 **اسم العملية بالإنجليزي**\n\n"
        "يرجى إدخال اسم العملية بالإنجليزي:\n"
        "مثال: Laparoscopic Cholecystectomy",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return SURGERY_CONSULT_NAME_EN


async def handle_surgery_consult_name_en(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 3: اسم العملية بالإنجليزي"""
    text = update.message.text.strip()
    valid, msg = validate_english_only(text, min_length=3, max_length=200)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال اسم العملية بالإنجليزي فقط:\n"
            f"مثال: Laparoscopic Cholecystectomy",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return SURGERY_CONSULT_NAME_EN

    context.user_data["report_tmp"]["operation_name_en"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "📊 **نسبة نجاح العملية**\n\n"
        "يرجى إدخال نسبة نجاح العملية المتوقعة:\n"
        "مثال: 95%",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return SURGERY_CONSULT_SUCCESS_RATE


async def handle_surgery_consult_success_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 4: نسبة نجاح العملية"""
    context.user_data['_conversation_state'] = SURGERY_CONSULT_SUCCESS_RATE
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=1, max_length=100)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال نسبة نجاح العملية:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return SURGERY_CONSULT_SUCCESS_RATE

    context.user_data.setdefault("report_tmp", {})["success_rate"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "💡 **نسبة الاستفادة من العملية**\n\n"
        "يرجى إدخال نسبة الاستفادة المتوقعة من العملية:\n"
        "مثال: تحسن كامل، تحسن جزئي، تحسن طفيف",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )
    
    context.user_data['_conversation_state'] = SURGERY_CONSULT_BENEFIT_RATE

    return SURGERY_CONSULT_BENEFIT_RATE


async def handle_surgery_consult_benefit_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 5: نسبة الاستفادة من العملية"""
    context.user_data['_conversation_state'] = SURGERY_CONSULT_BENEFIT_RATE
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال نسبة الاستفادة من العملية:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return SURGERY_CONSULT_BENEFIT_RATE

    context.user_data.setdefault("report_tmp", {})["benefit_rate"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "🔬 **الفحوصات والأشعة المطلوبة**\n\n"
        "يرجى إدخال الفحوصات والأشعة المطلوبة قبل العملية:\n"
        "(أو اكتب 'لا يوجد')",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )
    
    context.user_data['_conversation_state'] = SURGERY_CONSULT_TESTS

    return SURGERY_CONSULT_TESTS


async def handle_surgery_consult_tests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 6: الفحوصات والأشعة"""
    text = update.message.text.strip()

    if text.lower() in ['لا يوجد', 'لا', 'no', 'none']:
        text = "لا يوجد"

    context.user_data["report_tmp"]["tests"] = text
    context.user_data['_conversation_state'] = SURGERY_CONSULT_FOLLOWUP_DATE

    # عرض تقويم تاريخ العودة (اختياري)
    await _render_followup_calendar(update.message, context)

    return SURGERY_CONSULT_FOLLOWUP_DATE


async def handle_surgery_consult_followup_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 7: تاريخ ووقت العودة مدمج"""
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
            "مثال: 2025-10-30 10:00",
            reply_markup=_nav_buttons(show_back=True)
        )
        return SURGERY_CONSULT_FOLLOWUP_DATE

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "✍️ **سبب العودة**\n\n"
        "يرجى إدخال سبب العودة:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return SURGERY_CONSULT_FOLLOWUP_REASON


async def handle_surgery_consult_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 8: سبب العودة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return SURGERY_CONSULT_FOLLOWUP_REASON

    context.user_data["report_tmp"]["followup_reason"] = text

    await update.message.reply_text("✅ تم الحفظ")
    await show_translator_selection(update.message, context, "surgery_consult")

    return SURGERY_CONSULT_TRANSLATOR
