# =============================
# execute_smart_state_action.py
# تنفيذ الإجراء الذكي للخطوة المستهدفة - مستخرج من الـ monolith
# =============================

import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from .states import (
    STATE_SELECT_DATE, STATE_SELECT_PATIENT, STATE_SELECT_HOSPITAL,
    STATE_SELECT_DEPARTMENT, STATE_SELECT_SUBDEPARTMENT, STATE_SELECT_DOCTOR,
    STATE_SELECT_ACTION_TYPE,
    NEW_CONSULT_COMPLAINT, NEW_CONSULT_DIAGNOSIS, NEW_CONSULT_DECISION,
    NEW_CONSULT_TESTS, NEW_CONSULT_FOLLOWUP_DATE, NEW_CONSULT_FOLLOWUP_REASON,
    NEW_CONSULT_TRANSLATOR, NEW_CONSULT_CONFIRM,
    FOLLOWUP_COMPLAINT, FOLLOWUP_DIAGNOSIS, FOLLOWUP_DECISION, FOLLOWUP_ROOM_FLOOR,
    FOLLOWUP_DATE_TIME, FOLLOWUP_REASON, FOLLOWUP_TRANSLATOR, FOLLOWUP_CONFIRM,
    EMERGENCY_COMPLAINT, EMERGENCY_DIAGNOSIS, EMERGENCY_DECISION,
    EMERGENCY_STATUS, EMERGENCY_ADMISSION_NOTES, EMERGENCY_OPERATION_DETAILS,
    EMERGENCY_ADMISSION_TYPE, EMERGENCY_ROOM_NUMBER,
    EMERGENCY_DATE_TIME, EMERGENCY_REASON, EMERGENCY_TRANSLATOR, EMERGENCY_CONFIRM,
    ADMISSION_REASON, ADMISSION_ROOM, ADMISSION_NOTES,
    ADMISSION_FOLLOWUP_DATE, ADMISSION_FOLLOWUP_REASON,
    ADMISSION_TRANSLATOR, ADMISSION_CONFIRM,
    SURGERY_CONSULT_DIAGNOSIS, SURGERY_CONSULT_DECISION, SURGERY_CONSULT_NAME_EN,
    SURGERY_CONSULT_SUCCESS_RATE, SURGERY_CONSULT_BENEFIT_RATE, SURGERY_CONSULT_TESTS,
    SURGERY_CONSULT_FOLLOWUP_DATE, SURGERY_CONSULT_FOLLOWUP_REASON,
    SURGERY_CONSULT_TRANSLATOR, SURGERY_CONSULT_CONFIRM,
    OPERATION_DETAILS_AR, OPERATION_NAME_EN, OPERATION_NOTES,
    OPERATION_FOLLOWUP_DATE, OPERATION_FOLLOWUP_REASON,
    OPERATION_TRANSLATOR, OPERATION_CONFIRM,
    FINAL_CONSULT_DIAGNOSIS, FINAL_CONSULT_DECISION, FINAL_CONSULT_RECOMMENDATIONS,
    FINAL_CONSULT_TRANSLATOR, FINAL_CONSULT_CONFIRM,
    DISCHARGE_TYPE, DISCHARGE_ADMISSION_SUMMARY, DISCHARGE_OPERATION_DETAILS,
    DISCHARGE_OPERATION_NAME_EN, DISCHARGE_FOLLOWUP_DATE, DISCHARGE_FOLLOWUP_REASON,
    DISCHARGE_TRANSLATOR, DISCHARGE_CONFIRM,
    REHAB_TYPE, PHYSICAL_THERAPY_DETAILS, PHYSICAL_THERAPY_FOLLOWUP_DATE,
    PHYSICAL_THERAPY_FOLLOWUP_REASON, PHYSICAL_THERAPY_TRANSLATOR, PHYSICAL_THERAPY_CONFIRM,
    DEVICE_NAME_DETAILS, DEVICE_FOLLOWUP_DATE, DEVICE_FOLLOWUP_REASON,
    DEVICE_TRANSLATOR, DEVICE_CONFIRM,
    RADIOLOGY_TYPE, RADIOLOGY_DELIVERY_DATE, RADIOLOGY_TRANSLATOR, RADIOLOGY_CONFIRM,
    APP_RESCHEDULE_REASON, APP_RESCHEDULE_RETURN_DATE, APP_RESCHEDULE_RETURN_REASON,
    APP_RESCHEDULE_TRANSLATOR, APP_RESCHEDULE_CONFIRM,
)
from .utils import _nav_buttons
from .smart_state_renderer import SmartStateRenderer

