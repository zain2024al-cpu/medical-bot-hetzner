# =============================
# flows/new_consult.py
# مسار استشارة جديدة - NEW CONSULTATION FLOW
# جميع handlers الخاصة بمسار استشارة جديدة
# =============================

import logging
import calendar
from datetime import datetime, time
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

# Imports from parent modules
from ..states import (
    NEW_CONSULT_COMPLAINT, NEW_CONSULT_DIAGNOSIS, NEW_CONSULT_DECISION,
    NEW_CONSULT_TESTS, NEW_CONSULT_FOLLOWUP_DATE, NEW_CONSULT_FOLLOWUP_TIME,
    NEW_CONSULT_FOLLOWUP_REASON, NEW_CONSULT_TRANSLATOR, NEW_CONSULT_CONFIRM,
    # States for other flows (used in conditional logic)
    FOLLOWUP_REASON, EMERGENCY_REASON, ADMISSION_FOLLOWUP_REASON,
    SURGERY_CONSULT_FOLLOWUP_REASON, OPERATION_FOLLOWUP_REASON,
    DISCHARGE_FOLLOWUP_REASON, PHYSICAL_THERAPY_FOLLOWUP_REASON,
    DEVICE_FOLLOWUP_REASON,
    FOLLOWUP_DATE_TIME, EMERGENCY_DATE_TIME, ADMISSION_FOLLOWUP_DATE,
    SURGERY_CONSULT_FOLLOWUP_DATE, OPERATION_FOLLOWUP_DATE,
    DISCHARGE_FOLLOWUP_DATE, PHYSICAL_THERAPY_FOLLOWUP_DATE,
    DEVICE_FOLLOWUP_DATE,
    APP_RESCHEDULE_RETURN_DATE, APP_RESCHEDULE_RETURN_REASON,
    # ✅ حالات مسار المناظير (تُستخدم في توجيه معالجات تاريخ/سبب العودة المشتركة)
    ENDOSCOPY_FOLLOWUP_DATE, ENDOSCOPY_FOLLOWUP_REASON,
    # ✅ حالات مسارات جلسات العلاج (كيماوي/موجّه/مناعي/غسيل كلى)
    TREATMENT_FOLLOWUP_DATE, TREATMENT_FOLLOWUP_REASON,
)
from ..utils import _nav_buttons, MONTH_NAMES_AR, WEEKDAYS_AR, _chunked
from ...user_reports_add_helpers import validate_text_input

# Imports from shared flows
from .shared import show_translator_selection

logger = logging.getLogger(__name__)

# =============================
# Helper Functions - دوال مساعدة للتقويم
# =============================

def _build_followup_calendar_markup(year: int, month: int):
    """بناء تقويم تاريخ العودة"""
    cal = calendar.Calendar(firstweekday=calendar.SATURDAY)
    weeks = cal.monthdayscalendar(year, month)
    today = datetime.now().date()

    keyboard = []

    # تقويم الشهر مع أزرار التنقل
    keyboard.append([
        InlineKeyboardButton("⬅️", callback_data=f"followup_cal_prev:{year}-{month:02d}"),
        InlineKeyboardButton(f"{MONTH_NAMES_AR.get(month, month)} {year}", callback_data="noop"),
        InlineKeyboardButton("➡️", callback_data=f"followup_cal_next:{year}-{month:02d}"),
    ])
    keyboard.append([InlineKeyboardButton(day, callback_data="noop") for day in WEEKDAYS_AR])

    for week in weeks:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="noop"))
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                    # عدم عرض التواريخ القديمة - فقط من اليوم فصاعداً
                    if date_obj < today:
                        row.append(InlineKeyboardButton(" ", callback_data="noop"))
                    else:
                        # تمييز اليوم بعلامة خاصة
                        if date_obj == today:
                            row.append(InlineKeyboardButton(f"📍{day:02d}", callback_data=f"followup_cal_day:{date_str}"))
                        else:
                            row.append(InlineKeyboardButton(f"{day:02d}", callback_data=f"followup_cal_day:{date_str}"))
                except Exception:
                    row.append(InlineKeyboardButton(" ", callback_data="noop"))
        keyboard.append(row)

    # أزرار التنقل
    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    text = f"📅 **تاريخ العودة**\n\n{MONTH_NAMES_AR.get(month, str(month))} {year}\n\nاختر التاريخ من التقويم:"
    return text, InlineKeyboardMarkup(keyboard)


