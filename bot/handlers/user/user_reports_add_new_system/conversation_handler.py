# =============================
# conversation_handler.py
# تسجيل ConversationHandler - يستخدم الملفات المقسمة والـ flows
# =============================

from telegram.ext import ConversationHandler, MessageHandler, CallbackQueryHandler, InlineQueryHandler, ChosenInlineResultHandler, filters
from telegram.constants import ChatType
import logging
import os
import sys
import importlib.util

logger = logging.getLogger(__name__)

# =============================
# استيراد handlers من الملفات المقسمة
# =============================

# Date & Time handlers
from .date_time_handlers import (
    start_report, render_date_selection, handle_date_choice,
    handle_main_calendar_nav, handle_main_calendar_day,
    handle_date_time_hour, handle_date_time_minute, handle_date_time_skip,
    handle_date_time_back_hour, handle_step_back_date
)

# Patient handlers
from .patient_handlers import (
    show_patient_selection, render_patient_selection,
    show_patient_list, handle_patient_list_callback,
    handle_patient_selection, handle_patient
)

# Hospital handlers
from .hospital_handlers import (
    render_hospital_selection, handle_hospital_selection,
    handle_hospital_page, handle_hospital_search, show_hospitals_menu
)

# Department handlers
from .department_handlers import (
    render_department_selection, handle_department_selection,
    handle_department_page, handle_department_search, show_departments_menu,
    show_subdepartment_options, handle_subdepartment_choice, handle_subdepartment_page
)

# Doctor handlers
from .doctor_handlers import (
    render_doctor_selection, show_doctor_input, handle_doctor_selection, handle_doctor
)

# Action type handlers
from .action_type_handlers import (
    show_action_type_menu, handle_action_type_choice, handle_action_page,
    handle_noop, handle_stale_callback
)

# Navigation helpers
from .navigation_helpers import handle_cancel_navigation, handle_go_to_state

# Inline query handlers - لا نستخدمها حالياً، نعتمد على الملف الأصلي
# from .inline_query import unified_inline_query_handler, translator_inline_query_handler

