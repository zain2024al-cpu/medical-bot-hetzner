# modules/residency/followup/flow.py
# Handles rnf: callbacks for المتابعة and التحديثات المعلقة.
#
# Handler group:
#   group 20  CallbackQueryHandler(^rnf:)

import logging

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler

from bot.shared_auth import is_admin
from core.access.access_service import user_has_module

logger = logging.getLogger(__name__)
RNF = "rnf"
RN  = "rn"

_MODULE_KEY = "residency"


def _is_authorized(user_id: int) -> bool:
    return is_admin(user_id) or user_has_module(user_id, _MODULE_KEY)


async def _dispatch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data   = query.data or ""
    action = data[len(f"{RNF}:"):]
    uid    = query.from_user.id if query.from_user else "?"

    # ✅ الحماية داخل المعالِج نفسه — مستقلة تماماً عن ظهور الزر في القائمة.
    if not query.from_user or not _is_authorized(query.from_user.id):
        logger.warning(f"[residency.followup.cb] 🚫 blocked unauthorized user={uid}  action={action!r}")
        return

    logger.info(f"[residency.followup.cb] action={action!r}  user={uid}")

    try:
        await _dispatch_inner(update, context, action, uid)
    except Exception:
        logger.exception(f"[residency.followup.cb] unhandled  action={action!r}  user={uid}")


async def _dispatch_inner(update, context, action: str, uid) -> None:
    query = update.callback_query

    # ── تم التقديم — profile ─────────────────────────────────────────────────
    if action.startswith("submitted_c_"):
        # format: submitted_c_{companion_id}_{profile_id}
        parts = action[12:].split("_")
        try:
            companion_id = int(parts[0])
            profile_id   = int(parts[1])
        except (IndexError, ValueError):
            return
        from modules.residency.followup.repository import mark_renewal_submitted
        mark_renewal_submitted(
            profile_id=   profile_id,
            companion_id= companion_id,
            performed_by= uid if isinstance(uid, int) else None,
        )
        await query.answer("✅ تم تسجيل التقديم للمرافق", show_alert=True)
        # Refresh list
        from modules.residency.followup.repository import get_expiring_soon
        from modules.residency.followup.views import build_followup_list
        entries  = get_expiring_soon()
        text, kb = build_followup_list(entries)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if action.startswith("submitted_"):
        profile_id = int(action[10:])
        from modules.residency.followup.repository import mark_renewal_submitted
        mark_renewal_submitted(
            profile_id=   profile_id,
            companion_id= None,
            performed_by= uid if isinstance(uid, int) else None,
        )
        await query.answer("✅ تم تسجيل التقديم", show_alert=True)
        # Refresh list
        from modules.residency.followup.repository import get_expiring_soon
        from modules.residency.followup.views import build_followup_list
        entries  = get_expiring_soon()
        text, kb = build_followup_list(entries)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ── استكمال المرافقين — complete_{profile_id} ────────────────────────────
    if action.startswith("complete_"):
        profile_id = int(action[9:])
        # Open renewal flow for this profile, flagged as companion-completion
        # (the renewal flow will start from companion update directly)
        context.user_data["_rnr_complete_companions"] = True
        from telegram.ext import ContextTypes as CT
        # Redirect to renewal start
        query.data = f"rnr:start_{profile_id}"
        from modules.residency.renewal.flow import _dispatch_callback as rnr_cb
        await rnr_cb(update, context)
        return

    logger.warning(f"[residency.followup.cb] unhandled action={action!r}  user={uid}")


def register_handlers(app) -> None:
    app.add_handler(
        CallbackQueryHandler(_dispatch_callback, pattern=r"^rnf:"),
        group=20,
    )
    logger.info("[residency.followup] rnf: CallbackQueryHandler registered (group 20)")
