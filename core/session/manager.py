# core/session/manager.py
# Typed facade over PTB's user_data dict.
#
# Provides namespaced access to:
#   - active module tracking
#   - core navigation stack (delegates to core.navigation.stack)
#   - per-module draft data (form state while filling a report)
#   - full session wipe
#
# Usage:
#   from core.session import get_session
#   session = get_session(context)
#   session.set_active_module("user_reports")
#   session.draft("user_reports")["patient_id"] = 42

import logging
from core import navigation as nav
from core.conversation.lifecycle import wipe_session

logger = logging.getLogger(__name__)

_KEY_ACTIVE_MODULE = "_core_active_module"
_KEY_DRAFT = "_core_draft"


class SessionManager:
    """
    Thin, typed wrapper around a PTB user_data dict.

    Do not store the instance across async yields — always obtain a fresh
    one via get_session(context) at the start of each handler, since
    user_data is already persistent for the user's lifetime.
    """

    __slots__ = ("_d",)

    def __init__(self, user_data: dict) -> None:
        self._d = user_data

    # ── Module tracking ───────────────────────────────────────────────────────

    def get_active_module(self) -> str | None:
        return self._d.get(_KEY_ACTIVE_MODULE)

    def set_active_module(self, module: str | None) -> None:
        if module is None:
            self._d.pop(_KEY_ACTIVE_MODULE, None)
        else:
            self._d[_KEY_ACTIVE_MODULE] = module

    # ── Navigation stack ──────────────────────────────────────────────────────

    def nav_push(self, state, module: str | None = None) -> None:
        nav.push(self._d, state, module)

    def nav_pop(self) -> tuple[str | None, object]:
        return nav.pop(self._d)

    def nav_peek(self) -> tuple[str | None, object]:
        return nav.peek(self._d)

    def nav_peek_state(self) -> object:
        return nav.peek_state(self._d)

    def nav_previous_state(self) -> object:
        return nav.previous_state(self._d)

    def nav_clear(self) -> None:
        nav.clear(self._d)

    def nav_depth(self) -> int:
        return nav.depth(self._d)

    def nav_snapshot(self) -> list:
        return nav.snapshot(self._d)

    # ── Draft (per-module form data) ──────────────────────────────────────────

    def draft(self, module: str) -> dict:
        """
        Return the mutable draft dict for a module.
        Automatically created on first access.
        """
        return self._d.setdefault(_KEY_DRAFT, {}).setdefault(module, {})

    def clear_draft(self, module: str) -> None:
        self._d.get(_KEY_DRAFT, {}).pop(module, None)

    def clear_all_drafts(self) -> None:
        self._d.pop(_KEY_DRAFT, None)

    # ── Session wipe ──────────────────────────────────────────────────────────

    def wipe(self, extra_keys: set | None = None) -> None:
        """
        Wipe all transient session state (core + legacy keys).
        Pass extra_keys to also remove module-specific keys.
        """
        wipe_session(self._d, extra_keys)


def get_session(context) -> SessionManager:
    """Convenience factory — accepts any PTB context object."""
    return SessionManager(context.user_data)
