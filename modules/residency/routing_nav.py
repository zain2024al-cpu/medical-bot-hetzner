# modules/residency/routing_nav.py
# Handles rn: callbacks for top-level residency navigation.
#
# Handler group:
#   group 20  CallbackQueryHandler(^rn:)

import logging
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes, CallbackQueryHandler

from bot.shared_auth import is_admin
from core.access.access_service import user_has_module

logger = logging.getLogger(__name__)
RN = "rn"

_MODULE_KEY = "residency"


def _is_authorized(user_id: int) -> bool:
    return is_admin(user_id) or user_has_module(user_id, _MODULE_KEY)


async def _safe_edit(query, text: str, kb) -> None:
    """Edit a callback message, silently ignoring 'not modified' rejections."""
    try:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    except BadRequest as e:
        if "not modified" in str(e).lower():
            logger.debug("[residency.nav] message unchanged — edit skipped")
        else:
            raise


async def _handle_nav(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data   = query.data or ""
    action = data[len(f"{RN}:"):]
    uid    = query.from_user.id if query.from_user else "?"

    # ✅ الحماية داخل المعالِج نفسه — نفس ما تفعله rna:/rnf:/rnr:/rnu: وكان
    # هذا المعالِج وحده بلا فحص. إخفاء الأزرار لا يكفي: الأزرار المرسَلة
    # سابقاً تبقى قابلة للضغط في محادثة المستخدم بعد سحب صلاحيته، و`rn:archive`
    # يعرض أسماء المرضى وأرقام إقاماتهم وتواريخ انتهائها.
    if not query.from_user or not _is_authorized(query.from_user.id):
        logger.warning(f"[residency.nav] 🚫 blocked unauthorized user={uid}  action={action!r}")
        return

    logger.info(f"[residency.nav] action={action!r}  user={uid}")

    try:
        await _dispatch(update, context, action, uid)
    except Exception:
        logger.exception(f"[residency.nav] unhandled  action={action!r}  user={uid}")


async def _dispatch(update, context, action: str, uid) -> None:
    query = update.callback_query

    if action == "main":
        from modules.residency.profiles.views import build_residency_main_menu
        from modules.residency.followup.repository import get_expiring_soon, get_pending_documents
        text, kb = build_residency_main_menu(
            pending_docs_count=len(get_pending_documents()),
            expiring_count=len(get_expiring_soon()),
        )
        await _safe_edit(query, text, kb)
        return

    if action == "archive":
        from modules.residency.profiles.repository import get_profiles_page
        from modules.residency.profiles.views import build_archive_list
        page = context.user_data.get("_res_archive_page", 0)
        profiles, total = get_profiles_page(page=page)
        text, kb = build_archive_list(profiles, page=page, total=total)
        await _safe_edit(query, text, kb)
        return

    if action == "followup":
        from modules.residency.followup.repository import get_expiring_soon, get_dependent_pending
        from modules.residency.followup.views import build_followup_list
        entries  = get_expiring_soon()
        text, kb = build_followup_list(entries, pending_count=len(get_dependent_pending()))
        await _safe_edit(query, text, kb)
        return

    if action == "pending":
        from modules.residency.followup.repository import get_dependent_pending
        from modules.residency.followup.views import build_pending_list
        entries  = get_dependent_pending()
        text, kb = build_pending_list(entries)
        await _safe_edit(query, text, kb)
        return

    if action == "pending_docs":
        from modules.residency.followup.repository import get_pending_documents
        from modules.residency.followup.views import build_pending_documents_list
        entries  = get_pending_documents()
        text, kb = build_pending_documents_list(entries)
        await _safe_edit(query, text, kb)
        return

    logger.warning(f"[residency.nav] unhandled action={action!r}  user={uid}")


def register_nav_handler(app) -> None:
    app.add_handler(
        CallbackQueryHandler(_handle_nav, pattern=r"^rn:"),
        group=20,
    )
    logger.info("[residency.nav] rn: CallbackQueryHandler registered (group 20)")
