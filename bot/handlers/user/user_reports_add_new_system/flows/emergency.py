# -*- coding: utf-8 -*-
"""
Emergency Flow Handlers
مسار الطوارئ

يحتوي على:
- start_emergency_flow: بدء مسار طوارئ
- handle_emergency_complaint: معالجة شكوى المريض
- handle_emergency_diagnosis: معالجة التشخيص
- handle_emergency_decision: معالجة قرار الطبيب
- handle_emergency_status_choice: معالجة اختيار وضع الحالة
- handle_emergency_status_text: معالجة وضع الحالة (إدخال يدوي)
- handle_emergency_admission_type_choice: معالجة نوع الترقيد
- handle_emergency_room_number: معالجة رقم الغرفة
- handle_emergency_date_time_text: معالجة تاريخ ووقت العودة
- handle_emergency_reason: معالجة سبب العودة
"""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

# Import states
from ..states import (
    EMERGENCY_COMPLAINT, EMERGENCY_DIAGNOSIS, EMERGENCY_DECISION,
    EMERGENCY_STATUS, EMERGENCY_ADMISSION_NOTES, EMERGENCY_OPERATION_DETAILS,
    EMERGENCY_ADMISSION_TYPE, EMERGENCY_ROOM_NUMBER,
    EMERGENCY_DATE_TIME, EMERGENCY_REASON, EMERGENCY_TRANSLATOR
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
# Flow Start Function
# =============================

async def start_emergency_flow(message, context):
    """بدء مسار طوارئ - الحقل 1: شكوى المريض"""
    medical_action = context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')
    current_flow = context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')
    logger.debug(f"start_emergency_flow CALLED! medical_action={repr(medical_action)}, current_flow={repr(current_flow)}, state={EMERGENCY_COMPLAINT}")
    
    logger.info("=" * 80)
    logger.info("start_emergency_flow CALLED!")
    logger.info(f"medical_action: {context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')}")
    logger.info(f"current_flow: {context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')}")
    logger.info("=" * 80)
    
    # التأكد من حفظ medical_action
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "طوارئ"
    context.user_data["report_tmp"]["current_flow"] = "emergency"
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = EMERGENCY_COMPLAINT
    
    await message.reply_text(
        "💬 **شكوى المريض**\n\n"
        "يرجى إدخال شكوى المريض:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )
    
    return EMERGENCY_COMPLAINT


# =============================
# Handlers
# =============================

async def handle_emergency_complaint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 1: شكوى المريض"""
    # التأكد من وجود report_tmp
    context.user_data.setdefault("report_tmp", {})
    
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = EMERGENCY_COMPLAINT
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال شكوى المريض:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return EMERGENCY_COMPLAINT

    context.user_data["report_tmp"]["complaint"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "🔬 **التشخيص الطبي**\n\n"
        "يرجى إدخال التشخيص الطبي:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return EMERGENCY_DIAGNOSIS


async def handle_emergency_diagnosis(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        return EMERGENCY_DIAGNOSIS

    context.user_data["report_tmp"]["diagnosis"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "📝 **قرار الطبيب وماذا تم للحالة في الطوارئ**\n\n"
        "يرجى إدخال قرار الطبيب وتفاصيل ما تم للحالة:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return EMERGENCY_DECISION


async def handle_emergency_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 3: قرار الطبيب وماذا تم"""
    # التأكد من وجود report_tmp
    context.user_data.setdefault("report_tmp", {})
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال قرار الطبيب وتفاصيل ما تم للحالة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return EMERGENCY_DECISION

    context.user_data["report_tmp"]["decision"] = text

    # أزرار سريعة لوضع الحالة 
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 تم الخروج من الطوارئ", callback_data="emerg_status:discharged")],
        [InlineKeyboardButton("🛏️ تم الترقيد", callback_data="emerg_status:admitted")],
        [InlineKeyboardButton("⚕️ تم إجراء عملية", callback_data="emerg_status:operation")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "🏥 **وضع الحالة**\n\n"
        "ما هو وضع الحالة الآن؟",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

    return EMERGENCY_STATUS


async def handle_emergency_status_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار وضع الحالة"""
    query = update.callback_query
    await query.answer()

    data = query.data.split(":", 1)[1]

    # تحديد النص بناءً على الاختيار
    status_text = {
        "discharged": "تم الخروج من الطوارئ",
        "admitted": "تم الترقيد",
        "operation": "تم إجراء عملية"
    }.get(data, "غير محدد")

    context.user_data["report_tmp"]["status"] = status_text

    # إذا اختار "تم الترقيد"، نطلب الملاحظات أولاً
    if data == "admitted":
        await query.edit_message_text(
            "📝 **ملاحظات الرقود**\n\n"
            "يرجى توضيح ماذا تم وما هي خطة الرقود:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return EMERGENCY_ADMISSION_NOTES

    # إذا اختار "تم إجراء عملية"، نطلب تفاصيل العملية
    elif data == "operation":
        await query.edit_message_text(
            "⚕️ **تفاصيل العملية**\n\n"
            "يرجى إدخال ماهي العملية التي تمت للحالة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return EMERGENCY_OPERATION_DETAILS
    
    # للخروج من الطوارئ، نكمل مباشرة
    await query.edit_message_text(f"✅ تم اختيار: {status_text}")

    # عرض تقويم تاريخ العودة (اختياري)
    await _render_followup_calendar(query.message, context)

    return EMERGENCY_DATE_TIME



async def handle_emergency_admission_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة ملاحظات الرقود"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى توضيح ماذا تم وما هي خطة الرقود:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return EMERGENCY_ADMISSION_NOTES

    context.user_data["report_tmp"]["admission_notes"] = text

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏥 العناية المركزة", callback_data="emerg_admission:icu")],
        [InlineKeyboardButton("🛏️ الرقود", callback_data="emerg_admission:ward")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])

    await update.message.reply_text(
        "أين تم الترقيد؟",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

    return EMERGENCY_ADMISSION_TYPE


async def handle_emergency_operation_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة تفاصيل العملية"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال ماهي العملية التي تمت للحالة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return EMERGENCY_OPERATION_DETAILS

    context.user_data["report_tmp"]["operation_details"] = text

    await _render_followup_calendar(update.message, context)

    return EMERGENCY_DATE_TIME


async def handle_emergency_status_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 4: وضع الحالة (إدخال يدوي)"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال وضع الحالة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return EMERGENCY_STATUS

    context.user_data["report_tmp"]["status"] = text

    # إدخال مباشر للتاريخ والوقت (بدون أزرار)
    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "📅 **تاريخ ووقت العودة**\n\n"
        "يرجى إدخال التاريخ والوقت:\n"
        "الصيغة: YYYY-MM-DD HH:MM\n"
        "مثال: 2025-10-30 14:30",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return EMERGENCY_DATE_TIME


async def handle_emergency_admission_type_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار نوع الترقيد (العناية المركزة أو الرقود) - بعد الملاحظات"""
    query = update.callback_query
    await query.answer()

    data = query.data.split(":", 1)[1]

    admission_type_text = {
        "icu": "العناية المركزة",
        "ward": "الرقود"
    }.get(data, "غير محدد")

    context.user_data["report_tmp"]["admission_type"] = admission_type_text

    # إذا اختار "الرقود"، نطلب رقم الغرفة والطابق
    if data == "ward":
        await query.edit_message_text(
            f"✅ تم اختيار: {admission_type_text}\n\n"
            "🛏️ **رقم الغرفة والطابق**\n\n"
            "يرجى إدخال رقم الغرفة والطابق:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return EMERGENCY_ROOM_NUMBER

    # إذا اختار "العناية المركزة"، نكمل مباشرة للتاريخ
    await query.edit_message_text(f"✅ تم اختيار: {admission_type_text}")

    # عرض تقويم تاريخ العودة (اختياري)
    await _render_followup_calendar(query.message, context)

    return EMERGENCY_DATE_TIME


async def handle_emergency_room_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل: رقم الغرفة (عند اختيار الرقود)"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=1, max_length=50)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال رقم الغرفة والطابق:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return EMERGENCY_ROOM_NUMBER

    context.user_data["report_tmp"]["room_number"] = text

    await update.message.reply_text(f"✅ تم الحفظ: رقم الغرفة والطابق {text}")

    # عرض تقويم تاريخ العودة (اختياري)
    await _render_followup_calendar(update.message, context)

    return EMERGENCY_DATE_TIME


async def handle_emergency_date_time_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 5: تاريخ ووقت العودة"""
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
            "مثال: 2025-10-30 14:30",
            reply_markup=_nav_buttons(show_back=True)
        )
        return EMERGENCY_DATE_TIME

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "✍️ **سبب العودة**\n\n"
        "يرجى إدخال سبب العودة:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return EMERGENCY_REASON


async def handle_emergency_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 6: سبب العودة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return EMERGENCY_REASON

    context.user_data["report_tmp"]["followup_reason"] = text

    await update.message.reply_text("✅ تم الحفظ")
    gate_result = await show_translator_selection(update.message, context, "emergency")
    if gate_result == "MEDICAL_REPORT_ASK":
        return gate_result
    return EMERGENCY_TRANSLATOR
