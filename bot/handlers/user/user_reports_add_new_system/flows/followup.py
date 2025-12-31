# -*- coding: utf-8 -*-
"""
Followup Flow Handlers
مسار المتابعة / عودة دورية

يحتوي على:
- start_followup_flow: بدء مسار متابعة في الرقود
- start_periodic_followup_flow: بدء مسار مراجعة / عودة دورية
- handle_followup_complaint: معالجة شكوى المريض
- handle_followup_diagnosis: معالجة التشخيص
- handle_followup_decision: معالجة قرار الطبيب
- handle_followup_room_floor: معالجة رقم الغرفة والطابق
- handle_followup_reason: معالجة سبب العودة
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

# Import states
from ..states import (
    FOLLOWUP_COMPLAINT, FOLLOWUP_DIAGNOSIS, FOLLOWUP_DECISION,
    FOLLOWUP_ROOM_FLOOR, FOLLOWUP_DATE_TIME, FOLLOWUP_REASON,
    FOLLOWUP_TRANSLATOR
)

# Import utilities
from ..utils import _nav_buttons
from ...user_reports_add_helpers import validate_text_input

# Import shared functions
from .shared import show_translator_selection

# Import calendar rendering function from new_consult
from .new_consult import _render_followup_calendar

logger = logging.getLogger(__name__)

# =============================
# Flow Start Functions
# =============================

async def start_followup_flow(message, context):
    """بدء مسار مراجعة/عودة دورية - الحقل 1: شكوى المريض"""
    medical_action = context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')
    current_flow = context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')
    logger.debug(f"start_followup_flow CALLED! medical_action={repr(medical_action)}, current_flow={repr(current_flow)}, state={FOLLOWUP_COMPLAINT}")
    
    logger.info("=" * 80)
    logger.info("start_followup_flow CALLED!")
    logger.info(f"medical_action: {context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')}")
    logger.info(f"current_flow: {context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')}")
    logger.info("=" * 80)
    
    # التأكد من حفظ medical_action
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "متابعة في الرقود"
    context.user_data["report_tmp"]["current_flow"] = "followup"
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = FOLLOWUP_COMPLAINT
    
    await message.reply_text(
        "💬 **شكوى المريض**\n\n"
        "يرجى إدخال شكوى المريض:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )
    
    return FOLLOWUP_COMPLAINT


async def start_periodic_followup_flow(message, context):
    """بدء مسار مراجعة / عودة دورية - الحقل 1: شكوى المريض"""
    medical_action = context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')
    current_flow = context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')
    logger.debug(f"start_periodic_followup_flow CALLED! medical_action={repr(medical_action)}, current_flow={repr(current_flow)}, state={FOLLOWUP_COMPLAINT}")
    
    logger.info("=" * 80)
    logger.info("start_periodic_followup_flow CALLED!")
    logger.info(f"medical_action: {context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')}")
    logger.info(f"current_flow: {context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')}")
    logger.info("=" * 80)
    
    # التأكد من حفظ medical_action
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "مراجعة / عودة دورية"
    context.user_data["report_tmp"]["current_flow"] = "followup"  # نفس التدفق
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = FOLLOWUP_COMPLAINT
    
    await message.reply_text(
        "💬 **شكوى المريض**\n\n"
        "يرجى إدخال شكوى المريض:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )
    
    return FOLLOWUP_COMPLAINT


# =============================
# Handlers
# =============================

async def handle_followup_complaint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 1: شكوى المريض"""
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = FOLLOWUP_COMPLAINT
    
    # التأكد من وجود report_tmp
    context.user_data.setdefault("report_tmp", {})
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال شكوى المريض:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return FOLLOWUP_COMPLAINT

    context.user_data["report_tmp"]["complaint"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "🔬 **التشخيص الطبي**\n\n"
        "يرجى إدخال التشخيص:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return FOLLOWUP_DIAGNOSIS


async def handle_followup_diagnosis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 2: التشخيص"""
    # التأكد من وجود report_tmp
    context.user_data.setdefault("report_tmp", {})
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال التشخيص:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return FOLLOWUP_DIAGNOSIS

    context.user_data["report_tmp"]["diagnosis"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "📝 **قرار الطبيب**\n\n"
        "يرجى إدخال قرار الطبيب:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return FOLLOWUP_DECISION


async def handle_followup_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 3: قرار الطبيب"""
    # التأكد من وجود report_tmp
    context.user_data.setdefault("report_tmp", {})
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال قرار الطبيب:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return FOLLOWUP_DECISION

    context.user_data["report_tmp"]["decision"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "🏥 **رقم الغرفة والطابق**\n\n"
        "يرجى إدخال رقم الغرفة والطابق:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return FOLLOWUP_ROOM_FLOOR


async def handle_followup_room_floor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 4: رقم الغرفة والطابق"""
    # التأكد من وجود report_tmp
    context.user_data.setdefault("report_tmp", {})

    text = update.message.text.strip()

    # التحقق من صحة الإدخال (يمكن أن يكون رقم غرفة أو طابق أو كليهما)
    if not text or len(text) < 1 or len(text) > 50:
        await update.message.reply_text(
            "⚠️ **خطأ في الإدخال**\n\n"
            "يرجى إدخال رقم الغرفة والطابق (مثال: غرفة 205 - الطابق 2):",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return FOLLOWUP_ROOM_FLOOR

    context.user_data["report_tmp"]["room_floor"] = text

    # عرض تقويم تاريخ العودة (اختياري)
    await _render_followup_calendar(update.message, context)

    return FOLLOWUP_DATE_TIME


async def handle_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        return FOLLOWUP_REASON

    context.user_data["report_tmp"]["followup_reason"] = text

    await update.message.reply_text("✅ تم الحفظ")
    await show_translator_selection(update.message, context, "followup")

    return FOLLOWUP_TRANSLATOR