# States
from .states import (
    STATE_SELECT_DATE, STATE_SELECT_DATE_TIME, STATE_SELECT_PATIENT,
    STATE_SELECT_HOSPITAL, STATE_SELECT_DEPARTMENT, STATE_SELECT_SUBDEPARTMENT,
    STATE_SELECT_DOCTOR, STATE_SELECT_ACTION_TYPE,
    R_ACTION_TYPE,
    R_DATE, R_DATE_TIME, R_PATIENT, R_HOSPITAL, R_DEPARTMENT, R_SUBDEPARTMENT, R_DOCTOR,
    # Flow states - سيتم استيرادها من الملف الأصلي مؤقتاً
    NEW_CONSULT_COMPLAINT, NEW_CONSULT_DECISION, NEW_CONSULT_TESTS, NEW_CONSULT_FOLLOWUP_DATE, NEW_CONSULT_FOLLOWUP_TIME,
    NEW_CONSULT_FOLLOWUP_REASON, NEW_CONSULT_TRANSLATOR, NEW_CONSULT_CONFIRM,
    FOLLOWUP_COMPLAINT, FOLLOWUP_DIAGNOSIS, FOLLOWUP_DECISION, FOLLOWUP_ROOM_FLOOR,
    FOLLOWUP_DATE_TIME, FOLLOWUP_REASON, FOLLOWUP_TRANSLATOR, FOLLOWUP_CONFIRM,
    EMERGENCY_COMPLAINT, EMERGENCY_DIAGNOSIS, EMERGENCY_DECISION, EMERGENCY_STATUS, EMERGENCY_ADMISSION_TYPE,
    EMERGENCY_ROOM_NUMBER, EMERGENCY_DATE_TIME, EMERGENCY_REASON, EMERGENCY_TRANSLATOR, EMERGENCY_CONFIRM,
    ADMISSION_REASON, ADMISSION_ROOM, ADMISSION_NOTES, ADMISSION_FOLLOWUP_DATE, ADMISSION_FOLLOWUP_REASON,
    ADMISSION_TRANSLATOR, ADMISSION_CONFIRM,
    SURGERY_CONSULT_DIAGNOSIS, SURGERY_CONSULT_DECISION, SURGERY_CONSULT_NAME_EN, SURGERY_CONSULT_SUCCESS_RATE,
    SURGERY_CONSULT_BENEFIT_RATE, SURGERY_CONSULT_TESTS, SURGERY_CONSULT_FOLLOWUP_DATE, SURGERY_CONSULT_FOLLOWUP_REASON,
    SURGERY_CONSULT_TRANSLATOR, SURGERY_CONSULT_CONFIRM,
    OPERATION_DETAILS_AR, OPERATION_NAME_EN, OPERATION_NOTES, OPERATION_FOLLOWUP_DATE, OPERATION_FOLLOWUP_REASON,
    OPERATION_TRANSLATOR, OPERATION_CONFIRM,
    FINAL_CONSULT_DIAGNOSIS, FINAL_CONSULT_DECISION, FINAL_CONSULT_RECOMMENDATIONS, FINAL_CONSULT_TRANSLATOR, FINAL_CONSULT_CONFIRM,
    DISCHARGE_TYPE, DISCHARGE_ADMISSION_SUMMARY, DISCHARGE_OPERATION_DETAILS, DISCHARGE_OPERATION_NAME_EN,
    DISCHARGE_FOLLOWUP_DATE, DISCHARGE_FOLLOWUP_REASON, DISCHARGE_TRANSLATOR, DISCHARGE_CONFIRM,
    REHAB_TYPE, PHYSICAL_THERAPY_DETAILS, PHYSICAL_THERAPY_FOLLOWUP_DATE, PHYSICAL_THERAPY_FOLLOWUP_REASON,
    PHYSICAL_THERAPY_TRANSLATOR, PHYSICAL_THERAPY_CONFIRM, DEVICE_NAME_DETAILS, DEVICE_FOLLOWUP_DATE,
    DEVICE_FOLLOWUP_REASON, DEVICE_TRANSLATOR, DEVICE_CONFIRM,
    RADIOLOGY_TYPE, RADIOLOGY_DELIVERY_DATE, RADIOLOGY_TRANSLATOR, RADIOLOGY_CONFIRM,
    APP_RESCHEDULE_REASON, APP_RESCHEDULE_RETURN_DATE, APP_RESCHEDULE_RETURN_REASON,
    APP_RESCHEDULE_TRANSLATOR, APP_RESCHEDULE_CONFIRM
)

# =============================
# استيراد الدوال المشتركة من flows/shared.py
# =============================
from .flows.shared import (
    # Translator functions
    render_translator_selection,
    ask_translator_name,
    show_translator_list,
    handle_translator_list_callback,
    handle_translator_choice,
    handle_translator_inline_selection,
    handle_translator_text,
    get_translator_state,
    
    # Summary and Confirm functions
    show_final_summary,
    show_review_screen,
    handle_final_confirm,
    get_confirm_state,
    
    # Save functions (مؤقتاً يستورد من الأصلي)
    save_report_to_database,
    
    # Edit functions (مؤقتاً يستورد من الأصلي)
    handle_edit_before_save,
)

# =============================
# استيراد handlers المسارات (flows) من الملف الأصلي مؤقتاً
# TODO: نقل هذه handlers إلى ملفات flows منفصلة بشكل كامل
# =============================

