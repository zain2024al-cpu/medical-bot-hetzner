# modules/healthcare/routing.py
# Healthcare module wiring — registers all handlers and result routes.
# Called once from bot/handlers_registry.py at startup.
#
# Handler group allocation:
#   group  0  — woundcare text-input handler  (MessageHandler TEXT)
#   group  1  — all CallbackQueryHandlers (wca:, hcfu:, hcmed:, hcoth:, hc:)
#   group  2  — medical_followup text-input handler  (MessageHandler TEXT)
#   group  4  — medications text-input handler        (MessageHandler TEXT)
#   group  6  — other_hc text-input handler           (MessageHandler TEXT)
#
#   IMPORTANT (PTB v20): within a single group, the FIRST matching handler wins
#   and stops further processing in that group. Text handlers MUST each occupy a
#   unique group number so they all receive every message independently and can
#   each check their own session key without blocking one another.
#
# The hc: dispatcher lives in woundcare/flow.py and is the single handler for all
# hc:* navigation callbacks.  It uses late-binding imports for sub-module menu
# builders to avoid circular-import and PTB registration-order issues.

import logging

logger = logging.getLogger(__name__)


def register_all(app) -> None:
    """
    Register every healthcare handler with the PTB application.

    MUST be called AFTER all production ConversationHandlers so that the
    group-0 text-input handlers are lower-priority fallbacks.
    """
    # ── Top-level menu ────────────────────────────────────────────────────────
    from modules.healthcare.menu import register_menu_handler
    register_menu_handler(app)

    # ── Woundcare (🩺) ────────────────────────────────────────────────────────
    from modules.healthcare.woundcare.flow import (
        register_handlers as register_woundcare_handlers,
        register_result_routes as register_woundcare_routes,
    )
    register_woundcare_handlers(app)
    register_woundcare_routes()

    # ── Medical Follow-up (📋) ────────────────────────────────────────────────
    from modules.healthcare.medical_followup.flow import (
        register_handlers as register_followup_handlers,
        register_result_routes as register_followup_routes,
    )
    register_followup_handlers(app)
    register_followup_routes()

    # ── Medications (💊) ──────────────────────────────────────────────────────
    from modules.healthcare.medications.flow import (
        register_handlers as register_medication_handlers,
        register_result_routes as register_medication_routes,
    )
    register_medication_handlers(app)
    register_medication_routes()

    # ── Supplies (🏥) ────────────────────────────────────────────────────────
    from modules.healthcare.supplies.flow import (
        register_handlers as register_supplies_handlers,
        register_result_routes as register_supplies_routes,
    )
    register_supplies_handlers(app)
    register_supplies_routes()

    # ── Other (📝) ────────────────────────────────────────────────────────────
    from modules.healthcare.other.flow import (
        register_handlers as register_other_handlers,
        register_result_routes as register_other_routes,
    )
    register_other_handlers(app)
    register_other_routes()

    logger.info("[healthcare] all handlers and result routes registered")
