# core/navigation/stack.py
# Module-aware navigation stack stored in user_data.
#
# Each entry is a (module: str | None, state: int) tuple so the stack
# is portable across module boundaries.  The legacy integer-only stack
# in bot/handlers/user/user_reports_add_new_system/navigation.py remains
# untouched for backward compatibility; new modules use this one.
#
# API is intentionally low-level (plain functions over a dict) so it can
# be used from any PTB handler without an extra object instantiation.

import logging
from typing import Any

logger = logging.getLogger(__name__)

_KEY = "_core_nav_stack"
MAX_DEPTH = 25


def push(user_data: dict, state: Any, module: str | None = None) -> None:
    """
    Push a navigation entry.  Consecutive duplicates are silently dropped
    to avoid the same state appearing twice in a row.  Stack is capped at
    MAX_DEPTH entries; oldest entries are trimmed when the cap is exceeded.
    """
    stack = user_data.setdefault(_KEY, [])
    entry = (module, state)
    if stack and stack[-1] == entry:
        return

    if len(stack) >= 2 and stack[-2] == entry:
        removed = stack.pop()
        logger.debug(
            f"[nav] collapse duplicate transition  removed={removed}  depth={len(stack)}"
        )
        return

    stack.append(entry)
    if len(stack) > MAX_DEPTH:
        del stack[:len(stack) - MAX_DEPTH]
    logger.debug(f"[nav] push  state={state}  module={module!r}  depth={len(stack)}")


def pop(user_data: dict) -> tuple[str | None, Any]:
    """
    Remove and return the top entry as (module, state).
    Returns (None, None) when the stack is empty.
    """
    stack = user_data.get(_KEY, [])
    if stack:
        module, state = stack.pop()
        logger.debug(f"[nav] pop   state={state}  module={module!r}  depth={len(stack)}")
        return module, state
    return None, None


def peek(user_data: dict) -> tuple[str | None, Any]:
    """
    Return the top entry without removing it, or (None, None).
    """
    stack = user_data.get(_KEY, [])
    return stack[-1] if stack else (None, None)


def peek_state(user_data: dict) -> Any:
    """Return just the state integer at the top, or None."""
    return peek(user_data)[1]


def previous_state(user_data: dict) -> Any:
    """Return the state one below the top, or None."""
    stack = user_data.get(_KEY, [])
    return stack[-2][1] if len(stack) >= 2 else None


def clear(user_data: dict) -> None:
    """Remove the entire navigation stack."""
    user_data.pop(_KEY, None)
    logger.debug("[nav] cleared")


def depth(user_data: dict) -> int:
    """Current number of entries in the stack."""
    return len(user_data.get(_KEY, []))


def snapshot(user_data: dict) -> list:
    """Return a shallow copy of the stack for debugging."""
    return list(user_data.get(_KEY, []))


def diagnostics(user_data: dict) -> dict:
    """Return a debug summary: depth, top entry, full snapshot."""
    stack = user_data.get(_KEY, [])
    return {
        "depth": len(stack),
        "top": stack[-1] if stack else None,
        "stack": list(stack),
    }
