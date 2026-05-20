# ================================================
# bot/handlers/shared/flow_interrupt.py
# 🔄 Backward-compatible shim — delegates to core
#
# This file is kept so that existing import paths and the
# application's handler-registration call continue to work
# without any changes to other files.
#
# All logic now lives in:
#   core/conversation/lifecycle.py  — termination + wipe
#   core/conversation/interrupt.py  — menu-button interceptor
#   core/routing/registry.py        — button → module mapping
#   core/modules_bootstrap.py       — module declarations
#
# To add a new menu button that triggers interruption:
#   Edit core/modules_bootstrap.py  (NOT this file).
# ================================================

import logging
from telegram.ext import ConversationHandler, MessageHandler, filters

# Re-export from core so any code that imported these directly still works.
from core.conversation.lifecycle import (          # noqa: F401
    terminate_all_conversations as _terminate_all_conversations,
    has_active_conversation as _has_active_conversation,
    wipe_session as _wipe_session,
)
from core.conversation import interrupt as _core_interrupt

logger = logging.getLogger(__name__)


def register(app) -> None:
    """
    Register the flow-interruption handler.

    Delegates to core.conversation.interrupt which uses the module
    registry populated by core.modules_bootstrap.bootstrap_all().

    Must be called AFTER bootstrap_all() and AFTER all ConversationHandlers
    have been registered (so the group -2 handler is last in -2, before
    group 0 handlers see the message).
    """
    _core_interrupt.register(app)
    logger.info("[flow_interrupt] delegated to core interrupt system")
