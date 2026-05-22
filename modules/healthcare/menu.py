# modules/healthcare/menu.py
# Healthcare main-menu MessageHandler.
# Fires when a user presses "🏥 الرعاية الصحية" on the reply keyboard.

import logging

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

logger = logging.getLogger(__name__)

HEALTHCARE_BUTTON = "▶️ ابدأ الآن"


async def _show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delegate to user_start — pressing ابدأ الآن is identical to /start."""
    from bot.handlers.user.user_start import user_start
    logger.info(f"[healthcare] ابدأ الآن pressed → forwarding to user_start  user={update.effective_user.id}")
    await user_start(update, context)


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
