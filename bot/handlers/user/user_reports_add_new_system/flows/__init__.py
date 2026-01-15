# flows package
# Package for flow-specific handlers (new_consult, followup, emergency, etc.)

# Import shared functions (used by all flows)
from .shared import (
    # Translator functions
    load_translator_names,
    show_translator_selection,
    handle_simple_translator_choice,
    render_translator_selection,
    ask_translator_name,
    show_translator_list,
    handle_translator_list_callback,
    handle_translator_choice,
    handle_translator_inline_selection,
    handle_translator_text,
    get_translator_state,
    ensure_default_translators,
    
    # Summary and Confirm functions
    show_final_summary,
    show_review_screen,
    handle_final_confirm,
    get_confirm_state,
    
    # Save functions
    save_report_to_database,
    
    # Edit functions
    handle_edit_before_save,
    show_edit_fields_menu,
    get_editable_fields_by_flow_type,
    get_field_display_name,
    
    # Helper functions
    escape_markdown_v1,
    format_field_value,
)

# Import flow start functions from stub_flows (which imports from individual flow modules)
from .stub_flows import (
    start_new_consultation_flow,
    start_followup_flow,
    start_periodic_followup_flow,
    start_emergency_flow,
)

# Import followup handlers
from .followup import (
    handle_followup_complaint,
    handle_followup_diagnosis,
    handle_followup_decision,
    handle_followup_room_floor,
    handle_followup_reason,
)

# Import emergency handlers
from .emergency import (
    handle_emergency_complaint,
    handle_emergency_diagnosis,
    handle_emergency_decision,
    handle_emergency_status_choice,
    handle_emergency_admission_notes,
    handle_emergency_operation_details,
    handle_emergency_status_text,
    handle_emergency_admission_type_choice,
    handle_emergency_room_number,
    handle_emergency_date_time_text,
    handle_emergency_reason,
)

# Continue importing from stub_flows
from .stub_flows import (
    start_admission_flow,
    start_operation_flow,
    start_surgery_consult_flow,
    start_final_consult_flow,
    start_discharge_flow,
    start_rehab_flow,
    start_radiology_flow,
    start_reschedule_flow,
)

__all__ = [
    # Shared functions - Translator
    'load_translator_names',
    'show_translator_selection',
    'handle_simple_translator_choice',
    'render_translator_selection',
    'ask_translator_name',
    'show_translator_list',
    'handle_translator_list_callback',
    'handle_translator_choice',
    'handle_translator_inline_selection',
    'handle_translator_text',
    'get_translator_state',
    'ensure_default_translators',
    
    # Summary and Confirm functions
    'show_final_summary',
    'show_review_screen',
    'handle_final_confirm',
    'get_confirm_state',
    
    # Save functions
    'save_report_to_database',
    
    # Edit functions
    'handle_edit_before_save',
    'show_edit_fields_menu',
    'get_editable_fields_by_flow_type',
    'get_field_display_name',
    
    # Helper functions
    'escape_markdown_v1',
    'format_field_value',
    
    # Flow start functions
    'start_new_consultation_flow',
    'start_followup_flow',
    'start_periodic_followup_flow',
    # Followup handlers
    'handle_followup_complaint',
    'handle_followup_diagnosis',
    'handle_followup_decision',
    'handle_followup_room_floor',
    'handle_followup_reason',
    # Emergency handlers
    'handle_emergency_complaint',
    'handle_emergency_diagnosis',
    'handle_emergency_decision',
    'handle_emergency_status_choice',
    'handle_emergency_admission_notes',
    'handle_emergency_operation_details',
    'handle_emergency_status_text',
    'handle_emergency_admission_type_choice',
    'handle_emergency_room_number',
    'handle_emergency_date_time_text',
    'handle_emergency_reason',
    'start_emergency_flow',
    'start_admission_flow',
    'start_operation_flow',
    'start_surgery_consult_flow',
    'start_final_consult_flow',
    'start_discharge_flow',
    'start_rehab_flow',
    'start_radiology_flow',
    'start_reschedule_flow',
]

