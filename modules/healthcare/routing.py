# modules/healthcare/routing.py
# Healthcare module wiring — registers all handlers and result routes.
# Called once from bot/handlers_registry.py at startup.

import logging

logger = logging.getLogger(__name__)


def register_all(app) -> None:
    """
    Register every healthcare handler with the PTB application.

    Order matters within group 0 — this must be called AFTER
    all production ConversationHandlers so the notes MessageHandler
    doesn't intercept messages that belong to existing flows.
    """
    from modules.healthcare.menu import register_menu_handler
    from modules.healthcare.woundcare.flow import (
        register_handlers as register_woundcare_handlers,
        register_result_routes,
    )

    register_menu_handler(app)
    register_woundcare_handlers(app)
    register_result_routes()

    logger.info("[healthcare] all handlers and result routes registered")
