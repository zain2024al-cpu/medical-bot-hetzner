# =============================
# edit_handlers/draft/handlers.py
# تعديل التقرير قبل النشر (draft editing)
# منقول من المونوليث user_reports_add_new_system.py
# =============================

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime
import calendar
import logging

logger = logging.getLogger(__name__)

try:
    from bot.handlers.user.user_reports_add_new_system.flows.shared import (
        get_confirm_state,
        show_final_summary,
        get_editable_fields_by_flow_type,
    )
except ImportError:
    logger.error("❌ Cannot import from flows/shared.py")
    get_confirm_state = lambda x: ConversationHandler.END
    show_final_summary = None
    get_editable_fields_by_flow_type = lambda x: []

try:
    from bot.handlers.user.user_reports_edit import get_editable_fields_by_action_type
except ImportError:
    logger.warning("⚠️ Cannot import get_editable_fields_by_action_type from user_reports_edit")
    get_editable_fields_by_action_type = lambda x: []


# =============================
# قائمة الحقول القابلة للتعديل (قبل النشر)
# =============================

FIELD_KEY_MAPPING = {
    'complaint_text': 'complaint',
    'doctor_decision': 'decision',
    'diagnosis': 'diagnosis',
    'notes': 'notes',
    'treatment_plan': 'treatment_plan',
    'followup_date': 'followup_date',
    'followup_reason': 'followup_reason',
    'medications': 'medications',
    'case_status': 'status',
    'admission_reason': 'admission_reason',
    'room_number': 'room_number',
    'operation_details': 'operation_details',
    'operation_name_en': 'operation_name_en',
    'tests': 'tests',
    'translator_name': 'translator_name',
    'app_reschedule_reason': 'app_reschedule_reason',
    'app_reschedule_return_date': 'app_reschedule_return_date',
    'app_reschedule_return_reason': 'app_reschedule_return_reason',
    'radiology_type': 'radiology_type',
    'radiology_delivery_date': 'radiology_delivery_date',
    'therapy_details': 'therapy_details',
    'device_details': 'device_details',
    'admission_summary': 'admission_summary',
}

FIELD_DISPLAY_NAMES = {
    'complaint_text': 'الشكوى',
    'complaint': 'الشكوى',
    'diagnosis': 'التشخيص',
    'doctor_decision': 'قرار الطبيب',
    'decision': 'قرار الطبيب',
    'notes': 'الملاحظات',
    'treatment_plan': 'خطة العلاج',
    'medications': 'الأدوية',
    'followup_date': 'تاريخ العودة',
    'followup_reason': 'سبب العودة',
    'case_status': 'حالة الطوارئ',
    'status': 'حالة الطوارئ',
    'admission_reason': 'سبب الرقود',
    'room_number': 'رقم الغرفة',
    'operation_details': 'تفاصيل العملية',
    'operation_name_en': 'اسم العملية بالإنجليزي',
    'tests': 'الفحوصات المطلوبة',
    'translator_name': 'المترجم',
    'app_reschedule_reason': 'سبب تأجيل الموعد',
    'app_reschedule_return_date': 'موعد العودة الجديد',
    'app_reschedule_return_reason': 'سبب العودة',
    'radiology_type': 'نوع الأشعة والفحوصات',
    'radiology_delivery_date': 'تاريخ التسليم',
    'therapy_details': 'تفاصيل الجلسة',
    'device_details': 'تفاصيل الجهاز',
    'admission_summary': 'ملخص الرقود',
}

DATE_FIELDS = ['followup_date', 'app_reschedule_return_date', 'radiology_delivery_date']


def _load_translator_names():
    try:
        from bot.handlers.user.user_reports_add_new_system.flows.shared import load_translator_names
        return load_translator_names()
    except Exception:
        try:
            from bot.handlers.user.user_reports_add_new_system import load_translator_names
            return load_translator_names()
        except Exception:
            return []


# =============================
# show_edit_fields_menu — عرض قائمة الحقول (callback_data: draft_field:)
# =============================

