# modules/residency/routing.py
# نقطة التسجيل الوحيدة — تُستدعى من bot/handlers_registry.py.

import logging

logger = logging.getLogger(__name__)


def register_all(app) -> None:
    from modules.residency.menu import register_menu_handler
    from modules.residency.flow import register_handlers

    register_menu_handler(app)
    register_handlers(app)
    logger.info("[residency] all handlers registered (نظام دورة الحياة الكامل)")
