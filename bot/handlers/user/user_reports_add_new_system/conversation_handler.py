# =============================
# conversation_handler.py
# Phase-A-Activation: Explicit Governed ConversationHandler Assembly
#
# This file owns orchestration authority.
# All handlers are imported by explicit name — no globals() dispatch, no closures.
# The _original_module delegation is retained as a recovery path only.
#
# ACTIVATION STATE: GOVERNED PATH ACTIVE
# Recovery path: set ORCHESTRATION_FALLBACK=1 env var to delegate to monolith.
# =============================

from telegram.ext import (
    ConversationHandler, MessageHandler, CallbackQueryHandler,
    CommandHandler, InlineQueryHandler, ChosenInlineResultHandler, filters,
)
from telegram.constants import ChatType
import logging
import os
import sys
import importlib.util

logger = logging.getLogger(__name__)

# =============================
# States — single authoritative import
# =============================

from .states import (
    STATE_SELECT_DATE, STATE_SELECT_DATE_TIME, STATE_SELECT_PATIENT,
    STATE_SELECT_HOSPITAL, STATE_SELECT_DEPARTMENT, STATE_SELECT_SUBDEPARTMENT,
    STATE_SELECT_DOCTOR, STATE_SELECT_ACTION_TYPE,
    R_ACTION_TYPE,
    R_DATE, R_DATE_TIME, R_PATIENT, R_HOSPITAL, R_DEPARTMENT, R_SUBDEPARTMENT, R_DOCTOR,
    NEW_CONSULT_COMPLAINT, NEW_CONSULT_DIAGNOSIS, NEW_CONSULT_DECISION,
    NEW_CONSULT_TESTS, NEW_CONSULT_FOLLOWUP_DATE, NEW_CONSULT_FOLLOWUP_TIME,
    NEW_CONSULT_FOLLOWUP_REASON, NEW_CONSULT_TRANSLATOR, NEW_CONSULT_CONFIRM,
    FOLLOWUP_COMPLAINT, FOLLOWUP_DIAGNOSIS, FOLLOWUP_DECISION, FOLLOWUP_ROOM_FLOOR,
    FOLLOWUP_DATE_TIME, FOLLOWUP_REASON, FOLLOWUP_TRANSLATOR, FOLLOWUP_CONFIRM,
    EMERGENCY_COMPLAINT, EMERGENCY_DIAGNOSIS, EMERGENCY_DECISION, EMERGENCY_STATUS,
    EMERGENCY_ADMISSION_NOTES, EMERGENCY_OPERATION_DETAILS,
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
    RADIATION_THERAPY_TYPE, RADIATION_THERAPY_SESSION_NUMBER, RADIATION_THERAPY_REMAINING,
    RADIATION_THERAPY_NOTES, RADIATION_THERAPY_RETURN_DATE, RADIATION_THERAPY_RETURN_REASON,
    RADIATION_THERAPY_TRANSLATOR, RADIATION_THERAPY_CONFIRM,
)

# =============================
# Monolith loader — recovery path only
# =============================

def _load_original_module():
    """تحميل الملف الأصلي للحصول على handlers المسارات"""
    current_file = os.path.abspath(__file__)
    current_dir = os.path.dirname(current_file)
    parent_dir = os.path.dirname(current_dir)
    original_file = os.path.join(parent_dir, 'user_reports_add_new_system.py')

    if not os.path.exists(original_file):
        original_file_alt = os.path.normpath(os.path.join(current_dir, '..', 'user_reports_add_new_system.py'))
        if os.path.exists(original_file_alt):
            original_file = original_file_alt
        else:
            logger.warning(f"⚠️ Original module not found at: {original_file}")
            return None

    try:
        handlers_dir = os.path.dirname(parent_dir)
        bot_dir = os.path.dirname(handlers_dir)
        workspace_root = os.path.dirname(bot_dir)

        if workspace_root not in sys.path:
            sys.path.insert(0, workspace_root)

        module_name = "bot.handlers.user.user_reports_add_new_system_original"
        spec = importlib.util.spec_from_file_location(module_name, original_file)
        module = importlib.util.module_from_spec(spec)
        module.__package__ = "bot.handlers.user"
        module.__name__ = module_name
        module.__file__ = original_file
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        logger.error(f"❌ Error loading original module: {e}", exc_info=True)
        return None

_original_module = _load_original_module()

# =============================
# Explicit handler imports — grouped by source
# =============================

# --- Date & Time (modular) ---
from .date_time_handlers import (
    start_report, render_date_selection, handle_date_choice,
    handle_main_calendar_nav, handle_main_calendar_day,
    handle_date_time_hour, handle_date_time_minute, handle_date_time_skip,
    handle_date_time_back_hour, handle_step_back_date,
)

# --- Patient (modular) ---
from .patient_handlers import (
    show_patient_selection, render_patient_selection,
    show_patient_list, handle_patient_list_callback,
    handle_patient_selection, handle_patient,
)

# --- Hospital (modular) ---
from .hospital_handlers import (
    render_hospital_selection, handle_hospital_selection,
    handle_hospital_page, handle_hospital_search, show_hospitals_menu,
)

# --- Department (modular) ---
from .department_handlers import (
    render_department_selection, handle_department_selection,
    handle_department_page, handle_department_search, show_departments_menu,
    show_subdepartment_options, handle_subdepartment_choice, handle_subdepartment_page,
)

# --- Doctor (modular) ---
from .doctor_handlers import (
    render_doctor_selection, show_doctor_input, handle_doctor_selection, handle_doctor,
)

# --- Action Type (modular) ---
from .action_type_handlers import (
    show_action_type_menu, handle_action_type_choice, handle_action_page,
    handle_noop, handle_stale_callback,
)

# --- Navigation (modular) ---
from .navigation_helpers import handle_cancel_navigation, handle_go_to_state

