# modules/residency/routing.py
# Wires all residency handlers and result routes.
# Called once from bot/handlers_registry.py at startup.
#
# Handler group allocation:
#   group 16  MessageHandler(TEXT) — text input (name, residency number, notes, search)
#   group 20  CallbackQueryHandlers — rn: / rna: / rnf: / rnr:
#
# WARNING: group 16 must remain exclusive to residency text input.
# WARNING: group 20 must not conflict with other modules. GS uses group 15.

import logging

logger = logging.getLogger(__name__)


def register_all(app) -> None:
    """Register every residency handler with the PTB application."""

    # ── Reply keyboard button ─────────────────────────────────────────────────
    from modules.residency.menu import register_menu_handler
    register_menu_handler(app)

    # ── Top-level navigation (rn:) ─────────────────────────────────────────────
    from modules.residency.routing_nav import register_nav_handler
    register_nav_handler(app)

    # ── Profiles: archive + add new patient (rna:) ────────────────────────────
    from modules.residency.profiles.flow import (
        register_handlers as reg_profiles,
        register_result_routes as reg_profiles_routes,
    )
    reg_profiles(app)
    reg_profiles_routes()

    # ── Followup: expiring + pending (rnf:) ────────────────────────────────────
    from modules.residency.followup.flow import register_handlers as reg_followup
    reg_followup(app)

    # ── Renewal: issuance flow (rnr:) ──────────────────────────────────────────
    from modules.residency.renewal.flow import (
        register_handlers as reg_renewal,
        register_result_routes as reg_renewal_routes,
    )
    reg_renewal(app)
    reg_renewal_routes()

    logger.info("[residency] all handlers and result routes registered")