async def show_edit_fields_menu(query, context, flow_type):
    """عرض قائمة الحقول القابلة للتعديل — يُستخدم من CONFIRM states"""
    try:
        data = context.user_data.get("report_tmp", {})
        editable_fields = get_editable_fields_by_flow_type(flow_type)

        logger.info(f"🔍 show_edit_fields_menu: flow_type={flow_type}, fields={[fk for fk,_ in editable_fields]}")

        if not editable_fields:
            await query.edit_message_text(
                "⚠️ **لا توجد حقول قابلة للتعديل**\n\n"
                "يرجى استخدام زر '🔙 رجوع' للرجوع إلى الخطوات السابقة.",
                parse_mode="Markdown"
            )
            return ConversationHandler.END

        text = "✏️ **تعديل التقرير**\n\naختر الحقل الذي تريد تعديله:\n\n"
        keyboard = []

        for field_key, field_display in editable_fields:
            current_value = data.get(field_key, "")
            if not current_value or str(current_value).strip() == "" or current_value == "غير محدد":
                display_value = "⚠️ فارغ"
            elif isinstance(current_value, datetime):
                display_value = current_value.strftime('%Y-%m-%d')
            elif len(str(current_value)) > 15:
                display_value = str(current_value)[:12] + "..."
            else:
                display_value = str(current_value)

            field_display_short = field_display[:20] if len(field_display) > 20 else field_display
            keyboard.append([InlineKeyboardButton(
                f"{field_display_short}: {display_value}",
                callback_data=f"draft_field:{flow_type}:{field_key}"
            )])

        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"back_to_summary:{flow_type}")])
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")])

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

        confirm_state = get_confirm_state(flow_type)
        return confirm_state

    except Exception as e:
        logger.error(f"❌ خطأ في show_edit_fields_menu: {e}", exc_info=True)
        await query.edit_message_text(
            "❌ **حدث خطأ أثناء عرض قائمة التعديل**\n\nيرجى المحاولة مرة أخرى.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END


async def handle_edit_before_save(query, context, flow_type=None):
    """نقطة الدخول الرئيسية للتعديل قبل النشر"""
    try:
        data = context.user_data.setdefault("report_tmp", {})
        stored_flow_type = data.get("current_flow")

        if flow_type is None:
            if hasattr(query, 'data') and query.data:
                flow_type = query.data.split(":")[1] if query.data.startswith("edit:") else stored_flow_type
            else:
                flow_type = stored_flow_type

        if stored_flow_type and stored_flow_type != flow_type:
            if flow_type == "followup" and stored_flow_type in ("periodic_followup", "inpatient_followup"):
                flow_type = stored_flow_type
                logger.info(f"✅ [EDIT_BEFORE_SAVE] استخدام current_flow: {flow_type}")

        if not flow_type:
            await query.edit_message_text("❌ **حدث خطأ**\n\nلم يتم العثور على نوع التدفق.", parse_mode="Markdown")
            return ConversationHandler.END

        if flow_type == "followup" and not data.get("medical_action"):
            if data.get("room_number"):
                data["medical_action"] = "متابعة في الرقود"
            else:
                data["medical_action"] = "مراجعة / عودة دورية"
                flow_type = "periodic_followup"

        data["current_flow"] = flow_type
        return await show_edit_fields_menu(query, context, flow_type)

    except Exception as e:
        logger.error(f"❌ خطأ في handle_edit_before_save: {e}", exc_info=True)
        await query.edit_message_text(
            "❌ **حدث خطأ أثناء التعديل**\n\nيرجى المحاولة مرة أخرى.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END


# =============================
# handle_edit_draft_report — callback: edit_draft:{flow_type}
# =============================

async def handle_edit_draft_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        flow_type = query.data.split(":", 1)[1] if ":" in query.data else "new_consult"
        context.user_data.setdefault("report_tmp", {})["current_flow"] = flow_type
        return await show_edit_fields_menu(query, context, flow_type)
    except Exception as e:
        logger.error(f"❌ خطأ في handle_edit_draft_report: {e}", exc_info=True)
        await query.edit_message_text("❌ حدث خطأ في بدء عملية التعديل")
        return ConversationHandler.END


# =============================
# show_draft_edit_fields — قديم (يُستخدم من handle_back_to_edit_fields)
# =============================

async def show_draft_edit_fields(message, context, editable_fields, flow_type):
    """عرض قائمة حقول المسودة (يعرض فقط الحقول المعبأة)"""
    data = context.user_data.get("report_tmp", {})
    text = "✏️ **تعديل التقرير المؤقت**\n\nاختر الحقل الذي تريد تعديله:\n\n"
    keyboard_buttons = []

    for edit_field_key, field_name in editable_fields:
        report_key = FIELD_KEY_MAPPING.get(edit_field_key, edit_field_key)
        current_value = data.get(report_key, "")
        if not current_value or str(current_value).strip() == "":
            continue

        display_value = str(current_value)[:12] + "..." if len(str(current_value)) > 15 else str(current_value)
        field_name_short = field_name[:20] if len(field_name) > 20 else field_name
        keyboard_buttons.append([InlineKeyboardButton(
            f"{field_name_short}: {display_value}",
            callback_data=f"edit_field_draft:{edit_field_key}"
        )])

    if not keyboard_buttons:
        text = "⚠️ **لا توجد حقول مدخلة للتعديل**\n\nلم يتم إدخال أي بيانات بعد."

    keyboard_buttons.extend([
        [InlineKeyboardButton("✅ انتهيت من التعديل", callback_data=f"finish_edit_draft:{flow_type}")],
        [InlineKeyboardButton("🔙 رجوع للملخص", callback_data=f"back_to_summary:{flow_type}")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])

    try:
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard_buttons), parse_mode="Markdown")
    except Exception:
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard_buttons), parse_mode="Markdown")


