# modules/healthcare/menu.py
# Healthcare main-menu MessageHandler.
# Fires when a user presses "🏥 الرعاية الصحية" on the reply keyboard.

import logging

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from modules.healthcare.woundcare.views import build_healthcare_menu

logger = logging.getLogger(__name__)

HEALTHCARE_BUTTON = "🏥 الرعاية الصحية"


async def _show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text, kb = build_healthcare_menu()
    await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
    logger.info(f"[healthcare] menu shown  user={update.effective_user.id}")


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
