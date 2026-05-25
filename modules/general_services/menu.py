# modules/general_services/menu.py
# Reply-keyboard button handler for "🔧 الخدمات العامة".
#
# Registered in group -1 so it fires AFTER the interrupt handler (group -2)
# but BEFORE the generic TEXT handlers in group 0 (woundcare, medications, etc.).
# Using filters.Text([...]) — exact match, same pattern as healthcare/menu.py.

import logging

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

logger = logging.getLogger(__name__)

_BUTTON = "🔧 الخدمات العامة"


async def _handle_gs_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_id = update.effective_user.id

    from core.access.access_service import user_has_module
    if not user_has_module(tg_id, "general_services"):
        logger.warning(
            f"[general_services] {_BUTTON!r} pressed by unauthorized user={tg_id}"
            " — re-routing to user_start"
        )
        from bot.handlers.user.user_start import user_start
        await user_start(update, context)
        return

    logger.info(f"[general_services] {_BUTTON!r} pressed  user={tg_id}")
    from modules.general_services.views import build_gs_menu
    text, kb = build_gs_menu()
    await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


def register_menu_handler(app) -> None:
    """Register in group -1 — before group 0 generic text handlers."""
    app.add_handler(
        MessageHandler(filters.Text([_BUTTON]), _handle_gs_button),
        group=-1,
    )
    logger.info(f"[general_services] menu handler registered  button={_BUTTON!r}  group=-1")
