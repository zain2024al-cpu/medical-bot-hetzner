# =============================
# action_type_handlers.py
# معالجات اختيار نوع الإجراء
# =============================

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import logging

from .states import R_ACTION_TYPE
from ..user_reports_add_helpers import PREDEFINED_ACTIONS

logger = logging.getLogger(__name__)


def _get_action_routing():
    """الحصول على ربط أنواع الإجراءات بالمسارات - يتم استدعاؤه بعد تعريف الدوال"""
    # استيراد من stub_flows.py (الذي يستورد من الملف الأصلي مؤقتاً)
    from .flows.stub_flows import (
        start_new_consultation_flow,
        start_followup_flow,
        start_periodic_followup_flow,
        start_emergency_flow,
        start_admission_flow,
        start_operation_flow,
        start_surgery_consult_flow,
        start_final_consult_flow,
        start_discharge_flow,
        start_rehab_flow,
        start_radiology_flow,
        start_reschedule_flow,
    )
    
    from .states import (
        NEW_CONSULT_COMPLAINT, FOLLOWUP_COMPLAINT, EMERGENCY_COMPLAINT,
        ADMISSION_REASON, OPERATION_DETAILS_AR, SURGERY_CONSULT_DIAGNOSIS,
        FINAL_CONSULT_DIAGNOSIS, DISCHARGE_TYPE, REHAB_TYPE, RADIOLOGY_TYPE,
        APP_RESCHEDULE_REASON
    )
    
    routing_dict = {
        "استشارة جديدة": {
            "state": NEW_CONSULT_COMPLAINT,
            "flow": start_new_consultation_flow,
            "pre_process": None
        },
        "متابعة في الرقود": {
            "state": FOLLOWUP_COMPLAINT,
            "flow": start_followup_flow,
            "pre_process": None
        },
        "مراجعة / عودة دورية": {
            "state": FOLLOWUP_COMPLAINT,
            "flow": start_periodic_followup_flow,
            "pre_process": None
        },
        "استشارة مع قرار عملية": {
            "state": SURGERY_CONSULT_DIAGNOSIS,
            "flow": start_surgery_consult_flow,
            "pre_process": None
        },
        "طوارئ": {
            "state": EMERGENCY_COMPLAINT,
            "flow": start_emergency_flow,
            "pre_process": None
        },
        "عملية": {
            "state": OPERATION_DETAILS_AR,
            "flow": start_operation_flow,
            "pre_process": None
        },
        "استشارة أخيرة": {
            "state": FINAL_CONSULT_DIAGNOSIS,
            "flow": start_final_consult_flow,
            "pre_process": lambda context: context.user_data.setdefault("report_tmp", {}).update({"complaint_text": ""})
        },
        "علاج طبيعي وإعادة تأهيل": {
            "state": REHAB_TYPE,
            "flow": start_rehab_flow,
            "pre_process": None
        },
        "ترقيد": {
            "state": ADMISSION_REASON,
            "flow": start_admission_flow,
            "pre_process": None
        },
        "خروج من المستشفى": {
            "state": DISCHARGE_TYPE,
            "flow": start_discharge_flow,
            "pre_process": None
        },
        "أشعة وفحوصات": {
            "state": RADIOLOGY_TYPE,
            "flow": start_radiology_flow,
            "pre_process": None
        },
        "تأجيل موعد": {
            "state": APP_RESCHEDULE_REASON,
            "flow": start_reschedule_flow,
            "pre_process": None
        },
    }
    
    return routing_dict


def _build_action_type_keyboard(page=0):
    """بناء لوحة مفاتيح أنواع الإجراءات - جميع الأزرار في صفحة واحدة"""
    total = len(PREDEFINED_ACTIONS)
    keyboard = []

    for i in range(total):
        action_name = PREDEFINED_ACTIONS[i]
        callback_data = f"action_idx:{i}"
        display = f"⚕️ {action_name[:20]}..." if len(action_name) > 20 else f"⚕️ {action_name}"
        keyboard.append([InlineKeyboardButton(display, callback_data=callback_data)])

    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="go_to_search_doctor_screen"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    text = f"⚕️ **نوع الإجراء** (الخطوة 6 من 6)\n\nاختر نوع الإجراء من القائمة:"

    return text, InlineKeyboardMarkup(keyboard), 1


async def show_action_type_menu(message, context, page=0):
    """عرض قائمة أنواع الإجراءات المتاحة - جميع الأزرار في صفحة واحدة"""
    context.user_data['_current_search_type'] = 'action_type'
    context.user_data['last_valid_state'] = 'action_type_selection'
    context.user_data['_conversation_state'] = R_ACTION_TYPE

    logger.info("SHOW_ACTION_TYPE_MENU: Function called")
    logger.info(f"SHOW_ACTION_TYPE_MENU: Total actions = {len(PREDEFINED_ACTIONS)}")

    text, keyboard, total_pages = _build_action_type_keyboard(0)

    try:
        await message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
        logger.info("SHOW_ACTION_TYPE_MENU: Message sent successfully")
    except Exception as e:
        logger.error(f"SHOW_ACTION_TYPE_MENU: Error sending message: {e}", exc_info=True)
        raise


