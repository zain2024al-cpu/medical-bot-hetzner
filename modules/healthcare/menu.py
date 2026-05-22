# modules/healthcare/menu.py
# Healthcare reply-keyboard button handler.
# Fires when an authorized user presses "▶️ ابدأ الآن" on the reply keyboard.

import logging

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

logger = logging.getLogger(__name__)

HEALTHCARE_BUTTON = "▶️ ابدأ الآن"


async def _show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show the healthcare module menu directly (RBAC-gated).

    This handler fires for the reply-keyboard button "▶️ ابدأ الآن".
    It shows the healthcare menu immediately without going through the full
    /start flow — pressing this button is "go back to the healthcare menu",
    not "re-run onboarding".

    If a non-healthcare user somehow triggers this button (stale keyboard),
    they are silently re-routed to their role-appropriate /start screen.
    """
    tg_id = update.effective_user.id

    from core.access.access_service import user_has_module
    if not user_has_module(tg_id, "healthcare"):
        logger.warning(
            f"[healthcare] ▶️ ابدأ الآن pressed by non-healthcare user={tg_id} "
            f"— re-routing to user_start"
        )
        # Late import to avoid circular dependency (modules/ → bot/).
        from bot.handlers.user.user_start import user_start
        await user_start(update, context)
        return

    logger.info(f"[healthcare] ▶️ ابدأ الآن pressed  user={tg_id}")
    from modules.healthcare.views import build_healthcare_menu
    text, kb = build_healthcare_menu()
    await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


def register_menu_handler(app) -> None:
    """Register the reply-keyboard button handler in group 0."""
    app.add_handler(
        MessageHandler(
            filters.Text([HEALTHCARE_BUTTON]),
            _show_menu,
        ),
        group=0,
    )
    logger.info(f"[healthcare] menu handler registered  button={HEALTHCARE_BUTTON!r}")
