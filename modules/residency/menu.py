# modules/residency/menu.py
# Reply keyboard trigger: "🪪 الإقامة"

import logging
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

logger = logging.getLogger(__name__)

_BUTTON = "🪪 الإقامة"


async def _handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id if update.effective_user else "?"
    logger.info(f"[residency.menu] {_BUTTON!r} pressed  user={uid}")
    from modules.residency.profiles.views import build_residency_main_menu
    text, kb = build_residency_main_menu()
    await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


def register_menu_handler(app) -> None:
    app.add_handler(
        MessageHandler(filters.Text([_BUTTON]), _handle_menu_button),
        group=16,  # group 16 = residency text group, runs independently of group 0 (healthcare)
    )
    logger.info(f"[residency.menu] reply keyboard handler registered for {_BUTTON!r} (group 16)")
