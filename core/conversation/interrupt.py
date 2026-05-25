# core/conversation/interrupt.py
# Registry-driven menu-button interceptor.
#
# Registered in group -2 (before all ConversationHandlers in group 0).
# When a menu button is pressed that belongs to any registered module:
#   1. Check whether any ConversationHandler is currently active.
#   2. If yes: interrupt it, wipe session, send a brief notice.
#   3. Mark the new module as active in user_data.
#   4. Return None — PTB continues to group 0 where the target handler fires.
#
# The button → module mapping lives entirely in core.routing.registry so
# this file never needs to enumerate button strings manually.

import logging
import re
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from core.routing.registry import registry
from core.conversation.lifecycle import (
    has_active_conversation,
    interrupt_and_reset,
    wipe_session,
)

logger = logging.getLogger(__name__)

_KEY_ACTIVE_MODULE = "_core_active_module"


async def _intercept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return None

    text = update.message.text.strip()
    target_module = registry.resolve_button(text)
    if target_module is None:
        return None  # not a registered module button

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    current_module = context.user_data.get(_KEY_ACTIVE_MODULE)

    # Resolve target module registration once — used in both branches.
    target_reg = registry.get(target_module)
    target_wipe_keys = target_reg.extra_wipe_keys if target_reg else set()

    if not has_active_conversation(context.application, chat_id, user_id):
        # No active PTB ConversationHandler.
        # Still check for stale session-based flows (e.g. arrivals, departures,
        # public_services) that store state directly in user_data.  Pressing any
        # module button is a mandatory clean restart — wipe those keys too.
        stale_keys = target_wipe_keys & set(context.user_data)
        if stale_keys:
            wipe_session(context.user_data, target_wipe_keys)
            logger.info(
                f"[interrupt] stale session wiped  user={user_id}"
                f"  module={target_module!r}  found={stale_keys}"
            )
            try:
                await update.message.reply_text("ℹ️ تم إلغاء العملية السابقة تلقائياً.")
            except Exception as exc:
                logger.warning(f"[interrupt] stale-session notice failed: {exc}")
        context.user_data[_KEY_ACTIVE_MODULE] = target_module
        return None

    # ── Active ConversationHandler detected — full interrupt ─────────────────
    current_reg = registry.get(current_module) if current_module else None
    # Merge current-module keys + target-module keys so both are wiped atomically.
    extra_keys = (current_reg.extra_wipe_keys if current_reg else set()) | target_wipe_keys

    # Fire on_deactivate hook if the current module defined one
    if current_reg and current_reg.on_deactivate:
        try:
            current_reg.on_deactivate(context.user_data)
        except Exception as exc:
            logger.warning(f"[interrupt] on_deactivate({current_module!r}) failed: {exc}")

    terminated = interrupt_and_reset(
        context.application, chat_id, user_id,
        context.user_data, extra_keys,
    )

    context.user_data[_KEY_ACTIVE_MODULE] = target_module

    # Fire on_activate hook for the new module if defined
    if target_reg and target_reg.on_activate:
        try:
            target_reg.on_activate(context.user_data)
        except Exception as exc:
            logger.warning(f"[interrupt] on_activate({target_module!r}) failed: {exc}")

    logger.info(
        f"[interrupt] user={user_id}  button={text!r}"
        f"  {current_module!r} → {target_module!r}"
        f"  terminated={terminated}"
    )

    try:
        await update.message.reply_text("ℹ️ تم إلغاء العملية السابقة تلقائياً.")
    except Exception as exc:
        logger.warning(f"[interrupt] notice send failed: {exc}")

    return None  # continue dispatching to group 0


def register(app) -> None:
    """
    Register the core interrupt handler in PTB group -2.
    Must be called AFTER core.modules_bootstrap.bootstrap_all().
    """
    all_buttons = registry.all_menu_buttons()
    if not all_buttons:
        logger.warning(
            "[interrupt] no modules registered yet — "
            "call modules_bootstrap.bootstrap_all() before interrupt.register()"
        )
        return

    pattern = "^(" + "|".join(re.escape(b) for b in all_buttons) + ")$"
    btn_filter = filters.TEXT & filters.Regex(pattern)
    app.add_handler(MessageHandler(btn_filter, _intercept), group=-2)
    logger.info(
        f"[interrupt] registered in group -2  "
        f"modules={registry.all_modules()}  buttons={len(all_buttons)}"
    )