async def handle_action_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج التنقل بين صفحات أنواع الإجراءات"""
    query = update.callback_query
    if not query:
        logger.error("HANDLE_ACTION_PAGE: No callback_query in update!")
        return R_ACTION_TYPE

    await query.answer()
    
    try:
        page = int(query.data.split(":", 1)[1])
        text, keyboard, total_pages = _build_action_type_keyboard(page)
        
        if page < 0 or page >= total_pages:
            await query.answer("⚠️ رقم الصفحة غير صحيح", show_alert=True)
            return R_ACTION_TYPE
        
        context.user_data['_conversation_state'] = R_ACTION_TYPE
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
        logger.info(f"HANDLE_ACTION_PAGE: Successfully navigated to page {page}")
        return R_ACTION_TYPE
    except (ValueError, IndexError) as e:
        logger.error(f"HANDLE_ACTION_PAGE: Error parsing page number: {e}", exc_info=True)
        await query.answer("⚠️ خطأ في قراءة رقم الصفحة", show_alert=True)
        return R_ACTION_TYPE
    except Exception as e:
        logger.error(f"HANDLE_ACTION_PAGE: Error in handle_action_page: {e}", exc_info=True)
        await query.answer("⚠️ خطأ في التنقل", show_alert=True)
        return R_ACTION_TYPE


async def handle_noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج لزر noop (لا يفعل شيئاً - يستخدم لعرض معلومات فقط)"""
    query = update.callback_query
    if query:
        await query.answer()
    return R_ACTION_TYPE


