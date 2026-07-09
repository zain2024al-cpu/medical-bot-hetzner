# =============================
# conversation_handler.py
# Governed ConversationHandler Assembly
#
# This file owns orchestration authority.
# All handlers are imported by explicit name — no globals() dispatch, no closures.
# =============================

from telegram.ext import (
    ConversationHandler, MessageHandler, CallbackQueryHandler,
    CommandHandler, InlineQueryHandler, ChosenInlineResultHandler, filters,
)
from telegram.constants import ChatType
import logging

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
# Explicit handler imports — grouped by source
# =============================

# --- Date & Time (modular) ---
from .date_time_handlers import (
    start_report, render_date_selection, handle_date_choice,
    handle_main_calendar_nav, handle_main_calendar_day,
    handle_date_time_hour, handle_date_time_skip,
    handle_step_back_date,
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
    handle_medical_report_choice,
    handle_medical_report_image,
    handle_medical_report_image_done,
    handle_medical_report_no_reason,
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
from .patient_handlers import handle_chosen_inline_result
from .flows.app_reschedule import handle_view_reschedule_callback

# =============================
# Navigation stack helpers
# =============================

_MAX_NAV_DEPTH = 25


def _nav_push_state(context, state):
    """Push state onto the back-navigation stack."""
    history = context.user_data.setdefault('_nav_stack', [])
    if state is None or (history and history[-1] == state):
        return

    if len(history) >= 2 and history[-2] == state:
        removed = history.pop()
        logger.debug(f"NAV_COLLAPSE: removed={removed} depth={len(history)}")
        return

    history.append(state)
    if len(history) > _MAX_NAV_DEPTH:
        del history[:len(history) - _MAX_NAV_DEPTH]
    logger.debug(f"NAV_PUSH: {state} depth={len(history)}")


def _nav_pop_state(context):
    """Pop and return the top of the back-navigation stack."""
    history = context.user_data.get('_nav_stack', [])
    if history:
        state = history.pop()
        logger.debug(f"NAV_POP: {state} -> stack={history}")
        return state
    return None


def _nav_clear(context):
    """Clear the back-navigation stack."""
    context.user_data['_nav_stack'] = []


def _tracked(handler_fn, current_state):
    """
    Wrap a flow handler so that the PTB state the user was IN is pushed onto the
    navigation stack before the handler runs.  Back navigation pops from this stack
    to know exactly which step to return to — no flow-map lookups, no stale
    _conversation_state reads.

    current_state: the ConversationHandler state integer this handler is registered under.
    """
    if handler_fn is None:
        return None

    import functools

    @functools.wraps(handler_fn)
    async def _wrapper(update, context):
        _nav_push_state(context, current_state)
        return await handler_fn(update, context)

    return _wrapper


# ── Package-resident handlers ─────────────────────────────────────────────────
from .edit_handlers.draft.handlers import (
    handle_edit_draft_report,
    handle_edit_draft_field,
    handle_draft_field_input,
    handle_finish_edit_draft,
    handle_back_to_summary,
    handle_back_to_edit_fields,
    handle_draft_edit_translator,
    handle_draft_edit_calendar_nav,
    handle_draft_edit_calendar_day,
    handle_draft_edit_cal_skip,
    handle_draft_edit_time_hour,
    handle_draft_edit_time_minute,
    handle_draft_edit_time_skip,
    handle_draft_edit_back_calendar,
    handle_draft_edit_back_hour,
)
from .flows.shared import handle_simple_translator_choice, handle_translator_page_navigation
from .navigation_helpers import (
    handle_cancel_navigation as handle_smart_cancel_navigation,
    handle_smart_back_navigation,
)
from .date_time_handlers import handle_calendar_cancel, handle_followup_date_text_input
from .edit_handlers.draft.handlers import (
    handle_save_callback,
    handle_edit_field_selection,
    handle_edit_field_input,
    debug_all_callbacks,
)
from .action_type_handlers import handle_restart_from_start, handle_restart_from_start_main_menu
from .patient_handlers import handle_patient_btn_selection, handle_patient_page
from .flows.app_reschedule import (
    handle_app_reschedule_reason,
    handle_app_reschedule_return_reason,
    handle_reschedule_calendar_nav,
    handle_reschedule_calendar_day,
)
from .flows.radiology import (
    handle_radiology_type,
    handle_radiology_calendar_nav,
    handle_radiology_calendar_day,
)



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


def _followup_date_state_handlers(sh, state=None):
    """Return handlers for any followup-date calendar state. Pass state to enable nav-stack tracking."""
    return [
        CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_calendar_nav'], state) if state else sh['handle_new_consult_followup_calendar_nav'],  pattern="^followup_cal_(prev|next):"),
        CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_calendar_day'], state) if state else sh['handle_new_consult_followup_calendar_day'],  pattern="^followup_cal_day:"),
        CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_date_skip'], state) if state else sh['handle_new_consult_followup_date_skip'],        pattern="^followup_date_skip"),
        CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_time_hour'], state) if state else sh['handle_new_consult_followup_time_hour'],        pattern="^followup_time_hour:"),
        CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_time_minute'], state) if state else sh['handle_new_consult_followup_time_minute'],    pattern="^followup_time_minute:"),
        CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_time_skip'], state) if state else sh['handle_new_consult_followup_time_skip'],        pattern="^followup_time_skip"),
        MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(sh['handle_followup_date_text_input'], state) if state else sh['handle_followup_date_text_input']),
        CallbackQueryHandler(sh['handle_smart_back_navigation'],                                                                                             pattern="^nav:back$"),
    ]