# --- flows/shared.py (translator, confirm, save, edit) ---
from .flows.shared import (
    render_translator_selection,
    ask_translator_name,
    show_translator_list,
    handle_translator_list_callback,
    handle_translator_choice,
    handle_translator_inline_selection,
    handle_translator_text,
    get_translator_state,
    show_final_summary,
    show_review_screen,
    handle_final_confirm,
    get_confirm_state,
    save_report_to_database,
    handle_edit_before_save,
)

# --- Edit router (modular) ---
_route_edit_field_selection = None
_route_edit_field_input = None
try:
    from .edit_handlers.before_publish.router import (
        route_edit_field_selection as _route_edit_field_selection,
        route_edit_field_input as _route_edit_field_input,
    )
except ImportError as e:
    logger.warning(f"⚠️ Cannot import edit routers: {e}")

# --- Global callback handlers (extracted from monolith register() in pre-condition 3) ---
from bot.handlers.user.user_reports_add_new_system_original import (
    handle_chosen_inline_result,
    handle_view_reschedule_callback,
)

# =============================
# Monolith handler imports — flow handlers (globals() dispatch replaced with explicit imports)
# These come from _original_module to preserve exact runtime identity during cutover.
# After each flow is migrated to its own file, replace the getattr() call with a direct import.
# =============================

def _m(name):
    """Resolve a handler from the monolith module. Returns None on failure (wired as no-op guard)."""
    if _original_module is None:
        logger.error(f"❌ _original_module is None — cannot resolve handler '{name}'")
        return None
    fn = getattr(_original_module, name, None)
    if fn is None:
        logger.error(f"❌ Handler '{name}' not found in monolith module")
    return fn

# Shared calendar/navigation handlers (monolith) — used across multiple flow states
def _monolith_shared():
    """Return a namespace dict of shared handlers from the monolith."""
    return {
        'handle_calendar_cancel':                    _m('handle_calendar_cancel'),
        'handle_smart_back_navigation':               _m('handle_smart_back_navigation'),
        'handle_smart_cancel_navigation':             _m('handle_smart_cancel_navigation'),
        'handle_new_consult_followup_calendar_nav':   _m('handle_new_consult_followup_calendar_nav'),
        'handle_new_consult_followup_calendar_day':   _m('handle_new_consult_followup_calendar_day'),
        'handle_new_consult_followup_date_skip':      _m('handle_new_consult_followup_date_skip'),
        'handle_new_consult_followup_time_hour':      _m('handle_new_consult_followup_time_hour'),
        'handle_new_consult_followup_time_minute':    _m('handle_new_consult_followup_time_minute'),
        'handle_new_consult_followup_time_skip':      _m('handle_new_consult_followup_time_skip'),
        'handle_followup_date_text_input':            _m('handle_followup_date_text_input'),
        'handle_save_callback':                       _m('handle_save_callback'),
        'handle_edit_draft_report':                   _m('handle_edit_draft_report'),
        'handle_edit_field_selection':                _m('handle_edit_field_selection'),
        'handle_finish_edit_draft':                   _m('handle_finish_edit_draft'),
        'handle_back_to_summary':                     _m('handle_back_to_summary'),
        'handle_edit_draft_field':                    _m('handle_edit_draft_field'),
        'handle_draft_edit_translator':               _m('handle_draft_edit_translator'),
        'handle_back_to_edit_fields':                 _m('handle_back_to_edit_fields'),
        'handle_draft_field_input':                   _m('handle_draft_field_input'),
        'handle_edit_field_input':                    _m('handle_edit_field_input'),
        'handle_draft_edit_calendar_nav':             _m('handle_draft_edit_calendar_nav'),
        'handle_draft_edit_calendar_day':             _m('handle_draft_edit_calendar_day'),
        'handle_draft_edit_cal_skip':                 _m('handle_draft_edit_cal_skip'),
        'handle_draft_edit_time_hour':                _m('handle_draft_edit_time_hour'),
        'handle_draft_edit_time_minute':              _m('handle_draft_edit_time_minute'),
        'handle_draft_edit_time_skip':                _m('handle_draft_edit_time_skip'),
        'handle_draft_edit_back_calendar':            _m('handle_draft_edit_back_calendar'),
        'handle_draft_edit_back_hour':                _m('handle_draft_edit_back_hour'),
        'handle_translator_page_navigation':          _m('handle_translator_page_navigation'),
        'handle_simple_translator_choice':            _m('handle_simple_translator_choice'),
        'handle_restart_from_start':                  _m('handle_restart_from_start'),
        'handle_restart_from_start_main_menu':        _m('handle_restart_from_start_main_menu'),
        'debug_all_callbacks':                        _m('debug_all_callbacks'),
        # patient fallback handlers (used in fallbacks list)
        'handle_patient_btn_selection':               _m('handle_patient_btn_selection'),
        'handle_patient_page':                        _m('handle_patient_page'),
        # app_reschedule handlers (not yet in dedicated flow file)
        'handle_app_reschedule_reason':               _m('handle_app_reschedule_reason'),
        'handle_app_reschedule_return_reason':        _m('handle_app_reschedule_return_reason'),
        'handle_reschedule_calendar_nav':             _m('handle_reschedule_calendar_nav'),
        'handle_reschedule_calendar_day':             _m('handle_reschedule_calendar_day'),
        # radiology handlers (not yet in dedicated flow file)
        'handle_radiology_type':                      _m('handle_radiology_type'),
        'handle_radiology_calendar_nav':              _m('handle_radiology_calendar_nav'),
        'handle_radiology_calendar_day':              _m('handle_radiology_calendar_day'),
    }


