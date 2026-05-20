# core/conversation/lifecycle.py
# Single source of truth for conversation lifecycle management.
#
# Responsibilities:
#   - terminating PTB ConversationHandler FSM states
#   - wiping transient user_data keys (core + legacy)
#   - combined interrupt_and_reset for one-shot use
#
# This module has NO PTB handler registration — it is a pure utility
# consumed by core/conversation/interrupt.py and by bot/handlers/shared/flow_interrupt.py.

import logging
from telegram.ext import ConversationHandler

logger = logging.getLogger(__name__)

# ── Key sets ──────────────────────────────────────────────────────────────────

_CORE_KEYS: frozenset = frozenset({
    "_core_active_module",
    "_core_nav_stack",
    "_core_draft",
})

# Keys owned by shared infrastructure components.
# Wiped on every flow interruption so stale selector/upload state never
# leaks into a freshly started flow.
_SHARED_INFRA_KEYS: frozenset = frozenset({
    "_upl",          # shared/uploads  — upload collector session
    "_sel_patient",  # shared/selectors/patient_selector
    "_msel",         # shared/multiselect
})

# Legacy user_data keys that every module cleanup must wipe.
# Add here when a new module introduces a new transient key that should
# be cleared on any flow interruption.
_LEGACY_WIPE_KEYS: frozenset = frozenset({
    "report_tmp",
    "history",           # legacy nav stack used by user_reports_add_new_system
    "_nav_stack",
    "_conversation_state",
    "last_valid_state",
    "patient_page",
    "user_patient_page",
    "hospitals_page",
    "departments_page",
    "doctor_page",
    "edit_report_id",
    "delete_reports",
    "cs_patients",
    "cs_patient_id",
    "cs_page",
    "cs_patient_name",
    "ma_state",
    "print_type",
    "analysis_type",
    "edit_hospital_id",
    "patient_name_edit",
    "waiting_for_patients",
    "_current_search_type",
})

# Key prefixes — any user_data key *starting with* these is also wiped.
_WIPE_PREFIXES: tuple = (
    "print_", "period", "year_", "month_",
    "selected_", "waiting_", "searching_",
)


# ── Core functions ────────────────────────────────────────────────────────────

def terminate_all_conversations(
    application, chat_id: int, user_id: int
) -> int:
    """
    Remove (chat_id, user_id) from every ConversationHandler's internal
    _conversations dict, resetting all FSM states simultaneously.

    Returns the count of handlers that had an active state (and were reset).
    """
    key = (chat_id, user_id)
    terminated = 0

    for group_handlers in application.handlers.values():
        for handler in group_handlers:
            if not isinstance(handler, ConversationHandler):
                continue
            if key in handler._conversations:
                try:
                    del handler._conversations[key]
                    terminated += 1
                    logger.info(
                        f"[lifecycle] terminated handler={handler.name!r} key={key}"
                    )
                except Exception as exc:
                    logger.warning(
                        f"[lifecycle] could not terminate {handler.name!r}: {exc}"
                    )

    return terminated


def has_active_conversation(
    application, chat_id: int, user_id: int
) -> bool:
    """Return True if any ConversationHandler has an active state for this user."""
    key = (chat_id, user_id)
    for group_handlers in application.handlers.values():
        for handler in group_handlers:
            if isinstance(handler, ConversationHandler) and key in handler._conversations:
                return True
    return False


def wipe_session(user_data: dict, extra_keys: set | None = None) -> None:
    """
    Clear transient session state from user_data.

    Always removes:
      - Core-owned keys  (_core_active_module, _core_nav_stack, _core_draft)
      - Legacy transient keys  (report_tmp, history, etc.)
      - Keys with legacy prefixes  (print_*, year_*, etc.)

    Pass extra_keys to also wipe module-specific keys.
    """
    to_wipe = _CORE_KEYS | _SHARED_INFRA_KEYS | _LEGACY_WIPE_KEYS | (extra_keys or set())

    for k in list(user_data.keys()):
        if k in to_wipe or k.startswith(_WIPE_PREFIXES):
            del user_data[k]


def interrupt_and_reset(
    application,
    chat_id: int,
    user_id: int,
    user_data: dict,
    extra_wipe_keys: set | None = None,
) -> int:
    """
    Convenience wrapper: terminate all FSM states AND wipe user_data in one call.

    Returns the number of handlers that were actively terminated.
    Returns 0 if nothing was running (wipe still happens).
    """
    terminated = terminate_all_conversations(application, chat_id, user_id)
    wipe_session(user_data, extra_wipe_keys)
    if terminated:
        logger.info(
            f"[lifecycle] interrupt_and_reset  user={user_id}"
            f"  terminated={terminated}"
        )
    return terminated
