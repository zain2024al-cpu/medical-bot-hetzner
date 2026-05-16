# -*- coding: utf-8 -*-
"""
Followup Flow Handlers
مسار المتابعة / عودة دورية

يحتوي على:
- start_followup_flow: بدء مسار "متابعة في الرقود" (مع رقم الغرفة)
- start_periodic_followup_flow: بدء مسار "مراجعة / عودة دورية" (بدون رقم الغرفة)
- handle_followup_complaint: معالجة شكوى المريض
- handle_followup_diagnosis: معالجة التشخيص
- handle_followup_decision: معالجة قرار الطبيب (يفحص نوع المسار ويرسل إما لرقم الغرفة أو تاريخ العودة)
- handle_followup_room_floor: معالجة رقم الغرفة والطابق (فقط لمسار "متابعة في الرقود")
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
    """بدء مسار متابعة في الرقود - الحقل 1: شكوى المريض (مع رقم الغرفة)"""
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
        "🛏️ **متابعة في الرقود**\n\n"
        "أدخل حالة المريض اليومية:",
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
    context.user_data["report_tmp"]["current_flow"] = "periodic_followup"
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = FOLLOWUP_COMPLAINT
    
    await message.reply_text(
        "💬 **مراجعة / عودة دورية**\n\n"
        "أدخل شكوى المريض:",
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
    data = context.user_data.setdefault("report_tmp", {})
    
    # ✅ التأكد من حفظ medical_action و current_flow
    if not data.get("medical_action"):
        # ✅ افتراض أنه "متابعة في الرقود" إذا لم يتم تحديده مسبقاً
        data["medical_action"] = "متابعة في الرقود"
        logger.info(f"✅ [FOLLOWUP_COMPLAINT] تم استعادة medical_action='متابعة في الرقود' (الافتراضي)")
    
    # تحديث current_flow بناءً على medical_action إذا لم يكن مضبوطاً
    if data.get("medical_action") == "مراجعة / عودة دورية":
        data["current_flow"] = "periodic_followup"
    elif not data.get("current_flow"):
        data["current_flow"] = "followup"
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        if data.get("medical_action") == "متابعة في الرقود":
            error_label = "يرجى إدخال حالة المريض اليومية:"
        else:
            error_label = "يرجى إدخال شكوى المريض:"
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"{error_label}",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return FOLLOWUP_COMPLAINT

    data["complaint"] = text

    if data.get("medical_action") == "متابعة في الرقود":
        # ✅ تخطي التشخيص - الانتقال مباشرة لقرار الطبيب اليومي
        await update.message.reply_text(
            f"✅ تم الحفظ\n\n"
            f"📝 **متابعة في الرقود: قرار الطبيب اليومي**\n\n"
            f"أدخل قرار الطبيب اليومي:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        context.user_data['_conversation_state'] = FOLLOWUP_DECISION
        return FOLLOWUP_DECISION
    else:
        await update.message.reply_text(
            f"✅ تم الحفظ\n\n"
            f"🔬 **مراجعة / عودة دورية: التشخيص**\n\n"
            f"أدخل التشخيص:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
    return FOLLOWUP_DIAGNOSIS


async def handle_followup_diagnosis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 2: التشخيص"""
    # التأكد من وجود report_tmp
    data = context.user_data.setdefault("report_tmp", {})
    
    # ✅ التأكد من حفظ medical_action و current_flow
    if not data.get("medical_action"):
        # ✅ افتراض أنه "متابعة في الرقود" إذا لم يتم تحديده مسبقاً
        data["medical_action"] = "متابعة في الرقود"
        logger.info(f"✅ [FOLLOWUP_DIAGNOSIS] تم استعادة medical_action='متابعة في الرقود' (الافتراضي)")
    
    # تحديث current_flow بناءً على medical_action إذا لم يكن مضبوطاً
    if data.get("medical_action") == "مراجعة / عودة دورية":
        data["current_flow"] = "periodic_followup"
    elif not data.get("current_flow"):
        data["current_flow"] = "followup"
    
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

    data["diagnosis"] = text

    if data.get("medical_action") == "متابعة في الرقود":
        await update.message.reply_text(
            f"✅ تم الحفظ\n\n"
            f"📝 **متابعة في الرقود: قرار الطبيب اليومي**\n\n"
            f"أدخل قرار الطبيب اليومي:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"✅ تم الحفظ\n\n"
            f"📝 **مراجعة / عودة دورية: قرار الطبيب**\n\n"
            f"أدخل قرار الطبيب:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
    return FOLLOWUP_DECISION


async def handle_followup_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 3: قرار الطبيب"""
    # التأكد من وجود report_tmp
    data = context.user_data.setdefault("report_tmp", {})

    # تحديث current_flow بناءً على medical_action إذا لم يكن مضبوطاً
    if data.get("medical_action") == "مراجعة / عودة دورية":
        data["current_flow"] = "periodic_followup"
    elif not data.get("current_flow") or not data.get("medical_action"):
        data["medical_action"] = "متابعة في الرقود"
        data["current_flow"] = "followup"

    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        if data.get("medical_action") == "متابعة في الرقود":
            decision_label = "يرجى إدخال قرار الطبيب اليومي:"
        else:
            decision_label = "يرجى إدخال قرار الطبيب:"
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"{decision_label}",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return FOLLOWUP_DECISION

    data["decision"] = text

    logger.info(f"🔍 [FOLLOWUP_DECISION] medical_action={data.get('medical_action')}, report_tmp keys: {list(data.keys())}")

    # التحقق من نوع المسار لتحديد الخطوة التالية
    # ✅ المسارات التي تحتاج رقم غرفة: followup (متابعة في الرقود) و inpatient_followup
    if data.get("current_flow") in ["followup", "inpatient_followup"]:
        # مسار متابعة في الرقود: طلب رقم الغرفة والطابق
        logger.info(f"✅ [FOLLOWUP_DECISION] تم حفظ قرار الطبيب، مسار 'متابعة في الرقود' - طلب رقم الغرفة")
        logger.info(f"✅ [FOLLOWUP_DECISION] العودة إلى FOLLOWUP_ROOM_FLOOR state")
        await update.message.reply_text(
            f"✅ تم الحفظ\n\n"
            f"🏥 **متابعة في الرقود: رقم الغرفة والطابق**\n\n"
            f"أدخل رقم الغرفة والطابق (مثال: غرفة 205 - الطابق الثاني):",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        context.user_data['_conversation_state'] = FOLLOWUP_ROOM_FLOOR
        return FOLLOWUP_ROOM_FLOOR
    else:
        # مسار مراجعة / عودة دورية (periodic_followup): تخطي رقم الغرفة والذهاب للتقويم مباشرة
        logger.info(f"✅ [FOLLOWUP_DECISION] تم حفظ قرار الطبيب، مسار 'مراجعة / عودة دورية' - تخطي رقم الغرفة")
        await update.message.reply_text("✅ تم الحفظ")
        # عرض تقويم اختيار تاريخ ووقت العودة
        await _render_followup_calendar(update.message, context)
        context.user_data['_conversation_state'] = FOLLOWUP_DATE_TIME
        return FOLLOWUP_DATE_TIME


async def handle_followup_room_floor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 4: رقم الغرفة والطابق"""
    data = context.user_data.setdefault("report_tmp", {})
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=1)
    if not valid:
        from telegram import ReplyKeyboardMarkup
        skip_keyboard = ReplyKeyboardMarkup([["تخطي"]], resize_keyboard=True)
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال رقم الغرفة والطابق أو اضغط تخطي:",
            reply_markup=skip_keyboard,
            parse_mode="Markdown"
        )
        return FOLLOWUP_ROOM_FLOOR
    data["room_number"] = text
    await update.message.reply_text("✅ تم الحفظ")
    await _render_followup_calendar(update.message, context)
    context.user_data["report_tmp"]["current_flow"] = data.get("current_flow")
    return FOLLOWUP_DATE_TIME


async def handle_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 5: سبب العودة"""
    context.user_data['_conversation_state'] = FOLLOWUP_REASON
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

    # ✅ استخدام current_flow الصحيح (periodic_followup أو followup)
    current_flow = context.user_data.get("report_tmp", {}).get("current_flow", "followup")
    gate_result = await show_translator_selection(update.message, context, current_flow)
    if gate_result == "MEDICAL_REPORT_ASK":
        return gate_result
    return FOLLOWUP_TRANSLATOR