async def _render_followup_calendar(message_or_query, context, year=None, month=None):
    """عرض تقويم تاريخ العودة"""
    data_tmp = context.user_data.setdefault("report_tmp", {})
    if year is None or month is None:
        now = datetime.now()
        year = data_tmp.get("followup_calendar_year", now.year)
        month = data_tmp.get("followup_calendar_month", now.month)

    text, markup = _build_followup_calendar_markup(year, month)
    data_tmp["followup_calendar_year"] = year
    data_tmp["followup_calendar_month"] = month

    if hasattr(message_or_query, 'edit_message_text'):
        # query object
        await message_or_query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        # message object
        await message_or_query.reply_text(text, reply_markup=markup, parse_mode="Markdown")


def _build_followup_hour_keyboard() -> InlineKeyboardMarkup:
    """لوحة اختيار الساعة لموعد العودة — 24 ساعة كاملة، 4 في كل صف"""
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
            InlineKeyboardButton(label, callback_data=f"followup_time_hour:{val}")
            for label, val in hours[i:i+4]
        ])
    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel"),
    ])
    return InlineKeyboardMarkup(keyboard)


def _build_followup_minute_keyboard(hour: str):
    """بناء لوحة اختيار الدقائق لتاريخ العودة"""
    minute_options = ["00", "15", "30", "45"]
    keyboard = []

    # تحويل الساعة إلى صيغة 12 ساعة للعرض
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
                f"{hour_display}:{min}", callback_data=f"followup_time_minute:{hour}:{min}"
            )
            for min in chunk
        ]
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    return InlineKeyboardMarkup(keyboard)


# =============================
# Flow Start Function
# =============================