def _confirm_state_handlers(sh, route_sel, route_inp):
    """Return the standard handler list for any *_CONFIRM state."""
    return [
        CallbackQueryHandler(handle_final_confirm,                  pattern="^(save|publish|edit):"),
        CallbackQueryHandler(sh['handle_save_callback'],            pattern="^save:"),
        CallbackQueryHandler(sh['handle_edit_draft_report'],        pattern="^edit_draft:"),
        CallbackQueryHandler(sh['handle_edit_field_selection'],     pattern="^draft_field:"),
        CallbackQueryHandler(
            route_sel if route_sel else (lambda u, c: ConversationHandler.END),
            pattern="^edit_field:"
        ),
        CallbackQueryHandler(sh['handle_finish_edit_draft'],        pattern="^finish_edit_draft:"),
        CallbackQueryHandler(sh['handle_back_to_summary'],          pattern="^back_to_summary:"),
        CallbackQueryHandler(sh['handle_edit_draft_field'],         pattern="^edit_field_draft:"),
        CallbackQueryHandler(sh['handle_draft_edit_translator'],    pattern="^draft_edit_translator:"),
        CallbackQueryHandler(sh['handle_back_to_edit_fields'],      pattern="^back_to_edit_fields"),
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            route_inp if route_inp else sh['handle_draft_field_input'],
        ),
    ]


def _followup_date_state_handlers(sh):
    """Return handlers for any followup-date calendar state."""
    return [
        CallbackQueryHandler(sh['handle_new_consult_followup_calendar_nav'],  pattern="^followup_cal_(prev|next):"),
        CallbackQueryHandler(sh['handle_new_consult_followup_calendar_day'],  pattern="^followup_cal_day:"),
        CallbackQueryHandler(sh['handle_new_consult_followup_date_skip'],     pattern="^followup_date_skip"),
        CallbackQueryHandler(sh['handle_new_consult_followup_time_hour'],     pattern="^followup_time_hour:"),
        CallbackQueryHandler(sh['handle_new_consult_followup_time_minute'],   pattern="^followup_time_minute:"),
        CallbackQueryHandler(sh['handle_new_consult_followup_time_skip'],     pattern="^followup_time_skip"),
        MessageHandler(filters.TEXT & ~filters.COMMAND, sh['handle_followup_date_text_input']),
        CallbackQueryHandler(sh['handle_smart_back_navigation'],              pattern="^nav:back$"),
    ]


def _translator_state_handlers(sh):
    """Return handlers for any *_TRANSLATOR state (simple_translator: protocol)."""
    return [
        CallbackQueryHandler(sh['handle_translator_page_navigation'], pattern="^translator_page:"),
        CallbackQueryHandler(sh['handle_simple_translator_choice'],   pattern="^simple_translator:"),
    ]


def _radiation_handlers():
    """Import and return radiation_therapy flow handlers by name."""
    try:
        from bot.handlers.user.user_reports_add_new_system.flows.radiation_therapy import (
            handle_radiation_therapy_type,
            handle_radiation_therapy_session_number,
            handle_radiation_therapy_remaining,
            handle_radiation_therapy_notes,
            handle_radiation_therapy_return_date,
            handle_radiation_therapy_return_reason,
            handle_radiation_calendar_callback,
            handle_radiation_translator_callback,
        )
        return {
            'type':            handle_radiation_therapy_type,
            'session_number':  handle_radiation_therapy_session_number,
            'remaining':       handle_radiation_therapy_remaining,
            'notes':           handle_radiation_therapy_notes,
            'return_date':     handle_radiation_therapy_return_date,
            'return_reason':   handle_radiation_therapy_return_reason,
            'cal_callback':    handle_radiation_calendar_callback,
            'translator_cb':   handle_radiation_translator_callback,
        }
    except ImportError as e:
        logger.error(f"❌ Cannot import radiation_therapy handlers: {e}")
        return {}


# =============================
# Governed register()
# =============================

def _ensure_original():
    """تحميل الملف الأصلي للـ fallback"""
    global _original_module
    if _original_module is None:
        _original_module = _load_original_module()
    return _original_module