def _load_original_module():
    """تحميل الملف الأصلي للحصول على handlers المسارات"""
    current_file = os.path.abspath(__file__)
    current_dir = os.path.dirname(current_file)  # user_reports_add_new_system/
    parent_dir = os.path.dirname(current_dir)  # user/
    original_file = os.path.join(parent_dir, 'user_reports_add_new_system.py')
    
    # إذا لم يوجد في المجلد الأب، البحث في نفس المجلد
    if not os.path.exists(original_file):
        original_file_alt = os.path.join(current_dir, '..', 'user_reports_add_new_system.py')
        original_file_alt = os.path.normpath(original_file_alt)
        if os.path.exists(original_file_alt):
            original_file = original_file_alt
        else:
            logger.warning(f"⚠️ لم يتم العثور على الملف الأصلي في: {original_file} أو {original_file_alt}")
            logger.info("ℹ️ سيتم استخدام النسخة المقسمة فقط (قد تحتاج إلى إكمال handlers المسارات)")
            return None
    
    try:
        # إضافة workspace root (الذي يحتوي على bot/) إلى sys.path
        # current_dir = user_reports_add_new_system/
        # parent_dir = user/
        # handlers_dir = handlers/
        # bot_dir = bot/
        handlers_dir = os.path.dirname(parent_dir)  # handlers/
        bot_dir = os.path.dirname(handlers_dir)  # bot/
        workspace_root = os.path.dirname(bot_dir)  # workspace root (botuser@)
        
        if workspace_root not in sys.path:
            sys.path.insert(0, workspace_root)
        
        # استخدام اسم package صحيح للسماح بـ relative imports
        module_name = "bot.handlers.user.user_reports_add_new_system_original"
        spec = importlib.util.spec_from_file_location(module_name, original_file)
        module = importlib.util.module_from_spec(spec)
        
        # تعيين __package__ و __file__ للسماح بـ relative imports
        module.__package__ = "bot.handlers.user"
        module.__name__ = module_name
        module.__file__ = original_file
        
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        logger.error(f"❌ Error loading original module: {e}", exc_info=True)
        return None

_original_module = _load_original_module()

def register(app):
    """تسجيل ConversationHandler - يستخدم الملفات المقسمة للمراحل الأساسية وflows/shared.py للدوال المشتركة"""
    
    if not _original_module:
        logger.error("❌ فشل تحميل الملف الأصلي - سيتم استخدام register من الملف الأصلي مباشرة")
        # Fallback: استخدام الملف الأصلي مباشرة
        current_file = os.path.abspath(__file__)
        current_dir = os.path.dirname(current_file)
        parent_dir = os.path.dirname(current_dir)
        original_file = os.path.join(parent_dir, 'user_reports_add_new_system.py')
        if os.path.exists(original_file):
            spec = importlib.util.spec_from_file_location("user_reports_add_new_system_original_fallback", original_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.register(app)
        else:
            logger.error("❌ لم يتم العثور على الملف الأصلي كـ fallback")
            return
    
    # استيراد ensure_default_translators من flows/shared.py
    try:
        from .flows.shared import ensure_default_translators
        ensure_default_translators()
        logger.info("✅ تم استدعاء ensure_default_translators من flows/shared.py")
    except Exception as e:
        logger.warning(f"⚠️ فشل استيراد ensure_default_translators: {e}")
    
    # ✅ استخدام flows/shared.py للدوال المشتركة (translator, confirm, save, edit)
    # ✅ استخدام الملف الأصلي لـ ConversationHandler كاملاً (بما في ذلك inline query handlers)
    # TODO: نقل جميع handlers المسارات إلى ملفات flows منفصلة بشكل كامل
    
    logger.info("✅ استخدام الملفات المقسمة للمراحل الأساسية وflows/shared.py للدوال المشتركة")
    logger.info("✅ استخدام الملف الأصلي لـ ConversationHandler (بما في ذلك inline query handlers)")
    logger.warning("⚠️ TODO: نقل جميع handlers المسارات إلى ملفات flows منفصلة بشكل كامل")
    
    # استخدام الملف الأصلي مباشرة - سيستخدم inline query handlers الخاصة به
    return _original_module.register(app)