# =============================
# handle_edit_draft_field — callback: edit_field_draft:{field_key}
# =============================

async def handle_edit_draft_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        edit_field_key = query.data.split(":", 1)[1] if ":" in query.data else ""
        report_key = FIELD_KEY_MAPPING.get(edit_field_key, edit_field_key)

        context.user_data['editing_field'] = report_key
        context.user_data['editing_field_original'] = edit_field_key

        if edit_field_key == 'translator_name':
            return await _render_draft_edit_translator_selection(query, context)

        if edit_field_key in DATE_FIELDS:
            context.user_data['editing_draft_date'] = True
            await _render_draft_edit_followup_calendar(query, context)
            return "EDIT_DRAFT_FOLLOWUP_CALENDAR"

        data = context.user_data.get("report_tmp", {})
        current_value = data.get(report_key, "")
        field_display_name = FIELD_DISPLAY_NAMES.get(edit_field_key, edit_field_key)
        flow_type = (context.user_data.get('edit_flow_type') or context.user_data.get('draft_flow_type') or context.user_data.get('report_tmp', {}).get('current_flow') or 'new_consult')

        await query.edit_message_text(
            f"✏️ **تعديل: {field_display_name}**\n\nالقيمة الحالية: {current_value or 'غير محدد'}\n\n📝 أدخل القيمة الجديدة:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 رجوع لقائمة الحقول", callback_data=f"back_to_edit_fields:{flow_type}")],
                [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
            ]),
            parse_mode="Markdown"
        )
        return "EDIT_DRAFT_FIELD"

    except Exception as e:
        logger.error(f"خطأ في handle_edit_draft_field: {e}", exc_info=True)
        await query.edit_message_text("❌ حدث خطأ في بدء تعديل الحقل")


# =============================
# handle_draft_field_input — إدخال نصي في EDIT_DRAFT_FIELD
# =============================

async def handle_draft_field_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip() if update.message else ""
        if "إضافة" in text and "تقرير" in text and "جديد" in text:
            from bot.handlers.user.user_reports_add_new_system import start_report
            return await start_report(update, context)

        field_key = context.user_data.get('editing_field')
        if not field_key:
            return

        context.user_data.setdefault("report_tmp", {})[field_key] = text

        safe_name = FIELD_DISPLAY_NAMES.get(field_key, field_key).replace('_', ' ')
        flow_type = context.user_data.get('draft_flow_type', 'new_consult')
        medical_action = context.user_data.get('draft_medical_action', '')

        context.user_data.pop('editing_field', None)
        context.user_data.pop('editing_field_original', None)

        await update.message.reply_text(f"✅ تم تحديث {safe_name} بنجاح!\n\n📝 اختر حقلاً آخر للتعديل أو اضغط انتهيت:", parse_mode="Markdown")

        editable_fields = get_editable_fields_by_action_type(medical_action)
        await _show_edit_fields_menu(update.message, context, editable_fields, flow_type)

        return get_confirm_state(flow_type)

    except Exception as e:
        logger.error(f"خطأ في handle_draft_field_input: {e}", exc_info=True)
        await update.message.reply_text("❌ حدث خطأ في حفظ القيمة الجديدة")