def register(app):
    """
    Governed ConversationHandler assembly.

    Orchestration authority is held here, not in the monolith.
    All handlers are resolved by explicit import or explicit getattr() from the
    monolith module (for flows not yet migrated to dedicated files).

    Recovery path: if ORCHESTRATION_FALLBACK env var is set to '1',
    delegation falls through to _original_module.register(app).
    """

    # --- Recovery path (retain for one deploy cycle after cutover) ---
    if os.environ.get("ORCHESTRATION_FALLBACK") == "1":
        logger.warning("⚠️ ORCHESTRATION_FALLBACK=1 — delegating to monolith register()")
        orig = _ensure_original()
        if orig:
            return orig.register(app)
        logger.error("❌ Fallback requested but monolith module unavailable")

    orig = _ensure_original()
    if orig is None:
        logger.error("❌ Monolith module unavailable — cannot resolve flow handlers")
        return

    # --- Resolve shared/monolith handlers ---
    sh = _monolith_shared()

    # --- Validate critical handlers are present ---
    critical = [
        'handle_calendar_cancel', 'handle_smart_back_navigation',
        'handle_final_confirm', 'handle_save_callback',
        'handle_restart_from_start', 'debug_all_callbacks',
    ]
    missing = [k for k in critical if not sh.get(k)]
    if missing:
        logger.error(f"❌ Missing critical handlers: {missing} — aborting governed register()")
        return orig.register(app)

    # --- Edit routers ---
    route_sel = _route_edit_field_selection
    route_inp = _route_edit_field_input

    # --- Radiation therapy handlers ---
    rad = _radiation_handlers()

    # --- Flow handlers from monolith (globals() dispatch replaced with explicit getattr) ---
    # new_consult
    nc_complaint           = _m('handle_new_consult_complaint')
    nc_diagnosis           = _m('handle_new_consult_diagnosis')
    nc_decision            = _m('handle_new_consult_decision')
    nc_tests               = _m('handle_new_consult_tests')
    nc_followup_cal_nav    = _m('handle_new_consult_followup_calendar_nav')
    nc_followup_cal_day    = _m('handle_new_consult_followup_calendar_day')
    nc_followup_date_skip  = _m('handle_new_consult_followup_date_skip')
    nc_followup_time_hour  = _m('handle_new_consult_followup_time_hour')
    nc_followup_time_skip  = _m('handle_new_consult_followup_time_skip')
    nc_followup_reason     = _m('handle_new_consult_followup_reason')

    # surgery_consult
    sc_diagnosis           = _m('handle_surgery_consult_diagnosis')
    sc_decision            = _m('handle_surgery_consult_decision')
    sc_name_en             = _m('handle_surgery_consult_name_en')
    sc_success_rate        = _m('handle_surgery_consult_success_rate')
    sc_benefit_rate        = _m('handle_surgery_consult_benefit_rate')
    sc_tests               = _m('handle_surgery_consult_tests')
    sc_followup_reason     = _m('handle_surgery_consult_followup_reason')

    # final_consult
    fc_diagnosis           = _m('handle_final_consult_diagnosis')
    fc_decision            = _m('handle_final_consult_decision')
    fc_recommendations     = _m('handle_final_consult_recommendations')

    # followup
    fu_complaint           = _m('handle_followup_complaint')
    fu_diagnosis           = _m('handle_followup_diagnosis')
    fu_decision            = _m('handle_followup_decision')
    fu_room_floor          = _m('handle_followup_room_floor')
    fu_reason              = _m('handle_followup_reason')

    # emergency
    em_complaint           = _m('handle_emergency_complaint')
    em_diagnosis           = _m('handle_emergency_diagnosis')
    em_decision            = _m('handle_emergency_decision')
    em_status_choice       = _m('handle_emergency_status_choice')
    em_status_text         = _m('handle_emergency_status_text')
    em_admission_notes     = _m('handle_emergency_admission_notes')
    em_operation_details   = _m('handle_emergency_operation_details')
    em_admission_type      = _m('handle_emergency_admission_type_choice')
    em_room_number         = _m('handle_emergency_room_number')
    em_date_time_text      = _m('handle_emergency_date_time_text')
    em_reason              = _m('handle_emergency_reason')

    # operation
    op_details_ar          = _m('handle_operation_details_ar')
    op_name_en             = _m('handle_operation_name_en')
    op_notes               = _m('handle_operation_notes')
    op_followup_reason     = _m('handle_operation_followup_reason')

    # rehab
    re_rehab_type          = _m('handle_rehab_type')
    re_pt_details          = _m('handle_physical_therapy_details')
    re_pt_followup_reason  = _m('handle_physical_therapy_followup_reason')
    re_device_details      = _m('handle_device_name_details')
    re_device_followup_reason = _m('handle_device_followup_reason')

    # admission
    ad_reason              = _m('handle_admission_reason')
    ad_room                = _m('handle_admission_room')
    ad_notes               = _m('handle_admission_notes')
    ad_followup_reason     = _m('handle_admission_followup_reason')

    # discharge
    di_type                = _m('handle_discharge_type')
    di_admission_summary   = _m('handle_discharge_admission_summary')
    di_operation_details   = _m('handle_discharge_operation_details')
    di_operation_name_en   = _m('handle_discharge_operation_name_en')
    di_followup_reason     = _m('handle_discharge_followup_reason')

    # Validate that no critical flow handler is None
    flow_handlers = {
        'nc_complaint': nc_complaint, 'nc_diagnosis': nc_diagnosis,
        'fu_complaint': fu_complaint, 'em_complaint': em_complaint,
        'di_type': di_type, 'ad_reason': ad_reason,
        'sc_diagnosis': sc_diagnosis, 'fc_diagnosis': fc_diagnosis,
        'op_details_ar': op_details_ar, 're_rehab_type': re_rehab_type,
    }
    missing_flows = [k for k, v in flow_handlers.items() if v is None]
    if missing_flows:
        logger.error(f"❌ Missing flow handlers: {missing_flows} — falling back to monolith register()")
        return orig.register(app)

    # =============================
    # Global non-ConversationHandler registrations
    # =============================

    app.add_handler(ChosenInlineResultHandler(handle_chosen_inline_result))

    try:
        app.add_handler(CallbackQueryHandler(handle_view_reschedule_callback, pattern="^view_reschedule:"))
    except Exception:
        pass

    try:
        from .flows.shared import ensure_default_translators
        ensure_default_translators()
    except Exception as e:
        logger.warning(f"⚠️ ensure_default_translators failed: {e}")

    # =============================
    # ConversationHandler — exact topology mirror of monolith register()
    # =============================

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_report, pattern="^start_report$"),
            CallbackQueryHandler(start_report, pattern="^user_action:add_report$"),
            CallbackQueryHandler(start_report, pattern="^add_report$"),
            MessageHandler(filters.Regex(r"^📝\s*إضافة\s*تقرير\s*جديد\s*$"), start_report),
            MessageHandler(filters.Regex(r"^📝\s*إضافة تقرير جديد\s*$"), start_report),
            MessageHandler(filters.Regex(r"^📝 إضافة تقرير جديد$"), start_report),
            MessageHandler(filters.Regex(r"إضافة تقرير جديد"), start_report),
            MessageHandler(filters.TEXT & filters.Regex(r"📝.*إضافة.*تقرير.*جديد"), start_report),
        ],
        states={
            # ── DATE ──────────────────────────────────────────────────────────
            STATE_SELECT_DATE: [
                CallbackQueryHandler(sh['handle_calendar_cancel'],      pattern="^nav:cancel$"),
                CallbackQueryHandler(handle_date_choice,                pattern="^(date:|nav:)"),
                CallbackQueryHandler(handle_main_calendar_nav,          pattern="^main_cal_(prev|next):"),
                CallbackQueryHandler(handle_main_calendar_day,          pattern="^main_cal_day:"),
            ],
            R_DATE: [
                CallbackQueryHandler(sh['handle_calendar_cancel'],      pattern="^nav:cancel$"),
                CallbackQueryHandler(handle_date_choice,                pattern="^(date:|nav:)"),
                CallbackQueryHandler(handle_main_calendar_nav,          pattern="^main_cal_(prev|next):"),
                CallbackQueryHandler(handle_main_calendar_day,          pattern="^main_cal_day:"),
            ],
            R_DATE_TIME: [
                CallbackQueryHandler(handle_date_time_hour,             pattern="^time_hour:"),
                CallbackQueryHandler(handle_date_time_minute,           pattern="^time_minute:"),
                CallbackQueryHandler(handle_date_time_skip,             pattern="^time_skip"),
                CallbackQueryHandler(sh['handle_calendar_cancel'],      pattern="^nav:cancel$"),
            ],
            # ── PATIENT ───────────────────────────────────────────────────────
            STATE_SELECT_PATIENT: [
                CallbackQueryHandler(sh['handle_calendar_cancel'],      pattern="^nav:cancel$"),
                CallbackQueryHandler(handle_patient_selection,          pattern="^patient_idx:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_patient),
            ],
            R_PATIENT: [
                CallbackQueryHandler(sh['handle_calendar_cancel'],      pattern="^nav:cancel$"),
                CallbackQueryHandler(handle_patient_selection,          pattern="^patient_idx:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_patient),
            ],
            # ── HOSPITAL ──────────────────────────────────────────────────────
            STATE_SELECT_HOSPITAL: [
                CallbackQueryHandler(sh['handle_calendar_cancel'],      pattern="^nav:cancel$"),
                CallbackQueryHandler(handle_hospital_selection,         pattern="^hospital_idx:"),
                CallbackQueryHandler(handle_hospital_page,              pattern="^(hospital_page|hosp_page):"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_hospital_search),
            ],
            # ── DEPARTMENT ────────────────────────────────────────────────────
            STATE_SELECT_DEPARTMENT: [
                CallbackQueryHandler(sh['handle_calendar_cancel'],      pattern="^nav:cancel$"),
                CallbackQueryHandler(handle_department_selection,       pattern="^dept_idx:"),
                CallbackQueryHandler(handle_department_page,            pattern="^dept_page:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_department_search),
            ],
            R_DEPARTMENT: [
                CallbackQueryHandler(sh['handle_calendar_cancel'],      pattern="^nav:cancel$"),
                CallbackQueryHandler(handle_department_selection,       pattern="^dept_idx:"),
                CallbackQueryHandler(handle_department_page,            pattern="^dept_page:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_department_search),
            ],
            R_SUBDEPARTMENT: [
                CallbackQueryHandler(sh['handle_calendar_cancel'],      pattern="^nav:cancel$"),
                CallbackQueryHandler(handle_subdepartment_choice,       pattern="^subdept(?:_idx)?:"),
                CallbackQueryHandler(handle_subdepartment_page,         pattern="^subdept_page:"),
            ],
            # ── DOCTOR ────────────────────────────────────────────────────────
            STATE_SELECT_DOCTOR: [
                CallbackQueryHandler(sh['handle_calendar_cancel'],      pattern="^nav:cancel$"),
                CallbackQueryHandler(_m('handle_doctor_btn_selection'), pattern="^doctor_idx:"),
                CallbackQueryHandler(_m('handle_doctor_page'),          pattern="^doctor_page:"),
                CallbackQueryHandler(handle_doctor_selection,           pattern="^doctor_manual$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_doctor),
            ],
            R_DOCTOR: [
                CallbackQueryHandler(sh['handle_calendar_cancel'],      pattern="^nav:cancel$"),
                CallbackQueryHandler(_m('handle_doctor_btn_selection'), pattern="^doctor_idx:"),
                CallbackQueryHandler(_m('handle_doctor_page'),          pattern="^doctor_page:"),
                CallbackQueryHandler(handle_doctor_selection,           pattern="^doctor_manual$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_doctor),
            ],
            # ── ACTION TYPE ───────────────────────────────────────────────────
            R_ACTION_TYPE: [
                CallbackQueryHandler(sh['handle_calendar_cancel'],      pattern="^nav:cancel$"),
                CallbackQueryHandler(handle_action_type_choice,         pattern="^action_idx:"),
                CallbackQueryHandler(handle_noop,                       pattern="^noop$"),
                CallbackQueryHandler(handle_stale_callback,
                    pattern="^(hosp_page|hospital_page|dept_page|department_page|subdept_page|subdepartment_page|doctor_idx|hospital_idx|dept_idx|subdept|subdept_idx):"),
            ],
            STATE_SELECT_ACTION_TYPE: [
                CallbackQueryHandler(sh['handle_calendar_cancel'],      pattern="^nav:cancel$"),
                CallbackQueryHandler(handle_action_type_choice,         pattern="^action_idx:"),
                CallbackQueryHandler(handle_noop,                       pattern="^noop$"),
                CallbackQueryHandler(handle_stale_callback,
                    pattern="^(hosp_page|hospital_page|dept_page|department_page|subdept_page|subdepartment_page|doctor_idx|hospital_idx|dept_idx|subdept|subdept_idx):"),
            ],
            # ── NEW CONSULT ───────────────────────────────────────────────────
            NEW_CONSULT_COMPLAINT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, nc_complaint),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            NEW_CONSULT_DIAGNOSIS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, nc_diagnosis),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            NEW_CONSULT_DECISION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, nc_decision),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            NEW_CONSULT_TESTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, nc_tests),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            NEW_CONSULT_FOLLOWUP_DATE: [
                CallbackQueryHandler(nc_followup_cal_nav,               pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(nc_followup_cal_day,               pattern="^followup_cal_day:"),
                CallbackQueryHandler(nc_followup_date_skip,             pattern="^followup_date_skip"),
                CallbackQueryHandler(sh['handle_calendar_cancel'],      pattern="^nav:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sh['handle_followup_date_text_input']),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            NEW_CONSULT_FOLLOWUP_TIME: [
                CallbackQueryHandler(nc_followup_time_hour,             pattern="^followup_time_hour:"),
                CallbackQueryHandler(nc_followup_time_skip,             pattern="^followup_time_skip"),
                CallbackQueryHandler(sh['handle_calendar_cancel'],      pattern="^nav:cancel$"),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            NEW_CONSULT_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, nc_followup_reason),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            NEW_CONSULT_TRANSLATOR: _translator_state_handlers(sh),
            NEW_CONSULT_CONFIRM:    _confirm_state_handlers(sh, route_sel, route_inp),
            # ── EDIT DRAFT (string-keyed) ─────────────────────────────────────
            "EDIT_DRAFT_FIELD": [
                CallbackQueryHandler(sh['handle_back_to_edit_fields'],  pattern="^back_to_edit_fields"),
                CallbackQueryHandler(sh['handle_back_to_summary'],      pattern="^back_to_summary:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sh['handle_draft_field_input']),
            ],
            "EDIT_DRAFT_FOLLOWUP_CALENDAR": [
                CallbackQueryHandler(sh['handle_draft_edit_calendar_nav'],  pattern="^draft_edit_cal_nav:"),
                CallbackQueryHandler(sh['handle_draft_edit_calendar_day'],  pattern="^draft_edit_cal_day:"),
                CallbackQueryHandler(sh['handle_draft_edit_cal_skip'],      pattern="^draft_edit_cal_skip$"),
                CallbackQueryHandler(sh['handle_draft_edit_time_hour'],     pattern="^draft_edit_time_hour:"),
                CallbackQueryHandler(sh['handle_draft_edit_time_minute'],   pattern="^draft_edit_time_minute:"),
                CallbackQueryHandler(sh['handle_draft_edit_time_skip'],     pattern="^draft_edit_time_skip$"),
                CallbackQueryHandler(sh['handle_draft_edit_back_calendar'], pattern="^draft_edit_back_calendar$"),
                CallbackQueryHandler(sh['handle_draft_edit_back_hour'],     pattern="^draft_edit_back_hour$"),
                CallbackQueryHandler(sh['handle_back_to_edit_fields'],      pattern="^back_to_edit_fields"),
            ],
            "EDIT_DRAFT_TRANSLATOR": [
                CallbackQueryHandler(sh['handle_draft_edit_translator'],    pattern="^draft_edit_translator:"),
                CallbackQueryHandler(sh['handle_back_to_edit_fields'],      pattern="^back_to_edit_fields"),
            ],
            # ── SURGERY CONSULT ───────────────────────────────────────────────
            SURGERY_CONSULT_DIAGNOSIS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sc_diagnosis),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            SURGERY_CONSULT_DECISION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sc_decision),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            SURGERY_CONSULT_NAME_EN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sc_name_en),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            SURGERY_CONSULT_SUCCESS_RATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sc_success_rate),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            SURGERY_CONSULT_BENEFIT_RATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sc_benefit_rate),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            SURGERY_CONSULT_TESTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sc_tests),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            SURGERY_CONSULT_FOLLOWUP_DATE: [
                CallbackQueryHandler(sh['handle_new_consult_followup_calendar_nav'], pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(sh['handle_new_consult_followup_calendar_day'], pattern="^followup_cal_day:"),
                CallbackQueryHandler(sh['handle_new_consult_followup_date_skip'],    pattern="^followup_date_skip"),
                CallbackQueryHandler(sh['handle_new_consult_followup_time_hour'],    pattern="^followup_time_hour:"),
                CallbackQueryHandler(sh['handle_new_consult_followup_time_skip'],    pattern="^followup_time_skip"),
                CallbackQueryHandler(sh['handle_calendar_cancel'],                   pattern="^nav:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sh['handle_followup_date_text_input']),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],             pattern="^nav:back$"),
            ],
            SURGERY_CONSULT_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sc_followup_reason),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            SURGERY_CONSULT_TRANSLATOR: _translator_state_handlers(sh),
            SURGERY_CONSULT_CONFIRM:    _confirm_state_handlers(sh, route_sel, route_inp),
            # ── FINAL CONSULT ─────────────────────────────────────────────────
            FINAL_CONSULT_DIAGNOSIS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, fc_diagnosis),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            FINAL_CONSULT_DECISION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, fc_decision),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            FINAL_CONSULT_RECOMMENDATIONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, fc_recommendations),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            FINAL_CONSULT_TRANSLATOR: _translator_state_handlers(sh),
            FINAL_CONSULT_CONFIRM:    _confirm_state_handlers(sh, route_sel, route_inp),
            # ── FOLLOWUP ──────────────────────────────────────────────────────
            FOLLOWUP_COMPLAINT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, fu_complaint),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            FOLLOWUP_DIAGNOSIS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, fu_diagnosis),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            FOLLOWUP_DECISION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, fu_decision),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            FOLLOWUP_ROOM_FLOOR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, fu_room_floor),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            FOLLOWUP_DATE_TIME: _followup_date_state_handlers(sh),
            FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, fu_reason),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            FOLLOWUP_TRANSLATOR: _translator_state_handlers(sh),
            FOLLOWUP_CONFIRM:    _confirm_state_handlers(sh, route_sel, route_inp),
            # ── EMERGENCY ─────────────────────────────────────────────────────
            EMERGENCY_COMPLAINT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, em_complaint),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            EMERGENCY_DIAGNOSIS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, em_diagnosis),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            EMERGENCY_DECISION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, em_decision),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            EMERGENCY_STATUS: [
                CallbackQueryHandler(em_status_choice,                   pattern="^emerg_status:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, em_status_text),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            EMERGENCY_ADMISSION_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, em_admission_notes),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            EMERGENCY_OPERATION_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, em_operation_details),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            EMERGENCY_ADMISSION_TYPE: [
                CallbackQueryHandler(em_admission_type,                  pattern="^emerg_admission:"),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            EMERGENCY_ROOM_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, em_room_number),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            EMERGENCY_DATE_TIME: [
                CallbackQueryHandler(sh['handle_new_consult_followup_calendar_nav'], pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(sh['handle_new_consult_followup_calendar_day'], pattern="^followup_cal_day:"),
                CallbackQueryHandler(sh['handle_new_consult_followup_date_skip'],    pattern="^followup_date_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sh['handle_followup_date_text_input']),
                CallbackQueryHandler(sh['handle_new_consult_followup_time_hour'],    pattern="^followup_time_hour:"),
                CallbackQueryHandler(sh['handle_new_consult_followup_time_skip'],    pattern="^followup_time_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, em_date_time_text),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],             pattern="^nav:back$"),
            ],
            EMERGENCY_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, em_reason),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            EMERGENCY_TRANSLATOR: _translator_state_handlers(sh),
            EMERGENCY_CONFIRM:    _confirm_state_handlers(sh, route_sel, route_inp),
            # ── OPERATION ─────────────────────────────────────────────────────
            OPERATION_DETAILS_AR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, op_details_ar),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            OPERATION_NAME_EN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, op_name_en),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            OPERATION_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, op_notes),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            OPERATION_FOLLOWUP_DATE: [
                CallbackQueryHandler(sh['handle_new_consult_followup_calendar_nav'], pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(sh['handle_new_consult_followup_calendar_day'], pattern="^followup_cal_day:"),
                CallbackQueryHandler(sh['handle_new_consult_followup_date_skip'],    pattern="^followup_date_skip"),
                CallbackQueryHandler(sh['handle_new_consult_followup_time_hour'],    pattern="^followup_time_hour:"),
                CallbackQueryHandler(sh['handle_new_consult_followup_time_skip'],    pattern="^followup_time_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sh['handle_followup_date_text_input']),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],             pattern="^nav:back$"),
            ],
            OPERATION_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, op_followup_reason),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            OPERATION_TRANSLATOR: _translator_state_handlers(sh),
            OPERATION_CONFIRM:    _confirm_state_handlers(sh, route_sel, route_inp),
            # ── REHAB ─────────────────────────────────────────────────────────
            REHAB_TYPE: [
                CallbackQueryHandler(re_rehab_type,                      pattern="^rehab_type:"),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            PHYSICAL_THERAPY_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, re_pt_details),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            PHYSICAL_THERAPY_FOLLOWUP_DATE: [
                CallbackQueryHandler(sh['handle_new_consult_followup_calendar_nav'],  pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(sh['handle_new_consult_followup_calendar_day'],  pattern="^followup_cal_day:"),
                CallbackQueryHandler(sh['handle_new_consult_followup_date_skip'],     pattern="^followup_date_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sh['handle_followup_date_text_input']),
                CallbackQueryHandler(sh['handle_new_consult_followup_time_hour'],     pattern="^followup_time_hour:"),
                CallbackQueryHandler(sh['handle_new_consult_followup_time_minute'],   pattern="^followup_time_minute:"),
                CallbackQueryHandler(sh['handle_new_consult_followup_time_skip'],     pattern="^followup_time_skip"),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],              pattern="^nav:back$"),
            ],
            PHYSICAL_THERAPY_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, re_pt_followup_reason),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            PHYSICAL_THERAPY_TRANSLATOR: _translator_state_handlers(sh),
            PHYSICAL_THERAPY_CONFIRM:    _confirm_state_handlers(sh, route_sel, route_inp),
            DEVICE_NAME_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, re_device_details),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            DEVICE_FOLLOWUP_DATE: [
                CallbackQueryHandler(sh['handle_new_consult_followup_calendar_nav'],  pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(sh['handle_new_consult_followup_calendar_day'],  pattern="^followup_cal_day:"),
                CallbackQueryHandler(sh['handle_new_consult_followup_date_skip'],     pattern="^followup_date_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sh['handle_followup_date_text_input']),
                CallbackQueryHandler(sh['handle_new_consult_followup_time_hour'],     pattern="^followup_time_hour:"),
                CallbackQueryHandler(sh['handle_new_consult_followup_time_skip'],     pattern="^followup_time_skip"),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],              pattern="^nav:back$"),
            ],
            DEVICE_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, re_device_followup_reason),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            DEVICE_TRANSLATOR: _translator_state_handlers(sh),
            DEVICE_CONFIRM:    _confirm_state_handlers(sh, route_sel, route_inp),
            # ── RADIOLOGY ─────────────────────────────────────────────────────
            RADIOLOGY_TYPE: [
                CallbackQueryHandler(sh['handle_smart_back_navigation'],   pattern="^nav:back$"),
                CallbackQueryHandler(sh['handle_smart_cancel_navigation'], pattern="^nav:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sh['handle_radiology_type']),
            ],
            RADIOLOGY_DELIVERY_DATE: [
                CallbackQueryHandler(sh['handle_smart_back_navigation'],   pattern="^nav:back$"),
                CallbackQueryHandler(sh['handle_smart_cancel_navigation'], pattern="^nav:cancel$"),
                CallbackQueryHandler(sh['handle_radiology_calendar_nav'],  pattern="^radiology_cal_(prev|next):"),
                CallbackQueryHandler(sh['handle_radiology_calendar_day'],  pattern="^radiology_cal_day:"),
            ],
            RADIOLOGY_TRANSLATOR: [
                CallbackQueryHandler(sh['handle_smart_back_navigation'],   pattern="^nav:back$"),
                CallbackQueryHandler(sh['handle_smart_cancel_navigation'], pattern="^nav:cancel$"),
                CallbackQueryHandler(sh['handle_simple_translator_choice'], pattern="^simple_translator:"),
            ],
            RADIOLOGY_CONFIRM: _confirm_state_handlers(sh, route_sel, route_inp),
            # ── ADMISSION ─────────────────────────────────────────────────────
            ADMISSION_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ad_reason),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            ADMISSION_ROOM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ad_room),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            ADMISSION_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ad_notes),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            ADMISSION_FOLLOWUP_DATE: _followup_date_state_handlers(sh),
            ADMISSION_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ad_followup_reason),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            ADMISSION_TRANSLATOR: _translator_state_handlers(sh),
            ADMISSION_CONFIRM:    _confirm_state_handlers(sh, route_sel, route_inp),
            # ── DISCHARGE ─────────────────────────────────────────────────────
            DISCHARGE_TYPE: [
                CallbackQueryHandler(di_type,                            pattern="^discharge_type:"),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            DISCHARGE_ADMISSION_SUMMARY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, di_admission_summary),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            DISCHARGE_OPERATION_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, di_operation_details),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            DISCHARGE_OPERATION_NAME_EN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, di_operation_name_en),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            DISCHARGE_FOLLOWUP_DATE: _followup_date_state_handlers(sh),
            DISCHARGE_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, di_followup_reason),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            DISCHARGE_TRANSLATOR: _translator_state_handlers(sh),
            DISCHARGE_CONFIRM:    _confirm_state_handlers(sh, route_sel, route_inp),
            # ── APP RESCHEDULE ────────────────────────────────────────────────
            APP_RESCHEDULE_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sh['handle_app_reschedule_reason']),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            APP_RESCHEDULE_RETURN_DATE: [
                CallbackQueryHandler(sh['handle_reschedule_calendar_nav'],           pattern="^reschedule_cal_nav:"),
                CallbackQueryHandler(sh['handle_reschedule_calendar_day'],           pattern="^reschedule_cal_day:"),
                CallbackQueryHandler(sh['handle_new_consult_followup_time_hour'],    pattern="^followup_time_hour:"),
                CallbackQueryHandler(sh['handle_new_consult_followup_time_minute'],  pattern="^followup_time_minute:"),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],             pattern="^nav:back$"),
                CallbackQueryHandler(handle_cancel_navigation,                       pattern="^nav:cancel$"),
            ],
            APP_RESCHEDULE_RETURN_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sh['handle_app_reschedule_return_reason']),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            APP_RESCHEDULE_TRANSLATOR: _translator_state_handlers(sh),
            APP_RESCHEDULE_CONFIRM:    _confirm_state_handlers(sh, route_sel, route_inp),
            # ── RADIATION THERAPY ─────────────────────────────────────────────
            RADIATION_THERAPY_TYPE: [
                CallbackQueryHandler(sh['handle_smart_back_navigation'],   pattern="^nav:back$"),
                CallbackQueryHandler(sh['handle_smart_cancel_navigation'], pattern="^nav:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, rad.get('type')),
            ],
            RADIATION_THERAPY_SESSION_NUMBER: [
                CallbackQueryHandler(sh['handle_smart_back_navigation'],   pattern="^nav:back$"),
                CallbackQueryHandler(sh['handle_smart_cancel_navigation'], pattern="^nav:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, rad.get('session_number')),
            ],
            RADIATION_THERAPY_REMAINING: [
                CallbackQueryHandler(sh['handle_smart_back_navigation'],   pattern="^nav:back$"),
                CallbackQueryHandler(sh['handle_smart_cancel_navigation'], pattern="^nav:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, rad.get('remaining')),
            ],
            RADIATION_THERAPY_NOTES: [
                CallbackQueryHandler(sh['handle_smart_back_navigation'],   pattern="^nav:back$"),
                CallbackQueryHandler(sh['handle_smart_cancel_navigation'], pattern="^nav:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, rad.get('notes')),
            ],
            RADIATION_THERAPY_RETURN_DATE: [
                CallbackQueryHandler(sh['handle_smart_back_navigation'],   pattern="^nav:back$"),
                CallbackQueryHandler(sh['handle_smart_cancel_navigation'], pattern="^nav:cancel$"),
                CallbackQueryHandler(rad.get('cal_callback'),              pattern="^rad_cal_"),
                CallbackQueryHandler(rad.get('cal_callback'),              pattern="^rad_time_"),
                CallbackQueryHandler(handle_noop,                          pattern="^noop$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, rad.get('return_date')),
            ],
            RADIATION_THERAPY_RETURN_REASON: [
                CallbackQueryHandler(sh['handle_smart_back_navigation'],   pattern="^nav:back$"),
                CallbackQueryHandler(sh['handle_smart_cancel_navigation'], pattern="^nav:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, rad.get('return_reason')),
            ],
            RADIATION_THERAPY_TRANSLATOR: [
                CallbackQueryHandler(sh['handle_smart_back_navigation'],   pattern="^nav:back$"),
                CallbackQueryHandler(sh['handle_smart_cancel_navigation'], pattern="^nav:cancel$"),
                CallbackQueryHandler(rad.get('translator_cb'),             pattern="^rad_translator"),
                CallbackQueryHandler(handle_noop,                          pattern="^noop$"),
            ],
            RADIATION_THERAPY_CONFIRM: _confirm_state_handlers(sh, route_sel, route_inp),
            # ── EDIT_FIELD (generic) ───────────────────────────────────────────
            "EDIT_FIELD": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sh['handle_edit_field_input']),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(sh['handle_patient_btn_selection'],          pattern="^patient_idx:"),
            CallbackQueryHandler(sh['handle_patient_page'],                   pattern="^user_patient_page:"),
            CallbackQueryHandler(handle_hospital_page,                        pattern="^hosp_page:"),
            CallbackQueryHandler(handle_hospital_selection,                   pattern="^select_hospital:"),
            CallbackQueryHandler(handle_cancel_navigation,                    pattern="^nav:cancel$"),
            CommandHandler("cancel", handle_cancel_navigation),
            CommandHandler("start", sh['handle_restart_from_start']),
            MessageHandler(filters.Regex(r"^/start$"),                        sh['handle_restart_from_start']),
            MessageHandler(filters.Regex(r"^🚀\s*(ابدأ( الآن)?|أبدا استخدام النظام)\s*$"), sh['handle_restart_from_start']),
            CallbackQueryHandler(sh['handle_restart_from_start_main_menu'],   pattern="^start_main_menu$"),
            MessageHandler(filters.TEXT & filters.Regex(r".*إضافة.*تقرير.*جديد.*"), start_report),
            CallbackQueryHandler(sh['handle_smart_back_navigation'],          pattern="^nav:back$"),
            CallbackQueryHandler(sh['debug_all_callbacks'],                   pattern=".*"),
        ],
        per_message=False,
        per_chat=True,
        per_user=True,
        allow_reentry=True,
    )

    app.add_handler(conv_handler)
    logger.info("✅ Governed ConversationHandler registered — orchestration authority is conversation_handler.py")
