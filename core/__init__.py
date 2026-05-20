# core/__init__.py
# Public API surface of the core system.
#
# Typical startup sequence (in your main application file):
#
#   from core.modules_bootstrap import bootstrap_all
#   from core.conversation import interrupt
#
#   bootstrap_all()                        # register all modules
#   # ... add all PTB ConversationHandlers (group 0) ...
#   interrupt.register(app)               # add group -2 interceptor LAST
#
# Per-handler usage:
#
#   from core.session import get_session
#   from core import navigation as nav
#   from core.routing import registry

from core import navigation
from core.session import get_session, SessionManager
from core.routing import registry
from core.conversation.lifecycle import (
    terminate_all_conversations,
    has_active_conversation,
    wipe_session,
    interrupt_and_reset,
)

__all__ = [
    # Sub-packages
    "navigation",
    # Session
    "get_session",
    "SessionManager",
    # Routing
    "registry",
    # Lifecycle
    "terminate_all_conversations",
    "has_active_conversation",
    "wipe_session",
    "interrupt_and_reset",
]