async def _show_edit_fields_menu(message, context, editable_fields, flow_type):
    """عرض قائمة الحقول بعد التعديل (reply_text)"""
    data = context.user_data.get("report_tmp", {})
    keyboard_buttons = []

    for edit_field_key, field_name in editable_fields:
        report_key = FIELD_KEY_MAPPING.get(edit_field_key, edit_field_key)
        current_value = data.get(report_key, "")
        if not current_value or str(current_value).strip() == "":
            continue
        display_value = str(current_value)[:17] + "..." if len(str(current_value)) > 20 else str(current_value)
        keyboard_buttons.append([InlineKeyboardButton(
            f"{field_name}: {display_value}",
            callback_data=f"edit_field_draft:{edit_field_key}"
        )])

    keyboard_buttons.extend([
        [InlineKeyboardButton("✅ انتهيت من التعديل", callback_data=f"finish_edit_draft:{flow_type}")],
        [InlineKeyboardButton("🔙 رجوع للملخص", callback_data=f"back_to_summary:{flow_type}")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])

    await message.reply_text(
        "📝 **قائمة الحقول:**",
        reply_markup=InlineKeyboardMarkup(keyboard_buttons),
        parse_mode="Markdown"
    )


# =============================
# handle_finish_edit_draft — callback: finish_edit_draft:{flow_type}
# =============================

async def handle_finish_edit_draft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        flow_type = query.data.split(":", 1)[1] if ":" in query.data else context.user_data.get('draft_flow_type', 'new_consult')

        for key in ('editing_draft', 'draft_flow_type', 'draft_medical_action', 'editing_field', 'editing_field_original'):
            context.user_data.pop(key, None)

        data = context.user_data.get("report_tmp", {})
        report_date = data.get("report_date")
        if report_date and hasattr(report_date, 'strftime'):
            days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
            date_str = f"{report_date.strftime('%Y-%m-%d')} ({days_ar.get(report_date.weekday(), '')})"
        else:
            date_str = str(report_date) if report_date else 'غير محدد'

        summary = (
            f"📋 **ملخص التقرير (بعد التعديل)**\n\n"
            f"📅 **التاريخ:** {date_str}\n"
            f"👤 **المريض:** {data.get('patient_name') or 'غير محدد'}\n"
            f"🏥 **المستشفى:** {data.get('hospital_name') or 'غير محدد'}\n"
            f"🏷️ **القسم:** {data.get('department_name') or 'غير محدد'}\n"
            f"👨‍⚕️ **الطبيب:** {data.get('doctor_name') or 'غير محدد'}\n"
            f"⚕️ **نوع الإجراء:** {data.get('medical_action') or 'غير محدد'}\n\n"
        )
        for field, label in [('complaint', '💬 **الشكوى:**'), ('diagnosis', '🔬 **التشخيص:**'),
                               ('decision', '📝 **قرار الطبيب:**'), ('notes', '📋 **ملاحظات:**'),
                               ('tests', '🧪 **الفحوصات:**')]:
            if data.get(field):
                summary += f"{label} {data[field]}\n"

        summary += "\n✅ **هل تريد حفظ التقرير؟**"

        await query.edit_message_text(
            summary,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💾 حفظ التقرير", callback_data=f"save:{flow_type}")],
                [InlineKeyboardButton("✏️ تعديل آخر", callback_data=f"edit_draft:{flow_type}")],
                [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
            ]),
            parse_mode="Markdown"
        )

        confirm_state = get_confirm_state(flow_type)
        context.user_data['_conversation_state'] = confirm_state
        return confirm_state

    except Exception as e:
        logger.error(f"خطأ في handle_finish_edit_draft: {e}", exc_info=True)
        try:
            await query.edit_message_text("❌ حدث خطأ في إنهاء التعديل. اضغط /start للبدء من جديد.")
        except Exception:
            pass


# =============================
# handle_back_to_edit_fields — callback: back_to_edit_fields:{flow_type}
# =============================

