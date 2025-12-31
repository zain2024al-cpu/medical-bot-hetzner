# -*- coding: utf-8 -*-
"""
Final Consult Flow Handlers
مسار استشارة أخيرة

يحتوي على:
- start_final_consult_flow: بدء مسار استشارة أخيرة
- handle_final_consult_diagnosis: معالجة التشخيص
- handle_final_consult_decision: معالجة قرار الطبيب
- handle_final_consult_recommendations: معالجة التوصيات
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

# Import states
from ..states import (
    FINAL_CONSULT_DIAGNOSIS, FINAL_CONSULT_DECISION,
    FINAL_CONSULT_RECOMMENDATIONS, FINAL_CONSULT_TRANSLATOR
)

# Import utilities
from ..utils import _nav_buttons
from ...user_reports_add_helpers import validate_text_input

# Import shared functions
from .shared import show_translator_selection

logger = logging.getLogger(__name__)

# =============================
# Flow Start Function
# =============================

async def start_final_consult_flow(message, context):
    """بدء مسار استشارة أخيرة - الحقل 1: التشخيص"""
    medical_action = context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')
    current_flow = context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')
    logger.debug(f"start_final_consult_flow CALLED! medical_action={repr(medical_action)}, current_flow={repr(current_flow)}")
    
    logger.info("=" * 80)
    logger.info("start_final_consult_flow CALLED!")
    logger.info(f"medical_action: {context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')}")
    logger.info(f"current_flow: {context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')}")
    logger.info("=" * 80)
    
    # التأكد من حفظ medical_action
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "استشارة أخيرة"
    context.user_data["report_tmp"]["current_flow"] = "final_consult"
    context.user_data['_conversation_state'] = FINAL_CONSULT_DIAGNOSIS
    
    await message.reply_text(
        "🔬 **التشخيص النهائي**\n\n"
        "يرجى إدخال التشخيص النهائي:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )
    
    return FINAL_CONSULT_DIAGNOSIS


# =============================
# Handlers
# =============================

async def handle_final_consult_diagnosis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 1: التشخيص"""
    context.user_data.setdefault("report_tmp", {})
    context.user_data['_conversation_state'] = FINAL_CONSULT_DIAGNOSIS
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال التشخيص:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return FINAL_CONSULT_DIAGNOSIS

    context.user_data["report_tmp"]["diagnosis"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "📝 **تفاصيل قرار الطبيب**\n\n"
        "يرجى إدخال تفاصيل قرار الطبيب:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return FINAL_CONSULT_DECISION


async def handle_final_consult_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 2: تفاصيل قرار الطبيب"""
    context.user_data.setdefault("report_tmp", {})
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=1000)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال تفاصيل قرار الطبيب:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return FINAL_CONSULT_DECISION

    context.user_data["report_tmp"]["decision"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "💡 **التوصيات الطبية**\n\n"
        "يرجى إدخال التوصيات الطبية النهائية:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return FINAL_CONSULT_RECOMMENDATIONS


async def handle_final_consult_recommendations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 3: التوصيات الطبية"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=1000)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال التوصيات الطبية:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return FINAL_CONSULT_RECOMMENDATIONS

    context.user_data["report_tmp"]["recommendations"] = text
    context.user_data["report_tmp"]["followup_date"] = None
    context.user_data["report_tmp"]["followup_reason"] = "استشارة أخيرة - لا يوجد عودة"

    await update.message.reply_text("✅ تم الحفظ")
    await show_translator_selection(update.message, context, "final_consult")

    return FINAL_CONSULT_TRANSLATOR
