# modules/residency/menu.py
# Reply keyboard trigger: "🪪 الإقامة"

import logging
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from bot.shared_auth import is_admin
from core.access.access_service import user_has_module

logger = logging.getLogger(__name__)

_BUTTON = "🪪 الإقامة"
_MODULE_KEY = "residency"


def _is_authorized(user_id: int) -> bool:
    return is_admin(user_id) or user_has_module(user_id, _MODULE_KEY)


async def _handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id if update.effective_user else "?"
    # ✅ الحماية داخل المعالِج نفسه — لا تعتمد على إظهار/إخفاء الزر في
    # لوحة المفاتيح، لأن هذا المعالِج يستجيب لأي رسالة نصية تطابق النص
    # حرفياً بغض النظر عمن أرسلها أو كيف كُتبت.
    if not update.effective_user or not _is_authorized(update.effective_user.id):
        logger.warning(f"[residency.menu] 🚫 blocked unauthorized user={uid}")
        return
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
