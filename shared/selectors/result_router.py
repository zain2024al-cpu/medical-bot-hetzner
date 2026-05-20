# shared/selectors/result_router.py
# Completion handler registry for all shared selectors.
#
# When a selector finishes (user picks a value or cancels), it calls
# result_router.route(return_to, result, update, context).
# The registered handler for that key then receives the result.
#
# Usage — at application startup (once per module):
#
#   from shared.selectors.result_router import register
#   register("healthcare.woundcare.patient", my_handler)
#
# Usage — in a handler after the user picks a patient:
#
#   await route("healthcare.woundcare.patient", patient_record, update, context)
#
# Result value is selector-specific. Shared systems should prefer result
# objects with a `cancelled` flag.

import logging
from typing import Awaitable, Callable, Any

logger = logging.getLogger(__name__)

# key → async callable(result, update, context)
ResultHandler = Callable[[Any, Any, Any], Awaitable[None]]

_registry: dict[str, ResultHandler] = {}


def register(key: str, handler: ResultHandler) -> None:
    """
    Register a completion handler for a given return_to key.

    key     — unique dotted string, e.g. "healthcare.woundcare.patient"
    handler — async def handler(result, update, context)

    Registering the same key twice overwrites the previous handler.
    """
    _registry[key] = handler
    logger.debug(f"[result_router] registered key={key!r}")


async def route(
    key: str,
    result: Any,
    update,
    context,
) -> None:
    """
    Dispatch a selector result to the registered handler.

    If no handler is registered for key, logs a warning and does nothing.
    Shared systems should prefer result objects with a `cancelled` flag.
    """
    if not key:
        logger.debug("[result_router] empty route key ignored")
        return

    handler = _registry.get(key)
    if handler is None:
        logger.warning(f"[result_router] no handler registered for key={key!r}")
        return
    try:
        await handler(result, update, context)
    except Exception as exc:
        logger.error(
            f"[result_router] handler for key={key!r} raised: {exc}",
            exc_info=True,
        )


def registered_keys() -> list[str]:
    """Return all currently registered keys (for diagnostics)."""
    return list(_registry.keys())
