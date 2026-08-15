# modules/residency/menu.py
# زر لوحة المفاتيح "🪪 الإقامة" — يفتح "الملفات المعلّقة" مباشرة (شاشة واحدة).

import logging

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from bot.shared_auth import is_admin
from core.access.access_service import user_has_module

logger = logging.getLogger(__name__)

RESIDENCY_BUTTON = "🪪 الإقامة"
_MODULE_KEY = "residency"


async def _show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_id = update.effective_user.id if update.effective_user else 0

    if not (is_admin(tg_id) or user_has_module(tg_id, _MODULE_KEY)):
        logger.warning(f"[residency] {RESIDENCY_BUTTON!r} pressed by unauthorized user={tg_id}")
        from bot.handlers.user.user_start import user_start
        await user_start(update, context)
        return

    from modules.residency.repository import get_pending_profiles
    from modules.residency.views import build_pending_list

    logger.info(f"[residency] {RESIDENCY_BUTTON!r} pressed  user={tg_id}")
    text, kb = build_pending_list(get_pending_profiles())
    await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


def register_menu_handler(app) -> None:
    app.add_handler(
        MessageHandler(filters.Text([RESIDENCY_BUTTON]), _show_menu),
        group=16,
    )
    logger.info(f"[residency.menu] reply keyboard handler registered for {RESIDENCY_BUTTON!r} (group 16)")