async def start_new_consultation_flow(message, context):
    """بدء مسار استشارة جديدة - الحقل 1: شكوى المريض"""
    logger.info("=" * 80)
    logger.info("NEW_CONSULT_FLOW: Function called")
    logger.info(f"NEW_CONSULT_FLOW: medical_action = {context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')}")
    logger.info(f"NEW_CONSULT_FLOW: current_flow = {context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')}")
    logger.info("=" * 80)

    # التأكد من حفظ medical_action
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "استشارة جديدة"
    context.user_data["report_tmp"]["current_flow"] = "new_consult"
    logger.info("NEW_CONSULT_FLOW: Saved medical_action and current_flow")

    try:
        result = await message.reply_text(
            "شكوى المريض\n\n"
            "يرجى إدخال شكوى المريض:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        logger.info("NEW_CONSULT_FLOW: Message sent successfully, waiting for user input")
        # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
        context.user_data['_conversation_state'] = NEW_CONSULT_COMPLAINT
        logger.info(f"NEW_CONSULT_FLOW: Returning state = {NEW_CONSULT_COMPLAINT}")
        
        # إرجاع state للتأكد من أن ConversationHandler يعرف الحالة الجديدة
        return NEW_CONSULT_COMPLAINT
    except Exception as e:
        error_msg = f"ERROR: NEW_CONSULT_FLOW - Error sending message: {e}"
        logger.error(error_msg, exc_info=True)
        raise


# =============================
# Handlers - معالجات الحقول
# =============================

async def handle_new_consult_complaint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 1: شكوى المريض"""
    logger.info("NEW_CONSULT_COMPLAINT: Handler called")
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = NEW_CONSULT_COMPLAINT
    
    if not update.message:
        logger.error("NEW_CONSULT_COMPLAINT: No message in update!")
        return NEW_CONSULT_COMPLAINT
    
    text = update.message.text.strip()
    logger.info(f"NEW_CONSULT_COMPLAINT: Received text length = {len(text)}")
    
    try:
        valid, msg = validate_text_input(text, min_length=3)
        logger.info(f"NEW_CONSULT_COMPLAINT: Validation result = {valid}, message = {msg}")
    except Exception as e:
        logger.error(f"NEW_CONSULT_COMPLAINT: Error in validation: {e}", exc_info=True)
        return NEW_CONSULT_COMPLAINT

    if not valid:
        logger.warning(f"NEW_CONSULT_COMPLAINT: Validation failed, returning to same state")
        try:
            await update.message.reply_text(
                f"خطأ: {msg}\n\n"
                f"يرجى إدخال شكوى المريض:",
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"NEW_CONSULT_COMPLAINT: Failed to send error message: {e}", exc_info=True)
        return NEW_CONSULT_COMPLAINT

    logger.info(f"NEW_CONSULT_COMPLAINT: Validation passed, saving complaint")
    context.user_data["report_tmp"]["complaint"] = text

    try:
        logger.info("NEW_CONSULT_COMPLAINT: Sending diagnosis request message...")
        await update.message.reply_text(
            "✅ تم الحفظ\n\n"
            "🔬 **التشخيص**\n\n"
            "يرجى إدخال التشخيص:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        logger.info("NEW_CONSULT_COMPLAINT: Message sent, returning NEW_CONSULT_DIAGNOSIS")
    except Exception as e:
        logger.error(f"NEW_CONSULT_COMPLAINT: Error sending diagnosis request: {e}", exc_info=True)
        raise

    return NEW_CONSULT_DIAGNOSIS


async def handle_new_consult_diagnosis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 2: التشخيص"""
    # التأكد من وجود report_tmp
    context.user_data.setdefault("report_tmp", {})
    
    logger.info("NEW_CONSULT_DIAGNOSIS: Handler called")
    
    if not update.message:
        logger.error("NEW_CONSULT_DIAGNOSIS: No message in update!")
        return NEW_CONSULT_DIAGNOSIS
    
    text = update.message.text.strip()
    logger.info(f"NEW_CONSULT_DIAGNOSIS: Received text length = {len(text)}")
    
    try:
        valid, msg = validate_text_input(text, min_length=3)
        logger.info(f"NEW_CONSULT_DIAGNOSIS: Validation result = {valid}, message = {msg}")
    except Exception as e:
        logger.error(f"NEW_CONSULT_DIAGNOSIS: Error in validation: {e}", exc_info=True)
        return NEW_CONSULT_DIAGNOSIS

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال التشخيص:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return NEW_CONSULT_DIAGNOSIS

    context.user_data["report_tmp"]["diagnosis"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "📝 **قرار الطبيب**\n\n"
        "يرجى إدخال قرار الطبيب:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return NEW_CONSULT_DECISION


async def handle_new_consult_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        return NEW_CONSULT_DECISION

    context.user_data["report_tmp"]["decision"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "🔬 **الفحوصات المطلوبة**\n\n"
        "يرجى إدخال الفحوصات المطلوبة قبل العملية:\n"
        "(أو اكتب 'لا يوجد' إذا لم تكن هناك فحوصات)",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return NEW_CONSULT_TESTS


async def handle_new_consult_tests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 4: الفحوصات المطلوبة"""
    text = update.message.text.strip()

    if text.lower() in ['لا يوجد', 'لا', 'no', 'none']:
        text = "لا يوجد"
    else:
        valid, msg = validate_text_input(text, min_length=3)
        if not valid:
            await update.message.reply_text(
                f"⚠️ **خطأ: {msg}**\n\n"
                f"يرجى إدخال الفحوصات المطلوبة:",
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )
            return NEW_CONSULT_TESTS

    context.user_data["report_tmp"]["tests"] = text

    # عرض تقويم تاريخ العودة (اختياري)
    await _render_followup_calendar(update.message, context)

    return NEW_CONSULT_FOLLOWUP_DATE


async def handle_new_consult_followup_date_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تخطي تاريخ العودة"""
    query = update.callback_query
    await query.answer()

    # عدم حفظ تاريخ العودة
    context.user_data["report_tmp"]["followup_date"] = None
    context.user_data["report_tmp"]["followup_time"] = None

    # تحديد الحالة التالية بناءً على نوع الإجراء
    current_flow = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
    if current_flow in ["followup", "periodic_followup", "inpatient_followup"]:
        next_state = FOLLOWUP_REASON
    elif current_flow == "emergency":
        next_state = EMERGENCY_REASON
    elif current_flow == "admission":
        next_state = ADMISSION_FOLLOWUP_REASON
    elif current_flow == "surgery_consult":
        next_state = SURGERY_CONSULT_FOLLOWUP_REASON
    elif current_flow == "operation":
        next_state = OPERATION_FOLLOWUP_REASON
    elif current_flow == "discharge":
        next_state = DISCHARGE_FOLLOWUP_REASON
    elif current_flow == "rehab_physical":
        next_state = PHYSICAL_THERAPY_FOLLOWUP_REASON
    elif current_flow == "device":
        next_state = DEVICE_FOLLOWUP_REASON
    else:
        next_state = NEW_CONSULT_FOLLOWUP_REASON

    await query.edit_message_text(
        "✅ تم التخطي\n\n"
        "✍️ **سبب العودة**\n\n"
        "يرجى إدخال سبب العودة:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return next_state


async def handle_new_consult_followup_calendar_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج التنقل في تقويم تاريخ العودة"""
    query = update.callback_query
    await query.answer()

    # query.data format: "followup_cal_prev:2025-11" or "followup_cal_next:2025-11"
    parts = query.data.split(":", 1)
    if len(parts) != 2:
        await query.answer("⚠️ خطأ في البيانات", show_alert=True)
        return NEW_CONSULT_FOLLOWUP_DATE

    action_part = parts[0]  # "followup_cal_prev" or "followup_cal_next"
    date_str = parts[1]  # "2025-11"

    # استخراج action
    if "prev" in action_part:
        action = "prev"
    elif "next" in action_part:
        action = "next"
    else:
        await query.answer("⚠️ خطأ في البيانات", show_alert=True)
        return NEW_CONSULT_FOLLOWUP_DATE

    year, month = map(int, date_str.split("-"))

    if action == "prev":
        month -= 1
        if month < 1:
            month = 12
            year -= 1
    elif action == "next":
        month += 1
        if month > 12:
            month = 1
            year += 1

    # ✅ التحقق من حالة التعديل
    edit_field_key = context.user_data.get("edit_field_key")
    edit_flow_type = context.user_data.get("edit_flow_type")
    
    if edit_field_key and edit_flow_type:
        # ✅ حالة التعديل: استخدام confirm state
        from .shared import get_confirm_state
        current_state = get_confirm_state(edit_flow_type)
    else:
        # ✅ حالة الإدخال العادي: تحديد الحالة بناءً على نوع الإجراء
        current_flow = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
        if current_flow in ["followup", "periodic_followup", "inpatient_followup"]:
            current_state = FOLLOWUP_DATE_TIME
        elif current_flow == "emergency":
            current_state = EMERGENCY_DATE_TIME
        elif current_flow == "admission":
            current_state = ADMISSION_FOLLOWUP_DATE
        elif current_flow == "surgery_consult":
            current_state = SURGERY_CONSULT_FOLLOWUP_DATE
        elif current_flow == "operation":
            current_state = OPERATION_FOLLOWUP_DATE
        elif current_flow == "discharge":
            current_state = DISCHARGE_FOLLOWUP_DATE
        elif current_flow == "rehab_physical":
            current_state = PHYSICAL_THERAPY_FOLLOWUP_DATE
        elif current_flow == "device":
            current_state = DEVICE_FOLLOWUP_DATE
        elif current_flow == "appointment_reschedule":
            current_state = APP_RESCHEDULE_RETURN_DATE
        elif current_flow == "endoscopy":
            current_state = ENDOSCOPY_FOLLOWUP_DATE
        elif current_flow in ("treatment_chemo", "treatment_targeted", "treatment_immuno", "treatment_dialysis"):
            current_state = TREATMENT_FOLLOWUP_DATE
        else:
            current_state = NEW_CONSULT_FOLLOWUP_DATE

    await _render_followup_calendar(query, context, year, month)
    return current_state


async def handle_new_consult_followup_calendar_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار تاريخ العودة من التقويم"""
    query = update.callback_query
    await query.answer()

    date_str = query.data.split(":", 1)[1]
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        date_value = dt.date()
        
        # ✅ التحقق من حالة التعديل
        edit_field_key = context.user_data.get("edit_field_key")
        edit_flow_type = context.user_data.get("edit_flow_type")
        
        if edit_field_key:
            # ✅ حالة التعديل: حفظ التاريخ مباشرة في الحقل المحدد
            data = context.user_data.setdefault("report_tmp", {})
            data[edit_field_key] = date_str
            # مسح معلومات التعديل
            context.user_data.pop("edit_field_key", None)
            context.user_data.pop("edit_flow_type", None)
            
            # ✅ إعادة عرض الملخص
            from .shared import show_final_summary, get_confirm_state
            try:
                await show_final_summary(query.message, context, edit_flow_type)
                confirm_state = get_confirm_state(edit_flow_type)
                context.user_data['_conversation_state'] = confirm_state
                logger.info(f"✅ [CALENDAR_EDIT] تم حفظ التاريخ {date_str} في {edit_field_key} للـ flow_type={edit_flow_type}")
                return confirm_state
            except Exception as e:
                logger.error(f"❌ [CALENDAR_EDIT] خطأ في عرض الملخص بعد حفظ التاريخ: {e}", exc_info=True)
                await query.edit_message_text(
                    f"✅ **تم حفظ التاريخ:** {date_str}\n\n"
                    f"يرجى استخدام زر '🔙 رجوع' للرجوع إلى الملخص.",
                    parse_mode="Markdown"
                )
                confirm_state = get_confirm_state(edit_flow_type) if edit_flow_type else None
                if confirm_state:
                    context.user_data['_conversation_state'] = confirm_state
                    return confirm_state
                return ConversationHandler.END
        
        # ✅ حالة الإدخال العادي: حفظ في _pending_followup_date
        context.user_data["report_tmp"]["_pending_followup_date"] = date_value

        # بناء لوحة مفاتيح الساعات — 24 ساعة كاملة
        keyboard = _build_followup_hour_keyboard()

        # تحديد الحالة التالية بناءً على نوع الإجراء
        current_flow = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
        if current_flow in ["followup", "periodic_followup", "inpatient_followup"]:
            next_state = FOLLOWUP_DATE_TIME
        elif current_flow == "emergency":
            next_state = EMERGENCY_DATE_TIME
        elif current_flow == "admission":
            next_state = ADMISSION_FOLLOWUP_DATE
        elif current_flow == "surgery_consult":
            next_state = SURGERY_CONSULT_FOLLOWUP_DATE
        elif current_flow == "operation":
            next_state = OPERATION_FOLLOWUP_DATE
        elif current_flow == "discharge":
            next_state = DISCHARGE_FOLLOWUP_DATE
        elif current_flow == "rehab_physical":
            next_state = PHYSICAL_THERAPY_FOLLOWUP_DATE
        elif current_flow == "device":
            next_state = DEVICE_FOLLOWUP_DATE
        elif current_flow == "appointment_reschedule":
            next_state = APP_RESCHEDULE_RETURN_DATE
        elif current_flow == "endoscopy":
            next_state = ENDOSCOPY_FOLLOWUP_DATE
        elif current_flow in ("treatment_chemo", "treatment_targeted", "treatment_immuno", "treatment_dialysis"):
            next_state = TREATMENT_FOLLOWUP_DATE
        else:
            next_state = NEW_CONSULT_FOLLOWUP_TIME

        await query.edit_message_text(
            f"✅ **تم اختيار التاريخ**\n\n"
            f"📅 **التاريخ:**\n"
            f"{date_str}\n\n"
            f"🕐 **الوقت** (اختياري)\n\n"
            f"اختر الساعة:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return next_state
    except ValueError:
        # تحديد الحالة الحالية بناءً على نوع الإجراء
        current_flow = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
        if current_flow in ["followup", "periodic_followup", "inpatient_followup"]:
            current_state = FOLLOWUP_DATE_TIME
        elif current_flow == "emergency":
            current_state = EMERGENCY_DATE_TIME
        elif current_flow == "admission":
            current_state = ADMISSION_FOLLOWUP_DATE
        elif current_flow == "surgery_consult":
            current_state = SURGERY_CONSULT_FOLLOWUP_DATE
        elif current_flow == "operation":
            current_state = OPERATION_FOLLOWUP_DATE
        elif current_flow == "discharge":
            current_state = DISCHARGE_FOLLOWUP_DATE
        elif current_flow == "rehab_physical":
            current_state = PHYSICAL_THERAPY_FOLLOWUP_DATE
        elif current_flow == "device":
            current_state = DEVICE_FOLLOWUP_DATE
        elif current_flow == "appointment_reschedule":
            current_state = APP_RESCHEDULE_RETURN_DATE
        elif current_flow == "endoscopy":
            current_state = ENDOSCOPY_FOLLOWUP_DATE
        elif current_flow in ("treatment_chemo", "treatment_targeted", "treatment_immuno", "treatment_dialysis"):
            current_state = TREATMENT_FOLLOWUP_DATE
        else:
            current_state = NEW_CONSULT_FOLLOWUP_DATE

        await query.answer("⚠️ خطأ في التاريخ", show_alert=True)
        return current_state


async def handle_new_consult_followup_time_hour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار الساعة لتاريخ العودة — يحفظ مباشرة بدقائق 00"""
    query = update.callback_query
    await query.answer()
    hour = query.data.split(":", 1)[1]

    # حفظ الوقت مباشرة بدون اختيار الدقائق (الدقائق = 00)
    minute = "00"
    time_value = f"{hour}:{minute}"
    
    data_tmp = context.user_data.setdefault("report_tmp", {})
    pending_date = data_tmp.get("_pending_followup_date")
    if pending_date:
        # إنشاء datetime object
        dt = datetime.combine(pending_date, time(int(hour), int(minute)))
        
        data_tmp["followup_date"] = pending_date
        data_tmp["followup_time"] = time_value
        data_tmp.pop("_pending_followup_date", None)
        data_tmp.pop("_pending_followup_hour", None)
        
        # عرض الوقت بصيغة 12 ساعة
        hour_int = int(hour)
        if hour_int == 0:
            time_display = f"12:{minute} صباحاً"
        elif hour_int < 12:
            time_display = f"{hour_int}:{minute} صباحاً"
        elif hour_int == 12:
            time_display = f"12:{minute} ظهراً"
        else:
            time_display = f"{hour_int - 12}:{minute} مساءً"

        days_ar = {
            0: 'الاثنين',
            1: 'الثلاثاء',
            2: 'الأربعاء',
            3: 'الخميس',
            4: 'الجمعة',
            5: 'السبت',
            6: 'الأحد'
        }
        day_name = days_ar.get(dt.weekday(), '')
        date_str = f"{dt.strftime('%d')} {MONTH_NAMES_AR.get(dt.month, dt.month)} {dt.year} ({day_name}) - {time_display}"

        await query.edit_message_text(
            f"✅ **تم اختيار التاريخ والوقت**\n\n"
            f"📅 **التاريخ:**\n"
            f"{dt.strftime('%d')} {MONTH_NAMES_AR.get(dt.month, dt.month)} {dt.year} ({day_name})\n\n"
            f"🕐 **الوقت:**\n"
            f"{time_display}",
            parse_mode="Markdown"
        )

        # تحديد الحالة التالية بناءً على نوع الإجراء
        current_flow = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
        if current_flow in ["followup", "periodic_followup", "inpatient_followup"]:
            next_state = FOLLOWUP_REASON
        elif current_flow == "emergency":
            next_state = EMERGENCY_REASON
        elif current_flow == "admission":
            next_state = ADMISSION_FOLLOWUP_REASON
        elif current_flow == "surgery_consult":
            next_state = SURGERY_CONSULT_FOLLOWUP_REASON
        elif current_flow == "operation":
            next_state = OPERATION_FOLLOWUP_REASON
        elif current_flow == "discharge":
            next_state = DISCHARGE_FOLLOWUP_REASON
        elif current_flow == "rehab_physical":
            next_state = PHYSICAL_THERAPY_FOLLOWUP_REASON
        elif current_flow == "device":
            next_state = DEVICE_FOLLOWUP_REASON
        elif current_flow == "appointment_reschedule":
            next_state = APP_RESCHEDULE_RETURN_REASON
        elif current_flow == "endoscopy":
            next_state = ENDOSCOPY_FOLLOWUP_REASON
        elif current_flow in ("treatment_chemo", "treatment_targeted", "treatment_immuno", "treatment_dialysis"):
            next_state = TREATMENT_FOLLOWUP_REASON
        else:
            next_state = NEW_CONSULT_FOLLOWUP_REASON

        # الانتقال إلى خطوة سبب العودة
        await query.message.reply_text(
            "✅ تم الحفظ\n\n"
            "✍️ **سبب العودة**\n\n"
            "يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )

        # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
        context.user_data['_conversation_state'] = next_state

        return next_state
    else:
        # إذا لم يكن هناك تاريخ معلق، نعود إلى اختيار التاريخ
        await query.edit_message_text(
            "⚠️ **خطأ**\n\n"
            "لم يتم اختيار التاريخ. يرجى اختيار التاريخ أولاً.",
            parse_mode="Markdown"
        )
        # تحديد الحالة التالية بناءً على نوع الإجراء
        current_flow = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
        if current_flow in ["followup", "periodic_followup", "inpatient_followup"]:
            return FOLLOWUP_DATE_TIME
        elif current_flow == "emergency":
            return EMERGENCY_DATE_TIME
        elif current_flow == "admission":
            return ADMISSION_FOLLOWUP_DATE
        elif current_flow == "surgery_consult":
            return SURGERY_CONSULT_FOLLOWUP_DATE
        elif current_flow == "operation":
            return OPERATION_FOLLOWUP_DATE
        elif current_flow == "discharge":
            return DISCHARGE_FOLLOWUP_DATE
        elif current_flow == "rehab_physical":
            return PHYSICAL_THERAPY_FOLLOWUP_DATE
        elif current_flow == "device":
            return DEVICE_FOLLOWUP_DATE
        elif current_flow == "appointment_reschedule":
            return APP_RESCHEDULE_RETURN_DATE
        elif current_flow == "endoscopy":
            return ENDOSCOPY_FOLLOWUP_DATE
        elif current_flow in ("treatment_chemo", "treatment_targeted", "treatment_immuno", "treatment_dialysis"):
            return TREATMENT_FOLLOWUP_DATE
        else:
            return NEW_CONSULT_FOLLOWUP_DATE


async def handle_new_consult_followup_time_minute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار الدقائق لتاريخ العودة"""
    query = update.callback_query
    await query.answer()
    _, hour, minute = query.data.split(":")
    time_value = f"{hour}:{minute}"
    
    data_tmp = context.user_data.setdefault("report_tmp", {})
    pending_date = data_tmp.get("_pending_followup_date")
    if pending_date:
        # إنشاء datetime object أولاً
        dt = datetime.combine(pending_date, time(int(hour), int(minute)))
        
        data_tmp["followup_date"] = pending_date
        data_tmp["followup_time"] = time_value
        data_tmp.pop("_pending_followup_date", None)
        data_tmp.pop("_pending_followup_hour", None)
        
        # عرض الوقت بصيغة 12 ساعة
        hour_int = int(hour)
        if hour_int == 0:
            time_display = f"12:{minute} صباحاً"
        elif hour_int < 12:
            time_display = f"{hour_int}:{minute} صباحاً"
        elif hour_int == 12:
            time_display = f"12:{minute} ظهراً"
        else:
            time_display = f"{hour_int - 12}:{minute} مساءً"

        days_ar = {
            0: 'الاثنين',
            1: 'الثلاثاء',
            2: 'الأربعاء',
            3: 'الخميس',
            4: 'الجمعة',
            5: 'السبت',
            6: 'الأحد'
        }
        day_name = days_ar.get(dt.weekday(), '')

        await query.edit_message_text(
            f"✅ **تم اختيار التاريخ والوقت**\n\n"
            f"📅 **التاريخ:**\n"
            f"{dt.strftime('%d')} {MONTH_NAMES_AR.get(dt.month, dt.month)} {dt.year} ({day_name})\n\n"
            f"🕐 **الوقت:**\n"
            f"{time_display}",
            parse_mode="Markdown"
        )

        # تحديد الحالة التالية بناءً على نوع الإجراء
        current_flow = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
        if current_flow in ["followup", "periodic_followup", "inpatient_followup"]:
            next_state = FOLLOWUP_REASON
        elif current_flow == "emergency":
            next_state = EMERGENCY_REASON
        elif current_flow == "admission":
            next_state = ADMISSION_FOLLOWUP_REASON
        elif current_flow == "surgery_consult":
            next_state = SURGERY_CONSULT_FOLLOWUP_REASON
        elif current_flow == "operation":
            next_state = OPERATION_FOLLOWUP_REASON
        elif current_flow == "discharge":
            next_state = DISCHARGE_FOLLOWUP_REASON
        elif current_flow == "rehab_physical":
            next_state = PHYSICAL_THERAPY_FOLLOWUP_REASON
        elif current_flow == "device":
            next_state = DEVICE_FOLLOWUP_REASON
        elif current_flow == "appointment_reschedule":
            next_state = APP_RESCHEDULE_RETURN_REASON
        elif current_flow == "endoscopy":
            next_state = ENDOSCOPY_FOLLOWUP_REASON
        elif current_flow in ("treatment_chemo", "treatment_targeted", "treatment_immuno", "treatment_dialysis"):
            next_state = TREATMENT_FOLLOWUP_REASON
        else:
            next_state = NEW_CONSULT_FOLLOWUP_REASON

        # الانتقال إلى خطوة سبب العودة
        await query.message.reply_text(
            "✍️ **سبب العودة**\n\n"
            "يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        context.user_data['_conversation_state'] = next_state
        return next_state

    # تحديد الحالة الحالية بناءً على نوع الإجراء
    current_flow = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
    if current_flow in ["followup", "periodic_followup", "inpatient_followup"]:
        current_state = FOLLOWUP_DATE_TIME
    elif current_flow == "emergency":
        current_state = EMERGENCY_DATE_TIME
    elif current_flow == "admission":
        current_state = ADMISSION_FOLLOWUP_DATE
    elif current_flow == "surgery_consult":
        current_state = SURGERY_CONSULT_FOLLOWUP_DATE
    elif current_flow == "operation":
        current_state = OPERATION_FOLLOWUP_DATE
    elif current_flow == "discharge":
        current_state = DISCHARGE_FOLLOWUP_DATE
    elif current_flow == "rehab_physical":
        current_state = PHYSICAL_THERAPY_FOLLOWUP_DATE
    elif current_flow == "device":
        current_state = DEVICE_FOLLOWUP_DATE
    elif current_flow == "endoscopy":
        current_state = ENDOSCOPY_FOLLOWUP_DATE
    elif current_flow in ("treatment_chemo", "treatment_targeted", "treatment_immuno", "treatment_dialysis"):
        current_state = TREATMENT_FOLLOWUP_DATE
    else:
        current_state = NEW_CONSULT_FOLLOWUP_TIME

    await query.answer("خطأ: لم يتم تحديد التاريخ", show_alert=True)
    return current_state


async def handle_new_consult_followup_time_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تخطي اختيار الوقت لتاريخ العودة"""
    query = update.callback_query
    await query.answer()
    
    data_tmp = context.user_data.setdefault("report_tmp", {})
    pending_date = data_tmp.get("_pending_followup_date")
    if pending_date:
        data_tmp["followup_date"] = pending_date
        data_tmp["followup_time"] = None
        data_tmp.pop("_pending_followup_date", None)
        data_tmp.pop("_pending_followup_hour", None)
        
        days_ar = {
            0: 'الاثنين',
            1: 'الثلاثاء',
            2: 'الأربعاء',
            3: 'الخميس',
            4: 'الجمعة',
            5: 'السبت',
            6: 'الأحد'
        }
        day_name = days_ar.get(pending_date.weekday(), '')

        await query.edit_message_text(
            f"✅ تم اختيار التاريخ\n\n"
            f"📅 **التاريخ:**\n"
            f"{pending_date.strftime('%d')} {MONTH_NAMES_AR.get(pending_date.month, pending_date.month)} {pending_date.year} ({day_name})"
        )

        # تحديد الحالة التالية بناءً على نوع الإجراء
        current_flow = data_tmp.get("current_flow", "new_consult")
        if current_flow in ["followup", "periodic_followup", "inpatient_followup"]:
            next_state = FOLLOWUP_REASON
        elif current_flow == "emergency":
            next_state = EMERGENCY_REASON
        elif current_flow == "admission":
            next_state = ADMISSION_FOLLOWUP_REASON
        elif current_flow == "surgery_consult":
            next_state = SURGERY_CONSULT_FOLLOWUP_REASON
        elif current_flow == "operation":
            next_state = OPERATION_FOLLOWUP_REASON
        elif current_flow == "discharge":
            next_state = DISCHARGE_FOLLOWUP_REASON
        elif current_flow == "rehab_physical":
            next_state = PHYSICAL_THERAPY_FOLLOWUP_REASON
        elif current_flow == "device":
            next_state = DEVICE_FOLLOWUP_REASON
        elif current_flow == "appointment_reschedule":
            next_state = APP_RESCHEDULE_RETURN_REASON
        elif current_flow == "endoscopy":
            next_state = ENDOSCOPY_FOLLOWUP_REASON
        elif current_flow in ("treatment_chemo", "treatment_targeted", "treatment_immuno", "treatment_dialysis"):
            next_state = TREATMENT_FOLLOWUP_REASON
        else:
            next_state = NEW_CONSULT_FOLLOWUP_REASON

        # الانتقال إلى خطوة سبب العودة
        await query.message.reply_text(
            "✍️ **سبب العودة**\n\n"
            "يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return next_state

    # تحديد الحالة الحالية بناءً على نوع الإجراء
    current_flow = data_tmp.get("current_flow", "new_consult")
    if current_flow in ["followup", "periodic_followup", "inpatient_followup"]:
        current_state = FOLLOWUP_DATE_TIME
    elif current_flow == "emergency":
        current_state = EMERGENCY_DATE_TIME
    elif current_flow == "admission":
        current_state = ADMISSION_FOLLOWUP_DATE
    elif current_flow == "surgery_consult":
        current_state = SURGERY_CONSULT_FOLLOWUP_DATE
    elif current_flow == "operation":
        current_state = OPERATION_FOLLOWUP_DATE
    elif current_flow == "discharge":
        current_state = DISCHARGE_FOLLOWUP_DATE
    elif current_flow == "rehab_physical":
        current_state = PHYSICAL_THERAPY_FOLLOWUP_DATE
    elif current_flow == "device":
        current_state = DEVICE_FOLLOWUP_DATE
    elif current_flow == "endoscopy":
        current_state = ENDOSCOPY_FOLLOWUP_DATE
    elif current_flow in ("treatment_chemo", "treatment_targeted", "treatment_immuno", "treatment_dialysis"):
        current_state = TREATMENT_FOLLOWUP_DATE
    else:
        current_state = NEW_CONSULT_FOLLOWUP_TIME

    await query.answer("خطأ: لم يتم تحديد التاريخ", show_alert=True)
    return current_state


async def handle_new_consult_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 7: سبب العودة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return NEW_CONSULT_FOLLOWUP_REASON

    context.user_data["report_tmp"]["followup_reason"] = text

    await update.message.reply_text("✅ تم الحفظ")
    gate_result = await show_translator_selection(update.message, context, "new_consult")
    if gate_result == "MEDICAL_REPORT_ASK":
        return gate_result
    return NEW_CONSULT_TRANSLATOR


# Placeholder for handle_new_consult_followup_date_text (if needed)
async def handle_new_consult_followup_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج إدخال تاريخ العودة كنص (fallback)"""
    # يمكن إضافة منطق هنا إذا لزم الأمر
    return NEW_CONSULT_FOLLOWUP_DATE


__all__ = [
    'start_new_consultation_flow',
    'handle_new_consult_complaint',
    'handle_new_consult_diagnosis',
    'handle_new_consult_decision',
    'handle_new_consult_tests',
    'handle_new_consult_followup_date_skip',
    'handle_new_consult_followup_calendar_nav',
    'handle_new_consult_followup_calendar_day',
    'handle_new_consult_followup_time_hour',
    'handle_new_consult_followup_time_minute',
    'handle_new_consult_followup_time_skip',
    'handle_new_consult_followup_reason',
    'handle_new_consult_followup_date_text',
    '_render_followup_calendar',
    '_build_followup_calendar_markup',
    '_build_followup_minute_keyboard',
]
