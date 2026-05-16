# -*- coding: utf-8 -*-
"""
Rehab Flow Handlers
مسار علاج طبيعي / أجهزة تعويضية

يحتوي على:
- start_rehab_flow: بدء مسار التأهيل
- handle_rehab_type: معالجة نوع التأهيل
- handle_physical_therapy_details: معالجة تفاصيل العلاج الطبيعي
- handle_physical_therapy_followup_date_choice: معالجة اختيار تاريخ العودة
- handle_physical_therapy_followup_date_text: معالجة تاريخ العودة (نص)
- handle_physical_therapy_followup_reason: معالجة سبب العودة
- handle_device_name_details: معالجة اسم الجهاز
- handle_device_followup_date_text: معالجة تاريخ العودة للأجهزة
- handle_device_followup_reason: معالجة سبب العودة للأجهزة
"""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

# Import states
from ..states import (
    REHAB_TYPE, PHYSICAL_THERAPY_DETAILS, PHYSICAL_THERAPY_FOLLOWUP_DATE,
    PHYSICAL_THERAPY_FOLLOWUP_REASON, PHYSICAL_THERAPY_TRANSLATOR,
    DEVICE_NAME_DETAILS, DEVICE_FOLLOWUP_DATE, DEVICE_FOLLOWUP_REASON, DEVICE_TRANSLATOR
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

async def start_rehab_flow(message, context):
    """بدء مسار علاج طبيعي/أجهزة - اختيار النوع"""
    medical_action = context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')
    current_flow = context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')
    logger.debug(f"start_rehab_flow CALLED! medical_action={repr(medical_action)}, current_flow={repr(current_flow)}")
    
    logger.info("=" * 80)
    logger.info("start_rehab_flow CALLED!")
    logger.info(f"medical_action: {context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')}")
    logger.info(f"current_flow: {context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')}")
    logger.info("=" * 80)
    
    # التأكد من حفظ medical_action
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "علاج طبيعي وإعادة تأهيل"
    context.user_data["report_tmp"]["current_flow"] = "rehab_physical"
    context.user_data['_conversation_state'] = REHAB_TYPE
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏃 علاج طبيعي", callback_data="rehab_type:physical_therapy")],
        [InlineKeyboardButton("🦾 أجهزة تعويضية", callback_data="rehab_type:device")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])

    await message.reply_text(
        "🏃 **علاج طبيعي / أجهزة تعويضية**\n\n"
        "اختر النوع:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    
    return REHAB_TYPE


# =============================
# Handlers
# =============================

async def handle_rehab_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة نوع العلاج التأهيلي"""
    query = update.callback_query
    await query.answer()

    rehab_type = query.data.split(":", 1)[1]
    context.user_data.setdefault("report_tmp", {})["rehab_type"] = rehab_type

    if rehab_type == "physical_therapy":
        await query.edit_message_text("✅ اخترت: علاج طبيعي")
        context.user_data["report_tmp"]["current_flow"] = "rehab_physical"
        context.user_data["report_tmp"]["medical_action"] = "علاج طبيعي"
        context.user_data['_conversation_state'] = PHYSICAL_THERAPY_DETAILS
        await query.message.reply_text(
            "🏃 **تفاصيل جلسة العلاج الطبيعي**\n\n"
            "يرجى إدخال تفاصيل الجلسة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return PHYSICAL_THERAPY_DETAILS

    elif rehab_type == "device":
        await query.edit_message_text("✅ اخترت: أجهزة تعويضية")
        context.user_data["report_tmp"]["current_flow"] = "rehab_device"
        context.user_data["report_tmp"]["medical_action"] = "أجهزة تعويضية"
        context.user_data['_conversation_state'] = DEVICE_NAME_DETAILS
        await query.message.reply_text(
            "🦾 **اسم الجهاز الذي تم توفيره مع التفاصيل**\n\n"
            "يرجى إدخال اسم الجهاز والتفاصيل:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return DEVICE_NAME_DETAILS


# فرع 1: علاج طبيعي
async def handle_physical_therapy_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """علاج طبيعي - الحقل 1: تفاصيل الجلسة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=5, max_length=500)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال تفاصيل جلسة العلاج الطبيعي:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return PHYSICAL_THERAPY_DETAILS

    context.user_data["report_tmp"]["therapy_details"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "📅 **تاريخ العودة**\n\n"
        "يرجى اختيار تاريخ العودة من التقويم:",
        parse_mode="Markdown"
    )
    
    await _render_followup_calendar(update.message, context)

    return PHYSICAL_THERAPY_FOLLOWUP_DATE


async def handle_physical_therapy_followup_date_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار وجود تاريخ عودة"""
    query = update.callback_query
    await query.answer()

    if query.data == "physical_date:no":
        context.user_data["report_tmp"]["followup_date"] = None
        context.user_data["report_tmp"]["followup_time"] = None
        context.user_data["report_tmp"]["followup_reason"] = "لا يوجد"

        await query.edit_message_text("✅ لا يوجد تاريخ عودة")
        gate_result = await show_translator_selection(query.message, context, "rehab_physical")
        if gate_result == "MEDICAL_REPORT_ASK":
            return gate_result
        return PHYSICAL_THERAPY_TRANSLATOR

    elif query.data == "physical_date:yes":
        await _render_followup_calendar(query.message, context)
        return PHYSICAL_THERAPY_FOLLOWUP_DATE


async def handle_physical_therapy_followup_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """علاج طبيعي - تاريخ ووقت العودة مدمج"""
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
        return PHYSICAL_THERAPY_FOLLOWUP_DATE

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "✍️ **سبب العودة**\n\n"
        "يرجى إدخال سبب العودة:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return PHYSICAL_THERAPY_FOLLOWUP_REASON


async def handle_physical_therapy_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """علاج طبيعي - الحقل 4: سبب العودة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return PHYSICAL_THERAPY_FOLLOWUP_REASON

    context.user_data["report_tmp"]["followup_reason"] = text

    await update.message.reply_text("✅ تم الحفظ")
    gate_result = await show_translator_selection(update.message, context, "rehab_physical")
    if gate_result == "MEDICAL_REPORT_ASK":
        return gate_result
    return PHYSICAL_THERAPY_TRANSLATOR


# فرع 2: أجهزة تعويضية
async def handle_device_name_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أجهزة تعويضية - الحقل 1: اسم الجهاز والتفاصيل"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=5, max_length=500)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال اسم الجهاز والتفاصيل:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return DEVICE_NAME_DETAILS

    context.user_data["report_tmp"]["device_details"] = text

    # عرض تقويم تاريخ العودة مباشرة
    await _render_followup_calendar(update.message, context)

    return DEVICE_FOLLOWUP_DATE


async def handle_device_followup_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أجهزة تعويضية - تاريخ ووقت العودة مدمج"""
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
            "مثال: 2025-11-15 11:00",
            reply_markup=_nav_buttons(show_back=True)
        )
        return DEVICE_FOLLOWUP_DATE

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "✍️ **سبب العودة**\n\n"
        "يرجى إدخال سبب العودة:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return DEVICE_FOLLOWUP_REASON


async def handle_device_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أجهزة تعويضية - الحقل 4: سبب العودة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return DEVICE_FOLLOWUP_REASON

    context.user_data["report_tmp"]["followup_reason"] = text

    await update.message.reply_text("✅ تم الحفظ")
    gate_result = await show_translator_selection(update.message, context, "rehab_device")
    if gate_result == "MEDICAL_REPORT_ASK":
        return gate_result
    return DEVICE_TRANSLATOR