logger = logging.getLogger(__name__)


def _get_smart_nav_manager():
    from services.smart_navigation_manager import smart_nav_manager
    return smart_nav_manager


async def execute_smart_state_action(target_step, flow_type, update, context):
    """
    تنفيذ الإجراء المناسب للخطوة المستهدفة مع ضمان إعادة العرض الصحيح
    يتعامل مع جميع الخطوات في جميع التدفقات
    """
    logger.debug(f"🎯 Executing SMART action for step: {target_step}, flow: {flow_type}")

    # حماية تلقائية لمسار متابعة في الرقود
    FOLLOWUP_ROOM_FLOOR_VAL = 19
    if target_step == FOLLOWUP_ROOM_FLOOR_VAL and flow_type != 'followup':
        logger.warning(f"⚠️ Auto-fixing flow_type to 'followup' for FOLLOWUP_ROOM_FLOOR step (was: {flow_type})")
        flow_type = 'followup'

    report_tmp = context.user_data.get("report_tmp", {})
    medical_action = report_tmp.get("medical_action", "")
    if medical_action == "مراجعة / عودة دورية" and flow_type != 'periodic_followup':
        logger.info(f"✅ Auto-setting flow_type to 'periodic_followup' based on medical_action (was: {flow_type})")
        flow_type = 'periodic_followup'

    context.user_data['_conversation_state'] = target_step

    state_value_to_name = {
        NEW_CONSULT_COMPLAINT: 'COMPLAINT',
        NEW_CONSULT_DIAGNOSIS: 'DIAGNOSIS',
        NEW_CONSULT_DECISION: 'DECISION',
        NEW_CONSULT_TESTS: 'TESTS',
        NEW_CONSULT_FOLLOWUP_DATE: 'FOLLOWUP_DATE',
        NEW_CONSULT_FOLLOWUP_REASON: 'FOLLOWUP_REASON',
        NEW_CONSULT_TRANSLATOR: 'TRANSLATOR',
        FOLLOWUP_COMPLAINT: 'FOLLOWUP_COMPLAINT',
        FOLLOWUP_DIAGNOSIS: 'FOLLOWUP_DIAGNOSIS',
        FOLLOWUP_DECISION: 'FOLLOWUP_DECISION',
        FOLLOWUP_ROOM_FLOOR: 'FOLLOWUP_ROOM_FLOOR',
        FOLLOWUP_DATE_TIME: 'FOLLOWUP_DATE_TIME',
        FOLLOWUP_REASON: 'FOLLOWUP_REASON',
        FOLLOWUP_TRANSLATOR: 'TRANSLATOR',
        EMERGENCY_COMPLAINT: 'COMPLAINT',
        EMERGENCY_DIAGNOSIS: 'DIAGNOSIS',
        EMERGENCY_DECISION: 'DECISION',
        EMERGENCY_STATUS: 'STATUS',
        EMERGENCY_ADMISSION_NOTES: 'EMERGENCY_ADMISSION_NOTES',
        EMERGENCY_OPERATION_DETAILS: 'EMERGENCY_OPERATION_DETAILS',
        EMERGENCY_ADMISSION_TYPE: 'ADMISSION_TYPE',
        EMERGENCY_ROOM_NUMBER: 'ROOM',
        EMERGENCY_DATE_TIME: 'FOLLOWUP_DATE',
        EMERGENCY_REASON: 'FOLLOWUP_REASON',
        EMERGENCY_TRANSLATOR: 'TRANSLATOR',
        ADMISSION_REASON: 'REASON',
        ADMISSION_ROOM: 'ROOM',
        ADMISSION_NOTES: 'NOTES',
        ADMISSION_FOLLOWUP_DATE: 'FOLLOWUP_DATE',
        ADMISSION_FOLLOWUP_REASON: 'FOLLOWUP_REASON',
        ADMISSION_TRANSLATOR: 'TRANSLATOR',
        SURGERY_CONSULT_DIAGNOSIS: 'DIAGNOSIS',
        SURGERY_CONSULT_DECISION: 'DECISION',
        SURGERY_CONSULT_NAME_EN: 'NAME_EN',
        SURGERY_CONSULT_SUCCESS_RATE: 'SUCCESS_RATE',
        SURGERY_CONSULT_BENEFIT_RATE: 'BENEFIT_RATE',
        SURGERY_CONSULT_TESTS: 'TESTS',
        SURGERY_CONSULT_FOLLOWUP_DATE: 'FOLLOWUP_DATE',
        SURGERY_CONSULT_FOLLOWUP_REASON: 'FOLLOWUP_REASON',
        SURGERY_CONSULT_TRANSLATOR: 'TRANSLATOR',
        OPERATION_DETAILS_AR: 'DETAILS_AR',
        OPERATION_NAME_EN: 'NAME_EN',
        OPERATION_NOTES: 'NOTES',
        OPERATION_FOLLOWUP_DATE: 'FOLLOWUP_DATE',
        OPERATION_FOLLOWUP_REASON: 'FOLLOWUP_REASON',
        OPERATION_TRANSLATOR: 'TRANSLATOR',
        FINAL_CONSULT_DIAGNOSIS: 'DIAGNOSIS',
        FINAL_CONSULT_DECISION: 'DECISION',
        FINAL_CONSULT_RECOMMENDATIONS: 'RECOMMENDATIONS',
        FINAL_CONSULT_TRANSLATOR: 'TRANSLATOR',
        DISCHARGE_TYPE: 'DISCHARGE_TYPE',
        DISCHARGE_ADMISSION_SUMMARY: 'ADMISSION_SUMMARY',
        DISCHARGE_OPERATION_DETAILS: 'OPERATION_DETAILS',
        DISCHARGE_OPERATION_NAME_EN: 'NAME_EN',
        DISCHARGE_FOLLOWUP_DATE: 'FOLLOWUP_DATE',
        DISCHARGE_FOLLOWUP_REASON: 'FOLLOWUP_REASON',
        DISCHARGE_TRANSLATOR: 'TRANSLATOR',
        REHAB_TYPE: 'REHAB_TYPE',
        PHYSICAL_THERAPY_DETAILS: 'THERAPY_DETAILS',
        PHYSICAL_THERAPY_FOLLOWUP_DATE: 'FOLLOWUP_DATE',
        PHYSICAL_THERAPY_FOLLOWUP_REASON: 'FOLLOWUP_REASON',
        PHYSICAL_THERAPY_TRANSLATOR: 'TRANSLATOR',
        DEVICE_NAME_DETAILS: 'DEVICE_DETAILS',
        DEVICE_FOLLOWUP_DATE: 'FOLLOWUP_DATE',
        DEVICE_FOLLOWUP_REASON: 'FOLLOWUP_REASON',
        DEVICE_TRANSLATOR: 'TRANSLATOR',
        RADIOLOGY_TYPE: 'RADIOLOGY_TYPE',
        RADIOLOGY_DELIVERY_DATE: 'DELIVERY_DATE',
        RADIOLOGY_TRANSLATOR: 'TRANSLATOR',
        RADIOLOGY_CONFIRM: 'CONFIRM',
        APP_RESCHEDULE_REASON: 'RESCHEDULE_REASON',
        APP_RESCHEDULE_RETURN_DATE: 'RETURN_DATE',
        APP_RESCHEDULE_RETURN_REASON: 'RETURN_REASON',
        APP_RESCHEDULE_TRANSLATOR: 'TRANSLATOR',
        APP_RESCHEDULE_CONFIRM: 'CONFIRM',
        NEW_CONSULT_CONFIRM: 'CONFIRM',
        FOLLOWUP_CONFIRM: 'CONFIRM',
        SURGERY_CONSULT_CONFIRM: 'CONFIRM',
        EMERGENCY_CONFIRM: 'CONFIRM',
        ADMISSION_CONFIRM: 'CONFIRM',
        OPERATION_CONFIRM: 'CONFIRM',
        FINAL_CONSULT_CONFIRM: 'CONFIRM',
        DISCHARGE_CONFIRM: 'CONFIRM',
        PHYSICAL_THERAPY_CONFIRM: 'CONFIRM',
        DEVICE_CONFIRM: 'CONFIRM',
    }

    if isinstance(target_step, int):
        step_name = state_value_to_name.get(target_step, str(target_step))
    else:
        step_name = str(target_step)

    logger.info(f"🎯 Step name for comparison: {step_name}")

    try:
        if target_step == STATE_SELECT_DATE:
            _q = update.callback_query if update.callback_query else None
            _msg = _q.message if _q else update.message
            from .date_time_handlers import render_date_selection as _render_date
            await _render_date(_msg, context, query=_q)
            return target_step

        elif target_step == STATE_SELECT_PATIENT:
            await SmartStateRenderer.ensure_search_context(context, 'patient')
            _q = update.callback_query if update.callback_query else None
            _msg = _q.message if _q else update.message
            await SmartStateRenderer.render_patient_selection(_msg, context, query=_q,
                                                               restore=True, update=update)
            return target_step

        elif target_step == STATE_SELECT_HOSPITAL:
            await SmartStateRenderer.ensure_search_context(context, 'hospital')
            _q = update.callback_query if update.callback_query else None
            _msg = _q.message if _q else update.message
            from .hospital_handlers import show_hospitals_menu
            await show_hospitals_menu(_msg, context, query=_q, restore=True)
            return target_step

        elif target_step == STATE_SELECT_DEPARTMENT:
            await SmartStateRenderer.ensure_search_context(context, 'department')
            _q = update.callback_query if update.callback_query else None
            _msg = _q.message if _q else update.message
            from .department_handlers import show_departments_menu
            await show_departments_menu(_msg, context, query=_q, restore=True)
            return target_step

        elif target_step == STATE_SELECT_SUBDEPARTMENT:
            await SmartStateRenderer.ensure_search_context(context, 'subdepartment')
            main_dept = context.user_data.get('report_tmp', {}).get('main_department', 'الجراحة')
            from .department_handlers import show_subdepartment_options
            await show_subdepartment_options(update.callback_query.message, context, main_dept)
            return target_step

        elif target_step == STATE_SELECT_DOCTOR:
            await SmartStateRenderer.ensure_search_context(context, 'doctor')
            _q = update.callback_query if update.callback_query else None
            _msg = _q.message if _q else update.message
            await SmartStateRenderer.render_doctor_selection(_msg, context, query=_q)
            return target_step

        elif target_step == STATE_SELECT_ACTION_TYPE:
            _q = update.callback_query if update.callback_query else None
            _msg = _q.message if _q else update.message
            report_tmp = context.user_data.get("report_tmp", {})
            report_tmp.pop("medical_action", None)
            report_tmp.pop("action_type", None)
            report_tmp.pop("current_flow", None)
            from .action_type_handlers import show_action_type_menu
            await show_action_type_menu(_msg, context, query=_q)
            return target_step

        elif 'TRANSLATOR' in step_name:
            # عند الرجوع من المترجم — أعد عرض بوابة "هل يوجد تقرير طبي؟"
            _rt = context.user_data.get("report_tmp", {})
            _rt.pop("_medical_report_step_done", None)
            _rt.pop("_medical_attachments", None)
            _rt.pop("no_report_reason", None)

            _pending_flow = _rt.get("_pending_translator_flow", flow_type)
            if flow_type == "operation":
                gate_text = "📎 **هل يوجد تقرير طبي او صور للعملية؟**\n\n• ✅ يوجد تقرير طبي\n• 🟡 لم يجهز بعد\n• ❌ لا يوجد تقرير"
            elif flow_type in ("rehab_physical", "rehab_device", "device"):
                gate_text = "📎 **هل يوجد صور او فيدوهات للتمارين؟**\n\n• ✅ يوجد تقرير طبي\n• 🟡 لم يجهز بعد\n• ❌ لا يوجد تقرير"
            else:
                gate_text = "📎 **هل يوجد تقرير طبي؟**\n\n• ✅ يوجد تقرير طبي\n• 🟡 لم يجهز بعد\n• ❌ لا يوجد تقرير"

            # ✅ بوابة موحّدة بثلاث حالات (مصدر واحد مشترَك، بلا زر "تخطي")
            from .flows.shared import build_medical_report_gate_keyboard
            await update.callback_query.edit_message_text(
                gate_text,
                reply_markup=build_medical_report_gate_keyboard(),
                parse_mode="Markdown",
            )
            context.user_data["_conversation_state"] = "MEDICAL_REPORT_ASK"
            return "MEDICAL_REPORT_ASK"

        elif step_name == 'FOLLOWUP_DATE_TIME' or 'FOLLOWUP_DATE' in step_name or 'DELIVERY_DATE' in step_name or 'RETURN_DATE' in step_name:
            if 'DELIVERY_DATE' in step_name and flow_type == 'radiology':
                from .flows.radiology import _render_radiology_calendar
                await _render_radiology_calendar(update.callback_query.message, context)
            elif 'RETURN_DATE' in step_name and flow_type == 'app_reschedule':
                from .flows.app_reschedule import _show_reschedule_calendar
                await _show_reschedule_calendar(update.callback_query.message, context)
            else:
                from .flows.new_consult import _render_followup_calendar
                await _render_followup_calendar(update.callback_query.message, context)
            return target_step

        elif 'FOLLOWUP_REASON' in step_name or 'RETURN_REASON' in step_name:
            current_value = context.user_data.get("report_tmp", {}).get("followup_reason", "")
            message_text = "✍️ **سبب العودة**\n\nيرجى إدخال سبب العودة:"
            if current_value:
                message_text += f"\n\n📋 **القيمة الحالية:**\n```\n{current_value}\n```"
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )
            return target_step

        elif 'COMPLAINT' in step_name:
            current_value = context.user_data.get("report_tmp", {}).get("complaint", "")
            if flow_type == 'followup':
                complaint_label = "💬 **شكوى المريض**\n\nأدخل حالة المريض اليومية:"
            elif flow_type == 'periodic_followup':
                complaint_label = "💬 **مراجعة / عودة دورية**\n\nأدخل شكوى المريض:"
            else:
                complaint_label = "💬 **شكوى المريض**\n\nيرجى إدخال شكوى المريض:"
            if current_value:
                complaint_label += f"\n\n📋 **القيمة الحالية:**\n```\n{current_value}\n```"
            await update.callback_query.edit_message_text(
                complaint_label,
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )
            return target_step

        elif 'DIAGNOSIS' in step_name:
            current_value = context.user_data.get("report_tmp", {}).get("diagnosis", "")
            if flow_type == 'final_consult':
                diagnosis_label = "🔬 **التشخيص النهائي**\n\nيرجى إدخال التشخيص النهائي:"
            elif flow_type == 'surgery_consult':
                diagnosis_label = "🔬 **التشخيص الطبي**\n\nيرجى إدخال التشخيص الطبي:"
            elif flow_type == 'emergency':
                diagnosis_label = "🔬 **التشخيص الطبي**\n\nيرجى إدخال التشخيص الطبي:"
            elif flow_type in ('followup', 'periodic_followup'):
                diagnosis_label = "🔬 **مراجعة / عودة دورية: التشخيص**\n\nأدخل التشخيص:"
            else:
                diagnosis_label = "🔬 **التشخيص**\n\nيرجى إدخال التشخيص:"
            if current_value:
                diagnosis_label += f"\n\n📋 **القيمة الحالية:**\n```\n{current_value}\n```"
            await update.callback_query.edit_message_text(
                diagnosis_label,
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )
            return target_step

        elif 'DECISION' in step_name:
            current_value = context.user_data.get("report_tmp", {}).get("decision", "")
            if flow_type == 'final_consult':
                decision_label = "📝 **تفاصيل قرار الطبيب**\n\nيرجى إدخال تفاصيل قرار الطبيب:"
            elif flow_type == 'surgery_consult':
                decision_label = "📝 **قرار الطبيب وتفاصيل العملية**\n\nيرجى إدخال قرار الطبيب وتفاصيل العملية المقترحة:"
            elif flow_type == 'emergency':
                decision_label = "📝 **قرار الطبيب وماذا تم للحالة في الطوارئ**\n\nيرجى إدخال قرار الطبيب وتفاصيل ما تم للحالة:"
            elif flow_type == 'followup':
                decision_label = "📝 **متابعة في الرقود: قرار الطبيب اليومي**\n\nأدخل قرار الطبيب اليومي:"
            elif flow_type == 'periodic_followup':
                decision_label = "📝 **مراجعة / عودة دورية: قرار الطبيب**\n\nأدخل قرار الطبيب:"
            else:
                decision_label = "📝 **قرار الطبيب**\n\nيرجى إدخال قرار الطبيب:"
            if current_value:
                decision_label += f"\n\n📋 **القيمة الحالية:**\n```\n{current_value}\n```"
            await update.callback_query.edit_message_text(
                decision_label,
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )
            return target_step

        elif 'TESTS' in step_name:
            current_value = context.user_data.get("report_tmp", {}).get("tests", "")
            if flow_type == 'surgery_consult':
                tests_label = "🔬 **الفحوصات والأشعة المطلوبة**\n\nيرجى إدخال الفحوصات والأشعة المطلوبة قبل العملية:\n(أو اكتب 'لا يوجد')"
            else:
                tests_label = "🔬 **الفحوصات المطلوبة**\n\nيرجى إدخال الفحوصات المطلوبة..."
            if current_value:
                tests_label += f"\n\n📋 **القيمة الحالية:**\n```\n{current_value}\n```"
            await update.callback_query.edit_message_text(
                tests_label,
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )
            return target_step

        elif 'NAME_EN' in step_name:
            if flow_type == 'surgery_consult':
                name_label = "🔤 **اسم العملية بالإنجليزي**\n\nيرجى إدخال اسم العملية بالإنجليزي:\nمثال: Laparoscopic Cholecystectomy"
            elif flow_type == 'discharge':
                name_label = "🔤 **اسم العملية بالإنجليزي**\n\nيرجى إدخال اسم العملية بالإنجليزي:"
            else:
                name_label = "🔤 **اسم العملية بالإنجليزي**\n\nيرجى إدخال اسم العملية بالإنجليزي:\nمثال: Appendectomy"
            await update.callback_query.edit_message_text(
                name_label,
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )
            return target_step

        elif 'DETAILS_AR' in step_name or 'OPERATION_DETAILS' in step_name:
            if flow_type == 'operation':
                details_label = "⚕️ **تفاصيل العملية التي تمت للحالة**\n\nيرجى إدخال تفاصيل العملية بالعربي:"
            elif flow_type == 'discharge':
                details_label = "⚕️ **تفاصيل العملية التي تمت للحالة**\n\nيرجى إدخال تفاصيل العملية:"
            else:
                details_label = "📝 **تفاصيل العملية**\n\nيرجى إدخال تفاصيل العملية بالعربي:"
            await update.callback_query.edit_message_text(
                details_label,
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )
            return target_step

        elif 'NOTES' in step_name:
            if flow_type == 'radiation_therapy':
                notes_label = "📝 **ملاحظات أو توصيات**\n\nيرجى إدخال أي ملاحظات أو توصيات خاصة بالجلسة:\n(اختياري - أرسل 'تخطي' للمتابعة)"
            else:
                notes_label = "📝 **ملاحظات**\n\nيرجى إدخال أي ملاحظات إضافية:\n(أو اكتب 'لا يوجد')"
            await update.callback_query.edit_message_text(
                notes_label,
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )
            return target_step

        elif step_name == 'FOLLOWUP_ROOM_FLOOR':
            if flow_type == 'periodic_followup':
                logger.info("🔄 FOLLOWUP_ROOM_FLOOR in periodic_followup flow - skipping to previous step")
                smart_nav = _get_smart_nav_manager()
                previous_step = smart_nav.get_previous_step(flow_type, target_step, context)
                if previous_step is not None:
                    context.user_data['_conversation_state'] = previous_step
                    return await execute_smart_state_action(previous_step, flow_type, update, context)
                else:
                    current_value = context.user_data.get("report_tmp", {}).get("decision", "")
                    message_text = "📝 **مراجعة / عودة دورية: قرار الطبيب**\n\nأدخل قرار الطبيب:"
                    if current_value:
                        message_text += f"\n\n📋 **القيمة الحالية:**\n```\n{current_value}\n```"
                    await update.callback_query.edit_message_text(
                        message_text,
                        reply_markup=_nav_buttons(show_back=True),
                        parse_mode="Markdown"
                    )
                    return FOLLOWUP_DECISION
            else:
                current_value = context.user_data.get("report_tmp", {}).get("room_number", "")
                from telegram import ReplyKeyboardMarkup
                message_text = "🏥 **متابعة في الرقود: رقم الغرفة والطابق**\n\nأدخل رقم الغرفة والطابق (مثال: غرفة 205 - الطابق الثاني):"
                if current_value:
                    message_text += f"\n\n📋 **القيمة الحالية:**\n```\n{current_value}\n```"
                skip_keyboard = ReplyKeyboardMarkup([["تخطي"]], resize_keyboard=True)
                await update.callback_query.edit_message_text(
                    message_text,
                    reply_markup=skip_keyboard,
                    parse_mode="Markdown"
                )
            return target_step

        elif 'ROOM' in step_name:
            if flow_type == 'admission':
                room_label = "🚪 **رقم الغرفة**\n\nيرجى إدخال رقم الغرفة:\n(أو اكتب 'لم يتم التحديد' إذا لم يتم تحديدها بعد)"
            elif flow_type == 'emergency':
                room_label = "🛏️ **رقم الغرفة والطابق**\n\nيرجى إدخال رقم الغرفة والطابق:"
            else:
                room_label = "🚪 **رقم الغرفة**\n\nيرجى إدخال رقم الغرفة:"
            await update.callback_query.edit_message_text(
                room_label,
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )
            return target_step

        elif 'REASON' in step_name and 'FOLLOWUP' not in step_name and 'RETURN' not in step_name and 'RESCHEDULE' not in step_name:
            if flow_type == 'admission':
                reason_label = "🛏️ **سبب الرقود**\n\nيرجى إدخال سبب رقود المريض:"
            else:
                reason_label = "📝 **السبب**\n\nيرجى إدخال السبب:"
            await update.callback_query.edit_message_text(
                reason_label,
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )
            return target_step

        elif 'RESCHEDULE_REASON' in step_name:
            await update.callback_query.edit_message_text(
                "📝 **سبب تأجيل الموعد**\n\nيرجى إدخال سبب تأجيل الموعد:",
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )
            return target_step

        elif 'SUCCESS_RATE' in step_name:
            await update.callback_query.edit_message_text(
                "📊 **نسبة نجاح العملية**\n\nيرجى إدخال نسبة نجاح العملية المتوقعة:\nمثال: 95%",
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )
            return target_step

        elif 'BENEFIT_RATE' in step_name:
            await update.callback_query.edit_message_text(
                "💡 **نسبة الاستفادة من العملية**\n\nيرجى إدخال نسبة الاستفادة المتوقعة من العملية:\nمثال: تحسن كامل، تحسن جزئي، تحسن طفيف",
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )
            return target_step

        elif 'RECOMMENDATIONS' in step_name:
            await update.callback_query.edit_message_text(
                "📝 **التوصيات الطبية**\n\nيرجى إدخال التوصيات الطبية:",
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )
            return target_step

        elif 'ADMISSION_TYPE' in step_name and flow_type == 'emergency':
            await update.callback_query.edit_message_text(
                "🏥 **أين تم الترقيد؟**",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏥 العناية المركزة", callback_data="emerg_admission:icu")],
                    [InlineKeyboardButton("🛏️ الرقود", callback_data="emerg_admission:ward")],
                    [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back")],
                    [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")],
                ]),
                parse_mode="Markdown"
            )
            return target_step

        elif 'TYPE' in step_name and target_step != STATE_SELECT_ACTION_TYPE:
            if 'REHAB' in step_name:
                await update.callback_query.edit_message_text(
                    "🏃 **علاج طبيعي / أجهزة تعويضية**\n\nاختر النوع:",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🏃 علاج طبيعي", callback_data="rehab_type:physical_therapy")],
                        [InlineKeyboardButton("🦾 أجهزة تعويضية", callback_data="rehab_type:device")],
                        [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back")],
                        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")],
                    ]),
                    parse_mode="Markdown"
                )
            elif 'DISCHARGE' in step_name:
                await update.callback_query.edit_message_text(
                    "🏠 **خروج من المستشفى**\n\n"
                    "اختر نوع الخروج:",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🛏️ خروج بعد رقود طبي", callback_data="discharge_type:admission")],
                        [InlineKeyboardButton("⚕️ خروج بعد عملية", callback_data="discharge_type:operation")],
                        [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back")],
                        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
                    ]),
                    parse_mode="Markdown"
                )
            elif 'RADIOLOGY' in step_name:
                await update.callback_query.edit_message_text(
                    "🔬 **نوع الأشعة والفحوصات**\n\n"
                    "يرجى إدخال نوع الأشعة أو الفحوصات:",
                    reply_markup=_nav_buttons(show_back=True),
                    parse_mode="Markdown"
                )
            else:
                await update.callback_query.edit_message_text(
                    "📝 اختر النوع:",
                    reply_markup=_nav_buttons(show_back=True),
                    parse_mode="Markdown"
                )
            return target_step

        elif step_name == 'EMERGENCY_ADMISSION_NOTES':
            current_value = context.user_data.get("report_tmp", {}).get("admission_notes", "")
            message_text = "📝 **ملاحظات الرقود**\n\nيرجى توضيح ماذا تم وما هي خطة الرقود:"
            if current_value:
                message_text += f"\n\n📋 **القيمة الحالية:**\n```\n{current_value}\n```"
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )
            return target_step

        elif step_name == 'EMERGENCY_OPERATION_DETAILS':
            current_value = context.user_data.get("report_tmp", {}).get("operation_details", "")
            message_text = "⚕️ **تفاصيل العملية**\n\nيرجى إدخال ماهي العملية التي تمت للحالة:"
            if current_value:
                message_text += f"\n\n📋 **القيمة الحالية:**\n```\n{current_value}\n```"
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )
            return target_step

        elif 'STATUS' in step_name:
            await update.callback_query.edit_message_text(
                "🏥 **وضع الحالة**\n\nما هو وضع الحالة الآن؟",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 تم الخروج من الطوارئ", callback_data="emerg_status:discharged")],
                    [InlineKeyboardButton("🛏️ تم الترقيد", callback_data="emerg_status:admitted")],
                    [InlineKeyboardButton("⚕️ تم إجراء عملية", callback_data="emerg_status:operation")],
                    [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back")],
                    [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")],
                ]),
                parse_mode="Markdown"
            )
            return target_step

        elif 'CONFIRM' in step_name:
            from .flows.shared import show_final_summary
            await show_final_summary(update.callback_query.message, context, flow_type)
            return target_step

        elif 'ADMISSION_SUMMARY' in step_name:
            await update.callback_query.edit_message_text(
                "📋 **أبرز ما تم للحالة أثناء الرقود**\n\nيرجى إدخال ملخص ما تم للحالة:",
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )
            return target_step

        elif 'THERAPY_DETAILS' in step_name:
            await update.callback_query.edit_message_text(
                "🏃 **تفاصيل جلسة العلاج الطبيعي**\n\nيرجى إدخال تفاصيل الجلسة:",
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )
            return target_step

        elif 'DEVICE_DETAILS' in step_name:
            await update.callback_query.edit_message_text(
                "🦾 **اسم الجهاز الذي تم توفيره مع التفاصيل**\n\nيرجى إدخال اسم الجهاز والتفاصيل:",
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )
            return target_step

        elif target_step == "MEDICAL_REPORT_ASK":
            # ✅ بوابة موحّدة بثلاث حالات (مصدر واحد مشترَك، بلا زر "تخطي")
            from .flows.shared import build_medical_report_gate_keyboard
            context.user_data["_conversation_state"] = "MEDICAL_REPORT_ASK"
            await update.callback_query.edit_message_text(
                "📎 **هل يوجد تقرير طبي؟**\n\n"
                "• ✅ يوجد تقرير طبي\n• 🟡 لم يجهز بعد\n• ❌ لا يوجد تقرير",
                reply_markup=build_medical_report_gate_keyboard(),
                parse_mode="Markdown",
            )
            return "MEDICAL_REPORT_ASK"

        else:
            logger.warning(f"⚠️ Unknown target step: {target_step}")
            await update.callback_query.edit_message_text(
                f"⚠️ خطأ في التنقل\n\nيرجى المحاولة مرة أخرى",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
                    InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
                ]])
            )
            return target_step

    except Exception as e:
        logger.error(f"❌ Error in execute_smart_state_action: {e}", exc_info=True)
        try:
            await update.callback_query.edit_message_text(
                "❌ حدث خطأ في إعادة العرض\n\nيرجى المحاولة مرة أخرى",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
                    InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
                ]])
            )
        except Exception:
            pass
        return target_step


__all__ = ['execute_smart_state_action']