async def handle_back_to_edit_fields(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        flow_type = query.data.split(":", 1)[1] if ":" in query.data else context.user_data.get('draft_flow_type', 'new_consult')
        if not flow_type:
            flow_type = context.user_data.get('report_tmp', {}).get('current_flow', 'new_consult')
        from bot.handlers.user.user_reports_add_new_system.flows.shared import show_edit_fields_menu
        return await show_edit_fields_menu(query, context, flow_type)
    except Exception as e:
        logger.error(f"خطأ في handle_back_to_edit_fields: {e}", exc_info=True)
        await query.edit_message_text("❌ حدث خطأ في العودة لقائمة الحقول")


# =============================
# handle_back_to_summary — callback: back_to_summary:{flow_type}
# =============================

VALID_FLOW_TYPES = [
    "new_consult", "followup", "periodic_followup", "inpatient_followup",
    "emergency", "admission", "surgery_consult", "operation", "final_consult",
    "discharge", "rehab_physical", "rehab_device", "device",
    "radiology", "appointment_reschedule", "radiation_therapy"
]

async def handle_back_to_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        flow_type = query.data.split(":", 1)[1] if ":" in query.data else context.user_data.get('draft_flow_type', 'new_consult')
        data = context.user_data.get("report_tmp", {})
        current_flow = data.get("current_flow", "")

        if flow_type not in VALID_FLOW_TYPES and current_flow:
            flow_type = current_flow

        for key in ('editing_draft', 'draft_flow_type', 'draft_medical_action', 'editing_field',
                    'editing_field_original', 'edit_field_key', 'edit_flow_type'):
            context.user_data.pop(key, None)

        from bot.handlers.user.user_reports_add_new_system.flows.shared import show_final_summary
        await show_final_summary(query.message, context, flow_type)

        confirm_state = get_confirm_state(flow_type)
        context.user_data['_conversation_state'] = confirm_state
        return confirm_state

    except Exception as e:
        logger.error(f"❌ خطأ في handle_back_to_summary: {e}", exc_info=True)
        try:
            await query.edit_message_text(
                "❌ حدث خطأ في الرجوع للملخص.\n\nيرجى المحاولة مرة أخرى أو استخدام زر '❌ إلغاء'.",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return ConversationHandler.END


# =============================
# تقويم تاريخ العودة (draft)
# =============================

async def _render_draft_edit_followup_calendar(query, context, year=None, month=None):
    data_tmp = context.user_data.setdefault("report_tmp", {})
    if year is None or month is None:
        now = datetime.now()
        year = data_tmp.get("draft_edit_calendar_year", now.year)
        month = data_tmp.get("draft_edit_calendar_month", now.month)

    flow_type = (context.user_data.get('edit_flow_type') or context.user_data.get('draft_flow_type') or context.user_data.get('report_tmp', {}).get('current_flow') or 'new_consult')
    text, markup = _build_draft_edit_calendar_markup(year, month, flow_type)
    data_tmp["draft_edit_calendar_year"] = year
    data_tmp["draft_edit_calendar_month"] = month

    try:
        await query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"خطأ في عرض تقويم تعديل المسودة: {e}")


def _build_draft_edit_calendar_markup(year: int, month: int, flow_type: str = "unknown"):
    today = datetime.now()
    arabic_months = {1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل", 5: "مايو", 6: "يونيو",
                     7: "يوليو", 8: "أغسطس", 9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر"}
    week_header = ["س", "ح", "ن", "ث", "ر", "خ", "ج"]
    text = f"📅 **تعديل تاريخ العودة**\n\n**{arabic_months.get(month, str(month))} {year}**\nاختر تاريخ العودة الجديد:"

    keyboard = [[InlineKeyboardButton(d, callback_data="ignore") for d in week_header]]
    cal = calendar.Calendar(firstweekday=5)
    for week in cal.monthdayscalendar(year, month):
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                day_date = datetime(year, month, day).date()
                if day_date >= today.date():
                    row.append(InlineKeyboardButton(str(day), callback_data=f"draft_edit_cal_day:{year}-{month:02d}-{day:02d}"))
                else:
                    row.append(InlineKeyboardButton("·", callback_data="ignore"))
        keyboard.append(row)

    prev_y, prev_m = (year, month - 1) if month > 1 else (year - 1, 12)
    next_y, next_m = (year, month + 1) if month < 12 else (year + 1, 1)
    keyboard.append([
        InlineKeyboardButton("◀️ السابق", callback_data=f"draft_edit_cal_nav:{prev_y}-{prev_m}"),
        InlineKeyboardButton("▶️ التالي", callback_data=f"draft_edit_cal_nav:{next_y}-{next_m}")
    ])
    keyboard.append([InlineKeyboardButton("⏭️ بدون تاريخ عودة", callback_data="draft_edit_cal_skip")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع لقائمة الحقول", callback_data=f"back_to_edit_fields:{flow_type}")])
    return text, InlineKeyboardMarkup(keyboard)


async def handle_draft_edit_calendar_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        nav_data = query.data.replace("draft_edit_cal_nav:", "")
        year, month = map(int, nav_data.split("-"))
        await _render_draft_edit_followup_calendar(query, context, year, month)
        return "EDIT_DRAFT_FOLLOWUP_CALENDAR"
    except Exception as e:
        logger.error(f"خطأ في التنقل في تقويم تعديل المسودة: {e}")
        return "EDIT_DRAFT_FOLLOWUP_CALENDAR"


async def handle_draft_edit_calendar_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        date_str = query.data.replace("draft_edit_cal_day:", "")
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        context.user_data["report_tmp"]["_pending_draft_edit_date"] = dt.date()
        await _show_draft_edit_hour_selection(query, context)
        return "EDIT_DRAFT_FOLLOWUP_CALENDAR"
    except Exception as e:
        logger.error(f"خطأ في اختيار يوم من تقويم تعديل المسودة: {e}")
        return "EDIT_DRAFT_FOLLOWUP_CALENDAR"


async def _show_draft_edit_hour_selection(query, context):
    hours = []
    for h in range(24):
        if h == 0:
            display = "12 صباحاً"
        elif h < 12:
            display = f"{h} صباحاً"
        elif h == 12:
            display = "12 ظهراً"
        else:
            display = f"{h-12} مساءً"
        hours.append((str(h).zfill(2), display))

    keyboard = []
    for i in range(0, len(hours), 4):
        row = [InlineKeyboardButton(display, callback_data=f"draft_edit_time_hour:{hour}")
               for hour, display in hours[i:i+4]]
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("🔙 رجوع للتقويم", callback_data="draft_edit_back_calendar")])
    await query.edit_message_text("🕐 **اختر ساعة الموعد:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


async def handle_draft_edit_time_hour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختيار الساعة يحفظ الوقت مباشرة بدقائق 00"""
    query = update.callback_query
    await query.answer()
    try:
        hour = query.data.replace("draft_edit_time_hour:", "")
        date = context.user_data["report_tmp"].get("_pending_draft_edit_date")
        context.user_data["report_tmp"]["followup_date"] = date
        context.user_data["report_tmp"]["followup_time"] = f"{hour}:00"
        for k in ("_pending_draft_edit_date", "_pending_draft_edit_hour"):
            context.user_data["report_tmp"].pop(k, None)
        context.user_data.pop("editing_draft_date", None)
        context.user_data.pop("editing_field", None)

        hour_int = int(hour)
        if hour_int == 0:
            time_display = "12:00 صباحاً"
        elif hour_int < 12:
            time_display = f"{hour_int}:00 صباحاً"
        elif hour_int == 12:
            time_display = "12:00 ظهراً"
        else:
            time_display = f"{hour_int - 12}:00 مساءً"

        flow_type = (context.user_data.get('edit_flow_type') or
                     context.user_data.get('draft_flow_type') or
                     context.user_data.get('report_tmp', {}).get('current_flow') or 'new_consult')
        await query.edit_message_text(
            f"✅ تم تحديث تاريخ العودة: {date} الساعة {time_display}\n\nجاري العودة لقائمة الحقول...",
            parse_mode="Markdown"
        )
        return await _handle_back_to_edit_fields_direct(update, context, flow_type)
    except Exception as e:
        logger.error(f"خطأ في اختيار الساعة: {e}")
        return "EDIT_DRAFT_FOLLOWUP_CALENDAR"


async def handle_draft_edit_time_minute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """غير مستخدمة — تُبقى للتوافقية مع أي callback قديم معلّق"""
    query = update.callback_query
    await query.answer("⚠️ هذا الزر لم يعد مستخدماً", show_alert=False)
    return "EDIT_DRAFT_FOLLOWUP_CALENDAR"


async def handle_draft_edit_time_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        date = context.user_data["report_tmp"].get("_pending_draft_edit_date")
        context.user_data["report_tmp"]["followup_date"] = date
        context.user_data["report_tmp"]["followup_time"] = None
        for k in ("_pending_draft_edit_date", "_pending_draft_edit_hour"):
            context.user_data["report_tmp"].pop(k, None)
        context.user_data.pop("editing_draft_date", None)
        context.user_data.pop("editing_field", None)
        flow_type = (context.user_data.get('edit_flow_type') or
                     context.user_data.get('draft_flow_type') or
                     context.user_data.get('report_tmp', {}).get('current_flow') or 'new_consult')
        await query.edit_message_text(f"✅ تم تحديث تاريخ العودة: {date}\n\nجاري العودة لقائمة الحقول...", parse_mode="Markdown")
        return await _handle_back_to_edit_fields_direct(update, context, flow_type)
    except Exception as e:
        logger.error(f"خطأ في تخطي الوقت: {e}")
        return "EDIT_DRAFT_FOLLOWUP_CALENDAR"


async def handle_draft_edit_cal_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        context.user_data["report_tmp"]["followup_date"] = None
        context.user_data["report_tmp"]["followup_time"] = None
        context.user_data.pop("editing_draft_date", None)
        context.user_data.pop("editing_field", None)
        flow_type = (context.user_data.get('edit_flow_type') or
                     context.user_data.get('draft_flow_type') or
                     context.user_data.get('report_tmp', {}).get('current_flow') or 'new_consult')
        await query.edit_message_text("✅ تم إزالة تاريخ العودة\n\nجاري العودة لقائمة الحقول...", parse_mode="Markdown")
        return await _handle_back_to_edit_fields_direct(update, context, flow_type)
    except Exception as e:
        logger.error(f"خطأ في تخطي تاريخ العودة: {e}")
        return "EDIT_DRAFT_FOLLOWUP_CALENDAR"


async def handle_draft_edit_back_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _render_draft_edit_followup_calendar(query, context)
    return "EDIT_DRAFT_FOLLOWUP_CALENDAR"


async def handle_draft_edit_back_hour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _show_draft_edit_hour_selection(query, context)
    return "EDIT_DRAFT_FOLLOWUP_CALENDAR"


async def _handle_back_to_edit_fields_direct(update, context, flow_type: str):
    query = update.callback_query
    try:
        if not flow_type:
            flow_type = context.user_data.get('report_tmp', {}).get('current_flow', 'new_consult')
        from bot.handlers.user.user_reports_add_new_system.flows.shared import show_edit_fields_menu
        return await show_edit_fields_menu(query, context, flow_type)
    except Exception as e:
        logger.error(f"خطأ في العودة لقائمة الحقول: {e}")
        await query.edit_message_text("❌ حدث خطأ في العودة لقائمة الحقول")


# =============================
# تعديل المترجم (draft)
# =============================

async def _render_draft_edit_translator_selection(query, context):
    try:
        translator_names = _load_translator_names()
        current_translator = context.user_data.get("report_tmp", {}).get('translator_name', 'غير محدد')
        text = f"👤 **تعديل المترجم**\n\nالمترجم الحالي: {current_translator}\n\nاختر المترجم الجديد من القائمة:"

        keyboard = []
        row = []
        for i, name in enumerate(translator_names):
            row.append(InlineKeyboardButton(name, callback_data=f"draft_edit_translator:{i}"))
            if len(row) == 3 or i == len(translator_names) - 1:
                keyboard.append(row)
                row = []

        flow_type = (context.user_data.get('edit_flow_type') or context.user_data.get('draft_flow_type') or context.user_data.get('report_tmp', {}).get('current_flow') or 'new_consult')
        if context.user_data.get('_translator_edit_return') == 'summary':
            keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"back_to_summary:{flow_type}")])
        else:
            keyboard.append([InlineKeyboardButton("🔙 رجوع لقائمة الحقول", callback_data=f"back_to_edit_fields:{flow_type}")])
            keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")])

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return "EDIT_DRAFT_TRANSLATOR"

    except Exception as e:
        logger.error(f"خطأ في عرض قائمة المترجمين للتعديل: {e}")
        await query.edit_message_text("❌ حدث خطأ في تحميل قائمة المترجمين")


async def handle_draft_edit_translator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        translator_index = int(query.data.replace("draft_edit_translator:", ""))
        translator_names = _load_translator_names()

        if translator_index < 0 or translator_index >= len(translator_names):
            await query.edit_message_text("❌ اختيار غير صحيح")
            return

        new_translator_name = translator_names[translator_index]
        context.user_data.setdefault("report_tmp", {})["translator_name"] = new_translator_name
        context.user_data.pop('editing_field', None)
        context.user_data.pop('editing_field_original', None)

        flow_type = (context.user_data.get('edit_flow_type') or context.user_data.get('draft_flow_type') or context.user_data.get('report_tmp', {}).get('current_flow') or 'new_consult')

        if context.user_data.pop('_translator_edit_return', None) == 'summary':
            return await handle_back_to_summary(update, context)

        await query.edit_message_text(
            f"✅ تم تحديث المترجم: {new_translator_name}\n\nجاري العودة لقائمة الحقول...",
            parse_mode="Markdown"
        )
        return await _handle_back_to_edit_fields_direct(update, context, flow_type)

    except Exception as e:
        logger.error(f"خطأ في اختيار المترجم للمسودة: {e}")
        await query.edit_message_text("❌ حدث خطأ في تحديث المترجم")


# =============================
# Shared save/edit handlers (migrated from monolith)
# =============================

async def handle_save_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wrapper for save: callback — re-shows the summary screen."""
    query = update.callback_query
    await query.answer()
    if query.data.startswith("save:"):
        flow_type = query.data.split(":")[1]
        await show_final_summary(query.message, context, flow_type)
        confirm_state = get_confirm_state(flow_type)
        context.user_data['_conversation_state'] = confirm_state
        return confirm_state
    return ConversationHandler.END


async def handle_edit_field_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار حقل للتعديل (draft_field: callback) — يعرض طلب إدخال القيمة الجديدة."""
    query = update.callback_query
    await query.answer()
    try:
        parts = query.data.split(":")
        if len(parts) < 3:
            await query.edit_message_text("❌ خطأ في البيانات")
            return ConversationHandler.END
        flow_type = parts[1]
        field_key = parts[2]
        context.user_data["edit_field_key"] = field_key
        context.user_data["edit_flow_type"] = flow_type
        context.user_data["editing_field"] = field_key
        confirm_state = get_confirm_state(flow_type)
        current_value = context.user_data.get("report_tmp", {}).get(field_key, "غير محدد")
        if current_value and len(str(current_value)) > 200:
            current_value = str(current_value)[:200] + "..."
        await query.edit_message_text(
            f"✏️ **تعديل الحقل**\n\n"
            f"**القيمة الحالية:**\n{current_value}\n\n"
            f"📝 أرسل القيمة الجديدة:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 رجوع", callback_data=f"save:{flow_type}")],
                [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")],
            ]),
            parse_mode="Markdown"
        )
        context.user_data['_conversation_state'] = confirm_state
        return confirm_state
    except Exception as e:
        logger.error(f"handle_edit_field_selection error: {e}", exc_info=True)
        return ConversationHandler.END


async def handle_edit_field_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال القيمة الجديدة بعد اختيار حقل للتعديل."""
    try:
        text = update.message.text.strip() if update.message else ""
        field_key = context.user_data.get("edit_field_key") or context.user_data.get("editing_field")
        flow_type = (
            context.user_data.get("edit_flow_type")
            or context.user_data.get("draft_flow_type")
            or context.user_data.get("report_tmp", {}).get("current_flow")
        )
        if not field_key or not flow_type:
            return ConversationHandler.END
        data = context.user_data.setdefault("report_tmp", {})
        if field_key == "complaint":
            data["complaint_text"] = text
        elif field_key == "decision":
            data["doctor_decision"] = text
        data[field_key] = text
        context.user_data.pop("edit_field_key", None)
        context.user_data.pop("edit_flow_type", None)
        context.user_data.pop("editing_field", None)
        await show_final_summary(update.message, context, flow_type)
        confirm_state = get_confirm_state(flow_type)
        context.user_data['_conversation_state'] = confirm_state
        return confirm_state
    except Exception as e:
        logger.error(f"handle_edit_field_input error: {e}", exc_info=True)
        return ConversationHandler.END


async def debug_all_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Catch-all fallback handler — logs unmatched callbacks for debugging."""
    query = update.callback_query
    if not query:
        return None
    current_state = context.user_data.get('_conversation_state', 'NOT SET')
    logger.warning(f"debug_all_callbacks: unmatched callback data={query.data!r} state={current_state}")
    return None