async def handle_stale_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج للـ callbacks القديمة من حالات سابقة"""
    query = update.callback_query
    if not query:
        return None
    
    current_state = context.user_data.get('_conversation_state', None)
    
    # ✅ إذا كان callback هو doctor_idx: وكان state = STATE_SELECT_DOCTOR، استدعاء handle_doctor_selection مباشرة
    if query.data and query.data.startswith("doctor_idx:") and current_state == STATE_SELECT_DOCTOR:
        from .doctor_handlers import handle_doctor_selection
        logger.info(f"✅ handle_stale_callback: Redirecting doctor_idx: callback to handle_doctor_selection (state={current_state})")
        return await handle_doctor_selection(update, context)
    
    try:
        await query.answer("⚠️ هذه القائمة لم تعد نشطة. يرجى استخدام القائمة الحالية.", show_alert=False)
    except Exception as e:
        logger.warning(f"⚠️ خطأ في إجابة stale callback: {e}")
    
    try:
        await query.message.delete()
    except Exception as e:
        logger.debug(f"⚠️ لا يمكن حذف الرسالة القديمة: {e}")
    
    try:
        from .hospital_handlers import show_hospitals_menu
        from .department_handlers import show_departments_menu
        from .doctor_handlers import show_doctor_input
        from .states import STATE_SELECT_HOSPITAL, STATE_SELECT_DEPARTMENT, STATE_SELECT_DOCTOR
        
        if current_state == STATE_SELECT_HOSPITAL:
            await show_hospitals_menu(query.message, context)
            return STATE_SELECT_HOSPITAL
        elif current_state == STATE_SELECT_DEPARTMENT:
            await show_departments_menu(query.message, context)
            return STATE_SELECT_DEPARTMENT
        elif current_state == STATE_SELECT_DOCTOR:
            await show_doctor_input(query.message, context)
            return STATE_SELECT_DOCTOR
        elif current_state == R_ACTION_TYPE:
            await show_action_type_menu(query.message, context)
            return R_ACTION_TYPE
    except Exception as e:
        logger.error(f"❌ خطأ في إعادة عرض القائمة: {e}", exc_info=True)
    
    return current_state if current_state is not None else R_ACTION_TYPE


async def handle_action_type_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار نوع الإجراء - جميع المسارات"""
    from telegram.ext import ConversationHandler
    
    query = update.callback_query
    if not query:
        logger.error("ACTION_TYPE_CHOICE: CRITICAL - No callback_query in update!")
        return R_ACTION_TYPE

    current_state = context.user_data.get('_conversation_state', 'NOT SET')
    
    logger.info(f"ACTION_TYPE_CHOICE: Callback data = {query.data}")
    logger.info(f"ACTION_TYPE_CHOICE: Current state = {current_state}")

    if query.data and query.data.startswith("action_page:"):
        return None

    if not query.data or not query.data.startswith("action_idx:"):
        logger.warning(f"ACTION_TYPE_CHOICE: Received unexpected callback data: {query.data}")
        await query.answer("⚠️ نوع بيانات غير متوقع", show_alert=True)
        return R_ACTION_TYPE

    try:
        await query.answer()
        logger.info("ACTION_TYPE_CHOICE: Callback answered successfully")
    except Exception as e:
        logger.error(f"ACTION_TYPE_CHOICE: Error answering callback: {e}", exc_info=True)

    try:
        action_idx = int(query.data.split(":", 1)[1])
        logger.info(f"ACTION_TYPE_CHOICE: Extracted action_idx = {action_idx}")

        if action_idx < 0 or action_idx >= len(PREDEFINED_ACTIONS):
            logger.error(f"ACTION_TYPE_CHOICE: Invalid action index: {action_idx}")
            await query.answer("نوع الإجراء غير صحيح", show_alert=True)
            return R_ACTION_TYPE

        action_name = PREDEFINED_ACTIONS[action_idx]
        logger.info(f"ACTION_TYPE_CHOICE: Selected action = '{action_name}' (index: {action_idx})")

        # حفظ نوع الإجراء
        context.user_data.setdefault("report_tmp", {})["medical_action"] = action_name
        context.user_data["report_tmp"]["action_type"] = action_name
        context.user_data["report_tmp"].setdefault("step_history", []).append(R_ACTION_TYPE)

        # حفظ flow_type
        action_to_flow_type = {
            "استشارة جديدة": "new_consult",
            "متابعة في الرقود": "followup",
            "مراجعة / عودة دورية": "followup",
            "استشارة مع قرار عملية": "surgery_consult",
            "طوارئ": "emergency",
            "عملية": "operation",
            "استشارة أخيرة": "final_consult",
            "علاج طبيعي وإعادة تأهيل": "rehab_physical",
            "ترقيد": "admission",
            "خروج من المستشفى": "discharge",
            "أشعة وفحوصات": "radiology",
            "تأجيل موعد": "appointment_reschedule",
        }

        flow_type = action_to_flow_type.get(action_name, "new_consult")
        context.user_data["report_tmp"]["current_flow"] = flow_type
        logger.info(f"ACTION_TYPE_CHOICE: Flow type = '{flow_type}' for action '{action_name}'")

        message_target = query.message if query.message else None
        if not message_target:
            logger.error("ACTION_TYPE_CHOICE: No message target available")
            await query.edit_message_text(f"تم اختيار نوع الإجراء\n\nالنوع:\n{action_name}")
            return R_ACTION_TYPE

        # البحث عن المسار المناسب
        action_routing = _get_action_routing()
        routing = action_routing.get(action_name)
        
        if not routing:
            logger.warning(f"ACTION_TYPE_CHOICE: Unknown action type: '{action_name}', using default flow")
            routing = action_routing.get("استشارة جديدة")
            if not routing:
                logger.error("ACTION_TYPE_CHOICE: CRITICAL - Default routing also not found!")
                await query.answer("خطأ: نوع الإجراء غير مدعوم", show_alert=True)
                return R_ACTION_TYPE

        # تنفيذ pre_process إذا كان موجوداً
        if routing.get("pre_process"):
            logger.info(f"ACTION_TYPE_CHOICE: Executing pre_process for action: {action_name}")
            try:
                routing["pre_process"](context)
                logger.info("ACTION_TYPE_CHOICE: pre_process completed successfully")
            except Exception as e:
                logger.error(f"ACTION_TYPE_CHOICE: Error in pre_process: {e}", exc_info=True)

        try:
            await query.edit_message_text(f"تم اختيار نوع الإجراء\n\nالنوع:\n{action_name}")
            logger.info("ACTION_TYPE_CHOICE: Message updated successfully")
        except Exception as e:
            logger.error(f"ACTION_TYPE_CHOICE: Error updating message: {e}", exc_info=True)

        # استدعاء دالة بدء المسار
        try:
            flow_function = routing["flow"]
            target_state = routing["state"]
            logger.info(f"ACTION_TYPE_CHOICE: Calling flow function: {flow_function.__name__}")
            result = await flow_function(message_target, context)
            logger.info(f"ACTION_TYPE_CHOICE: Flow function returned: {result}")
            return result if result is not None else target_state
        except Exception as e:
            logger.error(f"ACTION_TYPE_CHOICE: Error calling flow function: {e}", exc_info=True)
            await query.answer("خطأ في بدء المسار", show_alert=True)
            return R_ACTION_TYPE

    except (ValueError, IndexError) as e:
        logger.error(f"ACTION_TYPE_CHOICE: Error parsing action index: {e}", exc_info=True)
        await query.answer("⚠️ خطأ في قراءة نوع الإجراء", show_alert=True)
        return R_ACTION_TYPE
    except Exception as e:
        logger.error(f"ACTION_TYPE_CHOICE: Error in handle_action_type_choice: {e}", exc_info=True)
        await query.answer("⚠️ خطأ في معالجة اختيار نوع الإجراء", show_alert=True)
        return R_ACTION_TYPE