def _translator_state_handlers(sh, state=None):
    """Return handlers for any *_TRANSLATOR state (simple_translator: protocol)."""
    return [
        CallbackQueryHandler(_tracked(sh['handle_translator_page_navigation'], state) if state else sh['handle_translator_page_navigation'], pattern="^translator_page:"),
        CallbackQueryHandler(_tracked(sh['handle_simple_translator_choice'], state) if state else sh['handle_simple_translator_choice'],     pattern="^simple_translator:"),
        CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
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
        )
        return {
            'type':            handle_radiation_therapy_type,
            'session_number':  handle_radiation_therapy_session_number,
            'remaining':       handle_radiation_therapy_remaining,
            'notes':           handle_radiation_therapy_notes,
            'return_date':     handle_radiation_therapy_return_date,
            'return_reason':   handle_radiation_therapy_return_reason,
            'cal_callback':    handle_radiation_calendar_callback,
        }
    except ImportError as e:
        logger.error(f"❌ Cannot import radiation_therapy handlers: {e}")
        return {}


# =============================
# Governed register()
# =============================

def register(app):
    """Governed ConversationHandler assembly. All handlers resolved by explicit import."""

    # --- Shared handler dict ---
    sh = {
        'handle_calendar_cancel':                    handle_calendar_cancel,
        'handle_smart_back_navigation':              handle_smart_back_navigation,
        'handle_followup_date_text_input':           handle_followup_date_text_input,
        'handle_save_callback':                      handle_save_callback,
        'handle_edit_field_selection':               handle_edit_field_selection,
        'handle_edit_field_input':                   handle_edit_field_input,
        'handle_translator_page_navigation':         handle_translator_page_navigation,
        'handle_restart_from_start':                 handle_restart_from_start,
        'handle_restart_from_start_main_menu':       handle_restart_from_start_main_menu,
        'debug_all_callbacks':                       debug_all_callbacks,
        'handle_patient_btn_selection':              handle_patient_btn_selection,
        'handle_patient_page':                       handle_patient_page,
        'handle_smart_cancel_navigation':            handle_smart_cancel_navigation,
        'handle_edit_draft_report':                  handle_edit_draft_report,
        'handle_edit_draft_field':                   handle_edit_draft_field,
        'handle_draft_field_input':                  handle_draft_field_input,
        'handle_finish_edit_draft':                  handle_finish_edit_draft,
        'handle_back_to_summary':                    handle_back_to_summary,
        'handle_back_to_edit_fields':                handle_back_to_edit_fields,
        'handle_draft_edit_translator':              handle_draft_edit_translator,
        'handle_draft_edit_calendar_nav':            handle_draft_edit_calendar_nav,
        'handle_draft_edit_calendar_day':            handle_draft_edit_calendar_day,
        'handle_draft_edit_cal_skip':                handle_draft_edit_cal_skip,
        'handle_draft_edit_time_hour':               handle_draft_edit_time_hour,
        'handle_draft_edit_time_minute':             handle_draft_edit_time_minute,
        'handle_draft_edit_time_skip':               handle_draft_edit_time_skip,
        'handle_draft_edit_back_calendar':           handle_draft_edit_back_calendar,
        'handle_draft_edit_back_hour':               handle_draft_edit_back_hour,
        'handle_simple_translator_choice':           handle_simple_translator_choice,
        'handle_app_reschedule_reason':              handle_app_reschedule_reason,
        'handle_app_reschedule_return_reason':       handle_app_reschedule_return_reason,
        'handle_reschedule_calendar_nav':            handle_reschedule_calendar_nav,
        'handle_reschedule_calendar_day':            handle_reschedule_calendar_day,
        'handle_radiology_type':                     handle_radiology_type,
        'handle_radiology_calendar_nav':             handle_radiology_calendar_nav,
        'handle_radiology_calendar_day':             handle_radiology_calendar_day,
    }

    # Patch new_consult followup calendar/time handlers into sh for _followup_date_state_handlers
    from .flows.new_consult import (
        handle_new_consult_followup_calendar_nav,
        handle_new_consult_followup_calendar_day,
        handle_new_consult_followup_date_skip,
        handle_new_consult_followup_time_hour,
        handle_new_consult_followup_time_minute,
        handle_new_consult_followup_time_skip,
    )
    sh['handle_new_consult_followup_calendar_nav'] = handle_new_consult_followup_calendar_nav
    sh['handle_new_consult_followup_calendar_day'] = handle_new_consult_followup_calendar_day
    sh['handle_new_consult_followup_date_skip']    = handle_new_consult_followup_date_skip
    sh['handle_new_consult_followup_time_hour']    = handle_new_consult_followup_time_hour
    sh['handle_new_consult_followup_time_minute']  = handle_new_consult_followup_time_minute
    sh['handle_new_consult_followup_time_skip']    = handle_new_consult_followup_time_skip

    # --- Edit routers ---
    route_sel = _route_edit_field_selection
    route_inp = _route_edit_field_input

    # --- Radiation therapy handlers ---
    rad = _radiation_handlers()

    # --- Flow handlers — direct imports from package (no monolith dependency) ---
    from .flows.new_consult import (
        handle_new_consult_complaint        as nc_complaint,
        handle_new_consult_diagnosis        as nc_diagnosis,
        handle_new_consult_decision         as nc_decision,
        handle_new_consult_tests            as nc_tests,
        handle_new_consult_followup_calendar_nav  as nc_followup_cal_nav,
        handle_new_consult_followup_calendar_day  as nc_followup_cal_day,
        handle_new_consult_followup_date_skip     as nc_followup_date_skip,
        handle_new_consult_followup_time_hour     as nc_followup_time_hour,
        handle_new_consult_followup_time_minute   as nc_followup_time_minute,
        handle_new_consult_followup_time_skip     as nc_followup_time_skip,
        handle_new_consult_followup_reason  as nc_followup_reason,
    )
    from .flows.surgery_consult import (
        handle_surgery_consult_diagnosis    as sc_diagnosis,
        handle_surgery_consult_decision     as sc_decision,
        handle_surgery_consult_name_en      as sc_name_en,
        handle_surgery_consult_success_rate as sc_success_rate,
        handle_surgery_consult_benefit_rate as sc_benefit_rate,
        handle_surgery_consult_tests        as sc_tests,
        handle_surgery_consult_followup_reason as sc_followup_reason,
    )
    from .flows.final_consult import (
        handle_final_consult_diagnosis      as fc_diagnosis,
        handle_final_consult_decision       as fc_decision,
        handle_final_consult_recommendations as fc_recommendations,
    )
    from .flows.followup import (
        handle_followup_complaint           as fu_complaint,
        handle_followup_diagnosis           as fu_diagnosis,
        handle_followup_decision            as fu_decision,
        handle_followup_room_floor          as fu_room_floor,
        handle_followup_reason              as fu_reason,
    )
    from .flows.emergency import (
        handle_emergency_complaint          as em_complaint,
        handle_emergency_diagnosis          as em_diagnosis,
        handle_emergency_decision           as em_decision,
        handle_emergency_status_choice      as em_status_choice,
        handle_emergency_status_text        as em_status_text,
        handle_emergency_admission_notes    as em_admission_notes,
        handle_emergency_operation_details  as em_operation_details,
        handle_emergency_admission_type_choice as em_admission_type,
        handle_emergency_room_number        as em_room_number,
        handle_emergency_date_time_text     as em_date_time_text,
        handle_emergency_reason             as em_reason,
    )
    from .flows.operation import (
        handle_operation_details_ar         as op_details_ar,
        handle_operation_name_en            as op_name_en,
        handle_operation_notes              as op_notes,
        handle_operation_followup_reason    as op_followup_reason,
    )
    from .flows.rehab import (
        handle_rehab_type                   as re_rehab_type,
        handle_physical_therapy_details     as re_pt_details,
        handle_physical_therapy_followup_reason as re_pt_followup_reason,
        handle_device_name_details          as re_device_details,
        handle_device_followup_reason       as re_device_followup_reason,
    )
    from .flows.admission import (
        handle_admission_reason             as ad_reason,
        handle_admission_room               as ad_room,
        handle_admission_notes              as ad_notes,
        handle_admission_followup_reason    as ad_followup_reason,
    )
    from .flows.discharge import (
        handle_discharge_type               as di_type,
        handle_discharge_admission_summary  as di_admission_summary,
        handle_discharge_operation_details  as di_operation_details,
        handle_discharge_operation_name_en  as di_operation_name_en,
        handle_discharge_followup_reason    as di_followup_reason,
    )

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
        logger.error(f"❌ Missing flow handlers: {missing_flows} — cannot register conversation handler")

    # =============================
    # Global non-ConversationHandler registrations
    # =============================

    app.add_handler(ChosenInlineResultHandler(handle_chosen_inline_result))

    try:
        app.add_handler(CallbackQueryHandler(handle_view_reschedule_callback, pattern="^view_reschedule:"))
    except Exception:
        pass

    try:
        from bot.handlers.shared.medical_files_access import handle_medical_files_callback
        app.add_handler(CallbackQueryHandler(handle_medical_files_callback, pattern="^medfiles:"))
    except Exception as e:
        logger.warning(f"⚠️ Cannot register medical_files_access handler: {e}")

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
            MessageHandler(filters.TEXT & filters.Regex(r"إضافة\s*تقرير\s*جديد"), start_report),
        ],
        states={
            # ── DATE ──────────────────────────────────────────────────────────
            STATE_SELECT_DATE: [
                CallbackQueryHandler(sh['handle_calendar_cancel'],                                    pattern="^nav:cancel$"),
                CallbackQueryHandler(_tracked(handle_date_choice, STATE_SELECT_DATE),                 pattern="^nav:back$"),
                CallbackQueryHandler(_tracked(handle_date_choice, STATE_SELECT_DATE),                 pattern="^(date:|nav:)"),
                CallbackQueryHandler(_tracked(handle_main_calendar_nav, STATE_SELECT_DATE),           pattern="^main_cal_(prev|next):"),
                CallbackQueryHandler(_tracked(handle_main_calendar_day, STATE_SELECT_DATE),           pattern="^main_cal_day:"),
            ],
            R_DATE: [
                CallbackQueryHandler(sh['handle_calendar_cancel'],                  pattern="^nav:cancel$"),
                CallbackQueryHandler(_tracked(handle_date_choice, R_DATE),           pattern="^(date:|nav:)"),
                CallbackQueryHandler(_tracked(handle_main_calendar_nav, R_DATE),     pattern="^main_cal_(prev|next):"),
                CallbackQueryHandler(_tracked(handle_main_calendar_day, R_DATE),     pattern="^main_cal_day:"),
            ],
            R_DATE_TIME: [
                CallbackQueryHandler(_tracked(handle_date_time_hour, R_DATE_TIME),   pattern="^time_hour:"),
                CallbackQueryHandler(_tracked(handle_date_time_skip, R_DATE_TIME),   pattern="^time_skip"),
                CallbackQueryHandler(sh['handle_calendar_cancel'],                   pattern="^nav:cancel$"),
            ],
            # ── PATIENT ───────────────────────────────────────────────────────
            STATE_SELECT_PATIENT: [
                CallbackQueryHandler(sh['handle_calendar_cancel'],                                        pattern="^nav:cancel$"),
                CallbackQueryHandler(_tracked(handle_patient_list_callback, STATE_SELECT_PATIENT),        pattern="^patient:show_list:"),
                CallbackQueryHandler(_tracked(handle_patient_list_callback, STATE_SELECT_PATIENT),        pattern="^patient:back_to_menu$"),
                CallbackQueryHandler(_tracked(handle_patient_selection, STATE_SELECT_PATIENT),            pattern="^patient_idx:"),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                                  pattern="^go_to_date_selection$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(handle_patient, STATE_SELECT_PATIENT)),
            ],
            R_PATIENT: [
                CallbackQueryHandler(sh['handle_calendar_cancel'],                               pattern="^nav:cancel$"),
                CallbackQueryHandler(_tracked(handle_patient_list_callback, R_PATIENT),          pattern="^patient:show_list:"),
                CallbackQueryHandler(_tracked(handle_patient_list_callback, R_PATIENT),          pattern="^patient:back_to_menu$"),
                CallbackQueryHandler(_tracked(handle_patient_selection, R_PATIENT),              pattern="^patient_idx:"),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                         pattern="^go_to_date_selection$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(handle_patient, R_PATIENT)),
            ],
            # ── HOSPITAL ──────────────────────────────────────────────────────
            STATE_SELECT_HOSPITAL: [
                CallbackQueryHandler(sh['handle_calendar_cancel'],                                          pattern="^nav:cancel$"),
                CallbackQueryHandler(_tracked(handle_hospital_selection, STATE_SELECT_HOSPITAL),            pattern="^hospital_idx:"),
                CallbackQueryHandler(_tracked(handle_hospital_page, STATE_SELECT_HOSPITAL),                 pattern="^(hospital_page|hosp_page):"),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                                    pattern="^go_to_patient_selection$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(handle_hospital_search, STATE_SELECT_HOSPITAL)),
            ],
            # ── DEPARTMENT ────────────────────────────────────────────────────
            STATE_SELECT_DEPARTMENT: [
                CallbackQueryHandler(sh['handle_calendar_cancel'],                                              pattern="^nav:cancel$"),
                CallbackQueryHandler(_tracked(handle_department_selection, STATE_SELECT_DEPARTMENT),            pattern="^dept_idx:"),
                CallbackQueryHandler(_tracked(handle_department_page, STATE_SELECT_DEPARTMENT),                 pattern="^dept_page:"),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                                        pattern="^go_to_hospital_selection$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(handle_department_search, STATE_SELECT_DEPARTMENT)),
            ],
            R_DEPARTMENT: [
                CallbackQueryHandler(sh['handle_calendar_cancel'],                                  pattern="^nav:cancel$"),
                CallbackQueryHandler(_tracked(handle_department_selection, R_DEPARTMENT),           pattern="^dept_idx:"),
                CallbackQueryHandler(_tracked(handle_department_page, R_DEPARTMENT),                pattern="^dept_page:"),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                            pattern="^go_to_hospital_selection$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(handle_department_search, R_DEPARTMENT)),
            ],
            R_SUBDEPARTMENT: [
                CallbackQueryHandler(sh['handle_calendar_cancel'],                                  pattern="^nav:cancel$"),
                CallbackQueryHandler(_tracked(handle_subdepartment_choice, R_SUBDEPARTMENT),        pattern="^subdept(?:_idx)?:"),
                CallbackQueryHandler(_tracked(handle_subdepartment_page, R_SUBDEPARTMENT),          pattern="^subdept_page:"),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                            pattern="^go_to_department_selection$"),
            ],
            # ── DOCTOR ────────────────────────────────────────────────────────
            STATE_SELECT_DOCTOR: [
                CallbackQueryHandler(sh['handle_calendar_cancel'],                                     pattern="^nav:cancel$"),
                CallbackQueryHandler(_tracked(handle_doctor_selection, STATE_SELECT_DOCTOR),           pattern="^doctor_idx:"),
                CallbackQueryHandler(_tracked(handle_doctor_selection, STATE_SELECT_DOCTOR),           pattern="^doctor_manual$"),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                               pattern="^go_to_department_selection$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(handle_doctor, STATE_SELECT_DOCTOR)),
            ],
            R_DOCTOR: [
                CallbackQueryHandler(sh['handle_calendar_cancel'],                         pattern="^nav:cancel$"),
                CallbackQueryHandler(_tracked(handle_doctor_selection, R_DOCTOR),          pattern="^doctor_idx:"),
                CallbackQueryHandler(_tracked(handle_doctor_selection, R_DOCTOR),          pattern="^doctor_manual$"),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                   pattern="^go_to_department_selection$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(handle_doctor, R_DOCTOR)),
            ],
            # ── ACTION TYPE / NEW CONSULT COMPLAINT (all share integer 7) ───────
            # R_ACTION_TYPE == STATE_SELECT_ACTION_TYPE == NEW_CONSULT_COMPLAINT == 7.
            # PTB merges duplicate integer keys — only the LAST wins.
            # We define ONE combined entry that handles all callbacks valid in state 7:
            # action-type menu callbacks + new_consult first step + back navigation.
            R_ACTION_TYPE: [
                CallbackQueryHandler(sh['handle_calendar_cancel'],                              pattern="^nav:cancel$"),
                CallbackQueryHandler(_tracked(handle_action_type_choice, R_ACTION_TYPE),        pattern="^action_idx:"),
                CallbackQueryHandler(handle_noop,                                               pattern="^noop$"),
                CallbackQueryHandler(_tracked(handle_go_to_state, R_ACTION_TYPE),              pattern="^go_to_search_doctor_screen$"),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                        pattern="^nav:back$"),
                CallbackQueryHandler(handle_stale_callback,
                    pattern="^(hosp_page|hospital_page|dept_page|department_page|subdept_page|subdepartment_page|doctor_idx|hospital_idx|dept_idx|subdept|subdept_idx):"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(nc_complaint, R_ACTION_TYPE)),
            ],
            # ── NEW CONSULT ───────────────────────────────────────────────────
            NEW_CONSULT_DIAGNOSIS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(nc_diagnosis, NEW_CONSULT_DIAGNOSIS)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            NEW_CONSULT_DECISION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(nc_decision, NEW_CONSULT_DECISION)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            NEW_CONSULT_TESTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(nc_tests, NEW_CONSULT_TESTS)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            NEW_CONSULT_FOLLOWUP_DATE: [
                CallbackQueryHandler(_tracked(nc_followup_cal_nav, NEW_CONSULT_FOLLOWUP_DATE),   pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(_tracked(nc_followup_cal_day, NEW_CONSULT_FOLLOWUP_DATE),   pattern="^followup_cal_day:"),
                CallbackQueryHandler(_tracked(nc_followup_date_skip, NEW_CONSULT_FOLLOWUP_DATE), pattern="^followup_date_skip"),
                CallbackQueryHandler(sh['handle_calendar_cancel'],                               pattern="^nav:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(sh['handle_followup_date_text_input'], NEW_CONSULT_FOLLOWUP_DATE)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                         pattern="^nav:back$"),
            ],
            NEW_CONSULT_FOLLOWUP_TIME: [
                CallbackQueryHandler(_tracked(nc_followup_time_hour, NEW_CONSULT_FOLLOWUP_TIME), pattern="^followup_time_hour:"),
                CallbackQueryHandler(_tracked(nc_followup_time_skip, NEW_CONSULT_FOLLOWUP_TIME), pattern="^followup_time_skip"),
                CallbackQueryHandler(sh['handle_calendar_cancel'],                               pattern="^nav:cancel$"),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                         pattern="^nav:back$"),
            ],
            NEW_CONSULT_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(nc_followup_reason, NEW_CONSULT_FOLLOWUP_REASON)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            NEW_CONSULT_TRANSLATOR: _translator_state_handlers(sh, NEW_CONSULT_TRANSLATOR),
            NEW_CONSULT_CONFIRM:    _confirm_state_handlers(sh, route_sel, route_inp),
            # ── MEDICAL REPORT GATE (string-keyed, shared across all flows) ───
            "MEDICAL_REPORT_ASK": [
                CallbackQueryHandler(handle_medical_report_choice,          pattern="^medrep:(yes|no|pending)$"),
                CallbackQueryHandler(handle_cancel_navigation,              pattern="^nav:cancel$"),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],    pattern="^nav:back$"),
            ],
            "MEDICAL_REPORT_IMAGE": [
                CallbackQueryHandler(handle_medical_report_image_done,      pattern="^medrep_done:yes$"),
                CallbackQueryHandler(handle_cancel_navigation,              pattern="^nav:cancel$"),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],    pattern="^nav:back$"),
                MessageHandler(filters.PHOTO,                               handle_medical_report_image),
                MessageHandler(filters.Document.ALL,                        handle_medical_report_image),
                MessageHandler(filters.VIDEO,                               handle_medical_report_image),
                MessageHandler(filters.AUDIO,                               handle_medical_report_image),
                MessageHandler(filters.VOICE,                               handle_medical_report_image),
                MessageHandler(filters.TEXT & ~filters.COMMAND,            handle_medical_report_image),
            ],
            "MEDICAL_REPORT_NO_REASON": [
                CallbackQueryHandler(handle_cancel_navigation,              pattern="^nav:cancel$"),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],    pattern="^nav:back$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND,            handle_medical_report_no_reason),
            ],
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
                CallbackQueryHandler(sh['handle_back_to_summary'],          pattern="^back_to_summary:"),
            ],
            # ── SURGERY CONSULT ───────────────────────────────────────────────
            SURGERY_CONSULT_DIAGNOSIS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(sc_diagnosis, SURGERY_CONSULT_DIAGNOSIS)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            SURGERY_CONSULT_DECISION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(sc_decision, SURGERY_CONSULT_DECISION)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            SURGERY_CONSULT_NAME_EN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(sc_name_en, SURGERY_CONSULT_NAME_EN)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            SURGERY_CONSULT_SUCCESS_RATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(sc_success_rate, SURGERY_CONSULT_SUCCESS_RATE)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            SURGERY_CONSULT_BENEFIT_RATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(sc_benefit_rate, SURGERY_CONSULT_BENEFIT_RATE)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            SURGERY_CONSULT_TESTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(sc_tests, SURGERY_CONSULT_TESTS)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            SURGERY_CONSULT_FOLLOWUP_DATE: [
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_calendar_nav'], SURGERY_CONSULT_FOLLOWUP_DATE), pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_calendar_day'], SURGERY_CONSULT_FOLLOWUP_DATE), pattern="^followup_cal_day:"),
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_date_skip'], SURGERY_CONSULT_FOLLOWUP_DATE),    pattern="^followup_date_skip"),
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_time_hour'], SURGERY_CONSULT_FOLLOWUP_DATE),    pattern="^followup_time_hour:"),
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_time_skip'], SURGERY_CONSULT_FOLLOWUP_DATE),    pattern="^followup_time_skip"),
                CallbackQueryHandler(sh['handle_calendar_cancel'],                                                             pattern="^nav:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(sh['handle_followup_date_text_input'], SURGERY_CONSULT_FOLLOWUP_DATE)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                                                       pattern="^nav:back$"),
            ],
            SURGERY_CONSULT_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(sc_followup_reason, SURGERY_CONSULT_FOLLOWUP_REASON)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            SURGERY_CONSULT_TRANSLATOR: _translator_state_handlers(sh, SURGERY_CONSULT_TRANSLATOR),
            SURGERY_CONSULT_CONFIRM:    _confirm_state_handlers(sh, route_sel, route_inp),
            # ── FINAL CONSULT ─────────────────────────────────────────────────
            FINAL_CONSULT_DIAGNOSIS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(fc_diagnosis, FINAL_CONSULT_DIAGNOSIS)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            FINAL_CONSULT_DECISION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(fc_decision, FINAL_CONSULT_DECISION)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            FINAL_CONSULT_RECOMMENDATIONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(fc_recommendations, FINAL_CONSULT_RECOMMENDATIONS)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            FINAL_CONSULT_TRANSLATOR: _translator_state_handlers(sh, FINAL_CONSULT_TRANSLATOR),
            FINAL_CONSULT_CONFIRM:    _confirm_state_handlers(sh, route_sel, route_inp),
            # ── FOLLOWUP ──────────────────────────────────────────────────────
            FOLLOWUP_COMPLAINT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(fu_complaint, FOLLOWUP_COMPLAINT)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            FOLLOWUP_DIAGNOSIS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(fu_diagnosis, FOLLOWUP_DIAGNOSIS)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            FOLLOWUP_DECISION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(fu_decision, FOLLOWUP_DECISION)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            FOLLOWUP_ROOM_FLOOR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(fu_room_floor, FOLLOWUP_ROOM_FLOOR)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            FOLLOWUP_DATE_TIME: _followup_date_state_handlers(sh, FOLLOWUP_DATE_TIME),
            FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(fu_reason, FOLLOWUP_REASON)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            FOLLOWUP_TRANSLATOR: _translator_state_handlers(sh, FOLLOWUP_TRANSLATOR),
            FOLLOWUP_CONFIRM:    _confirm_state_handlers(sh, route_sel, route_inp),
            # ── EMERGENCY ─────────────────────────────────────────────────────
            EMERGENCY_COMPLAINT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(em_complaint, EMERGENCY_COMPLAINT)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            EMERGENCY_DIAGNOSIS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(em_diagnosis, EMERGENCY_DIAGNOSIS)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            EMERGENCY_DECISION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(em_decision, EMERGENCY_DECISION)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            EMERGENCY_STATUS: [
                CallbackQueryHandler(_tracked(em_status_choice, EMERGENCY_STATUS),   pattern="^emerg_status:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(em_status_text, EMERGENCY_STATUS)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],              pattern="^nav:back$"),
            ],
            EMERGENCY_ADMISSION_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(em_admission_notes, EMERGENCY_ADMISSION_NOTES)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            EMERGENCY_OPERATION_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(em_operation_details, EMERGENCY_OPERATION_DETAILS)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            EMERGENCY_ADMISSION_TYPE: [
                CallbackQueryHandler(_tracked(em_admission_type, EMERGENCY_ADMISSION_TYPE), pattern="^emerg_admission:"),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                     pattern="^nav:back$"),
            ],
            EMERGENCY_ROOM_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(em_room_number, EMERGENCY_ROOM_NUMBER)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            EMERGENCY_DATE_TIME: [
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_calendar_nav'], EMERGENCY_DATE_TIME), pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_calendar_day'], EMERGENCY_DATE_TIME), pattern="^followup_cal_day:"),
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_date_skip'], EMERGENCY_DATE_TIME),    pattern="^followup_date_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(sh['handle_followup_date_text_input'], EMERGENCY_DATE_TIME)),
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_time_hour'], EMERGENCY_DATE_TIME),    pattern="^followup_time_hour:"),
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_time_skip'], EMERGENCY_DATE_TIME),    pattern="^followup_time_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(em_date_time_text, EMERGENCY_DATE_TIME)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                                            pattern="^nav:back$"),
            ],
            EMERGENCY_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(em_reason, EMERGENCY_REASON)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            EMERGENCY_TRANSLATOR: _translator_state_handlers(sh, EMERGENCY_TRANSLATOR),
            EMERGENCY_CONFIRM:    _confirm_state_handlers(sh, route_sel, route_inp),
            # ── OPERATION ─────────────────────────────────────────────────────
            OPERATION_DETAILS_AR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(op_details_ar, OPERATION_DETAILS_AR)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            OPERATION_NAME_EN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(op_name_en, OPERATION_NAME_EN)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            OPERATION_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(op_notes, OPERATION_NOTES)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            OPERATION_FOLLOWUP_DATE: [
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_calendar_nav'], OPERATION_FOLLOWUP_DATE), pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_calendar_day'], OPERATION_FOLLOWUP_DATE), pattern="^followup_cal_day:"),
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_date_skip'], OPERATION_FOLLOWUP_DATE),    pattern="^followup_date_skip"),
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_time_hour'], OPERATION_FOLLOWUP_DATE),    pattern="^followup_time_hour:"),
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_time_skip'], OPERATION_FOLLOWUP_DATE),    pattern="^followup_time_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(sh['handle_followup_date_text_input'], OPERATION_FOLLOWUP_DATE)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                                                pattern="^nav:back$"),
            ],
            OPERATION_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(op_followup_reason, OPERATION_FOLLOWUP_REASON)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            OPERATION_TRANSLATOR: _translator_state_handlers(sh, OPERATION_TRANSLATOR),
            OPERATION_CONFIRM:    _confirm_state_handlers(sh, route_sel, route_inp),
            # ── REHAB ─────────────────────────────────────────────────────────
            REHAB_TYPE: [
                CallbackQueryHandler(_tracked(re_rehab_type, REHAB_TYPE),            pattern="^rehab_type:"),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],             pattern="^nav:back$"),
            ],
            PHYSICAL_THERAPY_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(re_pt_details, PHYSICAL_THERAPY_DETAILS)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            PHYSICAL_THERAPY_FOLLOWUP_DATE: [
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_calendar_nav'], PHYSICAL_THERAPY_FOLLOWUP_DATE),  pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_calendar_day'], PHYSICAL_THERAPY_FOLLOWUP_DATE),  pattern="^followup_cal_day:"),
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_date_skip'], PHYSICAL_THERAPY_FOLLOWUP_DATE),     pattern="^followup_date_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(sh['handle_followup_date_text_input'], PHYSICAL_THERAPY_FOLLOWUP_DATE)),
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_time_hour'], PHYSICAL_THERAPY_FOLLOWUP_DATE),     pattern="^followup_time_hour:"),
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_time_minute'], PHYSICAL_THERAPY_FOLLOWUP_DATE),   pattern="^followup_time_minute:"),
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_time_skip'], PHYSICAL_THERAPY_FOLLOWUP_DATE),     pattern="^followup_time_skip"),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                                                        pattern="^nav:back$"),
            ],
            PHYSICAL_THERAPY_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(re_pt_followup_reason, PHYSICAL_THERAPY_FOLLOWUP_REASON)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            PHYSICAL_THERAPY_TRANSLATOR: _translator_state_handlers(sh, PHYSICAL_THERAPY_TRANSLATOR),
            PHYSICAL_THERAPY_CONFIRM:    _confirm_state_handlers(sh, route_sel, route_inp),
            DEVICE_NAME_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(re_device_details, DEVICE_NAME_DETAILS)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            DEVICE_FOLLOWUP_DATE: [
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_calendar_nav'], DEVICE_FOLLOWUP_DATE),  pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_calendar_day'], DEVICE_FOLLOWUP_DATE),  pattern="^followup_cal_day:"),
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_date_skip'], DEVICE_FOLLOWUP_DATE),     pattern="^followup_date_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(sh['handle_followup_date_text_input'], DEVICE_FOLLOWUP_DATE)),
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_time_hour'], DEVICE_FOLLOWUP_DATE),     pattern="^followup_time_hour:"),
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_time_skip'], DEVICE_FOLLOWUP_DATE),     pattern="^followup_time_skip"),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                                              pattern="^nav:back$"),
            ],
            DEVICE_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(re_device_followup_reason, DEVICE_FOLLOWUP_REASON)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            DEVICE_TRANSLATOR: _translator_state_handlers(sh, DEVICE_TRANSLATOR),
            DEVICE_CONFIRM:    _confirm_state_handlers(sh, route_sel, route_inp),
            # ── RADIOLOGY ─────────────────────────────────────────────────────
            RADIOLOGY_TYPE: [
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                           pattern="^nav:back$"),
                CallbackQueryHandler(sh['handle_smart_cancel_navigation'],                         pattern="^nav:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(sh['handle_radiology_type'], RADIOLOGY_TYPE)),
            ],
            RADIOLOGY_DELIVERY_DATE: [
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                                           pattern="^nav:back$"),
                CallbackQueryHandler(sh['handle_smart_cancel_navigation'],                                         pattern="^nav:cancel$"),
                CallbackQueryHandler(_tracked(sh['handle_radiology_calendar_nav'], RADIOLOGY_DELIVERY_DATE),      pattern="^radiology_cal_(prev|next):"),
                CallbackQueryHandler(_tracked(sh['handle_radiology_calendar_day'], RADIOLOGY_DELIVERY_DATE),      pattern="^radiology_cal_day:"),
            ],
            RADIOLOGY_TRANSLATOR: [
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                                        pattern="^nav:back$"),
                CallbackQueryHandler(sh['handle_smart_cancel_navigation'],                                      pattern="^nav:cancel$"),
                CallbackQueryHandler(_tracked(sh['handle_simple_translator_choice'], RADIOLOGY_TRANSLATOR),    pattern="^simple_translator:"),
            ],
            RADIOLOGY_CONFIRM: _confirm_state_handlers(sh, route_sel, route_inp),
            # ── ADMISSION ─────────────────────────────────────────────────────
            ADMISSION_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(ad_reason, ADMISSION_REASON)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            ADMISSION_ROOM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(ad_room, ADMISSION_ROOM)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            ADMISSION_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(ad_notes, ADMISSION_NOTES)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            ADMISSION_FOLLOWUP_DATE: _followup_date_state_handlers(sh, ADMISSION_FOLLOWUP_DATE),
            ADMISSION_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(ad_followup_reason, ADMISSION_FOLLOWUP_REASON)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            ADMISSION_TRANSLATOR: _translator_state_handlers(sh, ADMISSION_TRANSLATOR),
            ADMISSION_CONFIRM:    _confirm_state_handlers(sh, route_sel, route_inp),
            # ── DISCHARGE ─────────────────────────────────────────────────────
            DISCHARGE_TYPE: [
                CallbackQueryHandler(_tracked(di_type, DISCHARGE_TYPE),              pattern="^discharge_type:"),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],             pattern="^nav:back$"),
            ],
            DISCHARGE_ADMISSION_SUMMARY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(di_admission_summary, DISCHARGE_ADMISSION_SUMMARY)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            DISCHARGE_OPERATION_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(di_operation_details, DISCHARGE_OPERATION_DETAILS)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            DISCHARGE_OPERATION_NAME_EN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(di_operation_name_en, DISCHARGE_OPERATION_NAME_EN)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            DISCHARGE_FOLLOWUP_DATE: _followup_date_state_handlers(sh, DISCHARGE_FOLLOWUP_DATE),
            DISCHARGE_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(di_followup_reason, DISCHARGE_FOLLOWUP_REASON)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            DISCHARGE_TRANSLATOR: _translator_state_handlers(sh, DISCHARGE_TRANSLATOR),
            DISCHARGE_CONFIRM:    _confirm_state_handlers(sh, route_sel, route_inp),
            # ── APP RESCHEDULE ────────────────────────────────────────────────
            APP_RESCHEDULE_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(sh['handle_app_reschedule_reason'], APP_RESCHEDULE_REASON)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            APP_RESCHEDULE_RETURN_DATE: [
                CallbackQueryHandler(_tracked(sh['handle_reschedule_calendar_nav'], APP_RESCHEDULE_RETURN_DATE),          pattern="^reschedule_cal_nav:"),
                CallbackQueryHandler(_tracked(sh['handle_reschedule_calendar_day'], APP_RESCHEDULE_RETURN_DATE),          pattern="^reschedule_cal_day:"),
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_time_hour'], APP_RESCHEDULE_RETURN_DATE),   pattern="^followup_time_hour:"),
                CallbackQueryHandler(_tracked(sh['handle_new_consult_followup_time_minute'], APP_RESCHEDULE_RETURN_DATE), pattern="^followup_time_minute:"),
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                                                  pattern="^nav:back$"),
                CallbackQueryHandler(handle_cancel_navigation,                                                            pattern="^nav:cancel$"),
            ],
            APP_RESCHEDULE_RETURN_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(sh['handle_app_reschedule_return_reason'], APP_RESCHEDULE_RETURN_REASON)),
                CallbackQueryHandler(sh['handle_smart_back_navigation'], pattern="^nav:back$"),
            ],
            APP_RESCHEDULE_TRANSLATOR: _translator_state_handlers(sh, APP_RESCHEDULE_TRANSLATOR),
            APP_RESCHEDULE_CONFIRM:    _confirm_state_handlers(sh, route_sel, route_inp),
            # ── RADIATION THERAPY ─────────────────────────────────────────────
            RADIATION_THERAPY_TYPE: [
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                                        pattern="^nav:back$"),
                CallbackQueryHandler(sh['handle_smart_cancel_navigation'],                                      pattern="^nav:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(rad.get('type'), RADIATION_THERAPY_TYPE)),
            ],
            RADIATION_THERAPY_SESSION_NUMBER: [
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                                               pattern="^nav:back$"),
                CallbackQueryHandler(sh['handle_smart_cancel_navigation'],                                             pattern="^nav:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(rad.get('session_number'), RADIATION_THERAPY_SESSION_NUMBER)),
            ],
            RADIATION_THERAPY_REMAINING: [
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                                           pattern="^nav:back$"),
                CallbackQueryHandler(sh['handle_smart_cancel_navigation'],                                         pattern="^nav:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(rad.get('remaining'), RADIATION_THERAPY_REMAINING)),
            ],
            RADIATION_THERAPY_NOTES: [
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                                       pattern="^nav:back$"),
                CallbackQueryHandler(sh['handle_smart_cancel_navigation'],                                     pattern="^nav:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(rad.get('notes'), RADIATION_THERAPY_NOTES)),
            ],
            RADIATION_THERAPY_RETURN_DATE: [
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                                         pattern="^nav:back$"),
                CallbackQueryHandler(sh['handle_smart_cancel_navigation'],                                       pattern="^nav:cancel$"),
                CallbackQueryHandler(_tracked(rad.get('cal_callback'), RADIATION_THERAPY_RETURN_DATE),          pattern="^rad_cal_"),
                CallbackQueryHandler(_tracked(rad.get('cal_callback'), RADIATION_THERAPY_RETURN_DATE),          pattern="^rad_time_"),
                CallbackQueryHandler(handle_noop,                                                                pattern="^noop$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(rad.get('return_date'), RADIATION_THERAPY_RETURN_DATE)),
            ],
            RADIATION_THERAPY_RETURN_REASON: [
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                                            pattern="^nav:back$"),
                CallbackQueryHandler(sh['handle_smart_cancel_navigation'],                                          pattern="^nav:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _tracked(rad.get('return_reason'), RADIATION_THERAPY_RETURN_REASON)),
            ],
            RADIATION_THERAPY_TRANSLATOR: [
                CallbackQueryHandler(sh['handle_smart_back_navigation'],                                                   pattern="^nav:back$"),
                CallbackQueryHandler(sh['handle_smart_cancel_navigation'],                                                 pattern="^nav:cancel$"),
                CallbackQueryHandler(_tracked(sh['handle_translator_page_navigation'], RADIATION_THERAPY_TRANSLATOR),     pattern="^translator_page:"),
                CallbackQueryHandler(_tracked(sh['handle_simple_translator_choice'], RADIATION_THERAPY_TRANSLATOR),       pattern="^simple_translator:"),
                CallbackQueryHandler(handle_noop,                                                                          pattern="^noop$"),
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
            # medrep gate: handle regardless of current state to prevent unhandled-callback fallthrough
            CallbackQueryHandler(handle_medical_report_choice,                pattern="^medrep:(yes|no|pending)$"),
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
