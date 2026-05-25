# modules/general_services/routing.py
# Wires all general-services handlers and result routes.
# Called once from bot/handlers_registry.py at startup.
#
# Handler group allocation:
#   group  9  — admin_daily_patients text handler  (registered in admin_daily_patients.py)
#   group 10  — arrivals text-input handler         (MessageHandler TEXT)
#   group 11  — arrivals photo-input handler        (MessageHandler PHOTO | Document.IMAGE)
#   group 12  — departures text-input handler       (MessageHandler TEXT)
#   group 14  — public_services text-input handler  (MessageHandler TEXT)
#   group 15  — all GS CallbackQueryHandlers        (gsa: / gsd: / gsp: / gs:)
#
# WARNING: group 10 must remain exclusive to arrivals. Any other broad TEXT handler
# in group 10 will silently absorb arrivals patient-name input before it reaches flow.py.

import logging

logger = logging.getLogger(__name__)


def register_all(app) -> None:
    """Register every general-services handler with the PTB application."""

    # ── Reply keyboard button ─────────────────────────────────────────────────
    from modules.general_services.menu import register_menu_handler
    register_menu_handler(app)

    # ── Main GS menu (gs: navigation) ─────────────────────────────────────────
    from modules.general_services.routing_nav import register_nav_handler
    register_nav_handler(app)

    # ── Arrivals (🛬) ──────────────────────────────────────────────────────────
    from modules.general_services.arrivals.flow import register_handlers as reg_arrivals
    reg_arrivals(app)

    # ── Departures (🛫) ────────────────────────────────────────────────────────
    from modules.general_services.departures.flow import (
        register_handlers as reg_departures,
        register_result_routes as reg_dep_routes,
    )
    reg_departures(app)
    reg_dep_routes()

    # ── Public Services (🧾) ───────────────────────────────────────────────────
    from modules.general_services.public_services.flow import (
        register_handlers as reg_public,
        register_result_routes as reg_pub_routes,
    )
    reg_public(app)
    reg_pub_routes()

    logger.info("[general_services] all handlers and result routes registered")
