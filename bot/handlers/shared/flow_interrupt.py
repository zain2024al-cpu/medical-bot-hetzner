# ================================================
# bot/handlers/shared/flow_interrupt.py
# 🔄 Global automatic flow interruption system
#
# Runs in group -1 (before all ConversationHandlers in group 0).
# When a user presses a main-menu button while any ConversationHandler
# has an active state for that user:
#   1. Iterates all registered ConversationHandlers in the application
#   2. Removes the user's conversation key from each handler's internal
#      _conversations dict (the authoritative PTB state store)
#   3. Clears navigation/draft keys from user_data
#   4. Sends a single "cancelled" notice
#   5. Returns None — update continues to group 0, target handler opens normally
#
# Why _conversations and not user_data:
#   PTB stores ConversationHandler state in handler._conversations[(chat_id, user_id)],
#   NOT in user_data. Clearing user_data alone leaves the FSM state intact and the
#   new entry_point never fires because PTB thinks the old flow is still running.
# ================================================

import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters

logger = logging.getLogger(__name__)

# ── Main menu buttons that trigger auto-interruption ─────────────────────────
# Must match exact strings in bot/keyboards.py user_main_kb()
_USER_MENU_BUTTONS = {
    "📝 إضافة تقرير جديد",
    "✏️ تعديل التقارير",
    "🗑️ حذف التقارير",
    "📅 جدول اليوم",
    "🚀 ابدأ",
    "📋 ملخص الحالة",
    "📎 المرفقات الطبية",
}

# user_data keys to wipe when interrupting (draft/nav state only)
_WIPE_KEYS = {
    "report_tmp",
    "_nav_stack",
    "_conversation_state",
    "last_valid_state",
    "patient_page",
    "user_patient_page",
    "hospitals_page",
    "departments_page",
    "doctor_page",
    "edit_report_id",
    "delete_reports",
    "cs_patients",
    "cs_patient_id",
    "cs_page",
    "cs_patient_name",
    "ma_state",
    "print_type",
    "analysis_type",
    "edit_hospital_id",
    "patient_name_edit",
    "waiting_for_patients",
    "_current_search_type",
}


def _terminate_all_conversations(application, chat_id: int, user_id: int) -> int:
    """
    Walk every ConversationHandler registered in the application and remove
    the (chat_id, user_id) key from its internal _conversations dict.

    Returns the number of active conversations that were terminated.
    """
    terminated = 0
    conversation_key = (chat_id, user_id)

    for group_handlers in application.handlers.values():
        for handler in group_handlers:
            if not isinstance(handler, ConversationHandler):
                continue
            if conversation_key in handler._conversations:
                try:
                    del handler._conversations[conversation_key]
                    terminated += 1
                    logger.info(
                        f"[flow_interrupt] terminated conv handler "
                        f"name={handler.name!r} key={conversation_key}"
                    )
                except Exception as e:
                    logger.warning(f"[flow_interrupt] could not terminate handler {handler.name!r}: {e}")

    return terminated


def _has_active_conversation(application, chat_id: int, user_id: int) -> bool:
    """Return True if ANY ConversationHandler has an active state for this user."""
    conversation_key = (chat_id, user_id)
    for group_handlers in application.handlers.values():
        for handler in group_handlers:
            if isinstance(handler, ConversationHandler):
                if conversation_key in handler._conversations:
                    return True
    return False


def _clear_user_data(user_data: dict) -> None:
    """Remove known transient keys from user_data."""
    for k in list(user_data.keys()):
        if k in _WIPE_KEYS or k.startswith(("print_", "period", "year_", "month_",
                                             "selected_", "waiting_", "searching_")):
            del user_data[k]


async def intercept_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Group -1 interceptor. Fires before ConversationHandlers (group 0).

    Checks if any ConversationHandler has an active state for this user.
    If yes: terminates all active conversations, clears user_data draft state,
    sends a brief notice, then returns None so the message continues to group 0
    where the target handler's entry_point picks it up normally.
    """
    if not update.message or not update.message.text:
        return None

    text = update.message.text.strip()
    if text not in _USER_MENU_BUTTONS:
        return None

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if not _has_active_conversation(context.application, chat_id, user_id):
        return None

    # ── Active conversation found — terminate it ──────────────────────────────
    count = _terminate_all_conversations(context.application, chat_id, user_id)
    _clear_user_data(context.user_data)

    logger.info(
        f"[flow_interrupt] user={user_id} button='{text}' "
        f"— terminated {count} conversation(s)"
    )

    try:
        await update.message.reply_text("ℹ️ تم إلغاء العملية السابقة تلقائياً.")
    except Exception as e:
        logger.warning(f"[flow_interrupt] could not send notice: {e}")

    # Return None — PTB continues dispatching to group 0.
    return None


# ── Registration ──────────────────────────────────────────────────────────────

def register(app) -> None:
    """Register the interceptor in group -1 (before all ConversationHandlers)."""
    import re
    btn_filter = filters.TEXT & filters.Regex(
        "^(" + "|".join(re.escape(s) for s in _USER_MENU_BUTTONS) + ")$"
    )
    app.add_handler(
        MessageHandler(btn_filter, intercept_menu_button),
        group=-1,
    )
    logger.info("[flow_interrupt] registered in group -1")
