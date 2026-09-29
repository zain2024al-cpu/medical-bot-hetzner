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
# key → callable(user_id) -> bool
Guard = Callable[[int], bool]

_registry: dict[str, ResultHandler] = {}
_guards: dict[str, Guard] = {}


def register(key: str, handler: ResultHandler, *, guard: Guard | None = None) -> None:
    """
    Register a completion handler for a given return_to key.

    key     — unique dotted string, e.g. "healthcare.woundcare.patient"
    handler — async def handler(result, update, context)
    guard   — اختياري: callable(user_id) -> bool يُعاد التحقّق منه فعلياً عند
              اكتمال الاختيار (لا فقط عند فتح الشاشة). كل شاشات multiselect/
              selectors تبقى مفتوحة لدقائق، وصلاحية المستخدم قد تُلغى أثناء
              ذلك — بلا guard يُكمِل حتى النهاية رغم إلغاء صلاحيته. الفشل أو
              رفع استثناء داخل guard يُرفَض احتياطاً (fail-closed)، نفس
              اتفاقية `scripts/audit_callback_auth.py`.

    Registering the same key twice overwrites the previous handler/guard.
    """
    _registry[key] = handler
    if guard is not None:
        _guards[key] = guard
    else:
        _guards.pop(key, None)
    logger.debug(f"[result_router] registered key={key!r} guard={'yes' if guard else 'no'}")


async def route(
    key: str,
    result: Any,
    update,
    context,
) -> None:
    """
    Dispatch a selector result to the registered handler.

    If no handler is registered for key, logs a warning and does nothing.
    If a guard was registered for key, it is re-checked here against the
    current user before the handler runs — see `register()`.
    Shared systems should prefer result objects with a `cancelled` flag.
    """
    if not key:
        logger.debug("[result_router] empty route key ignored")
        return

    handler = _registry.get(key)
    if handler is None:
        logger.warning(f"[result_router] no handler registered for key={key!r}")
        return

    guard = _guards.get(key)
    if guard is not None:
        uid = update.effective_user.id if update and update.effective_user else 0
        try:
            allowed = bool(guard(uid))
        except Exception as exc:
            logger.error(f"[result_router] guard for key={key!r} raised: {exc}", exc_info=True)
            allowed = False   # fail-closed
        if not allowed:
            logger.warning(f"[result_router] guard rejected key={key!r} user={uid}")
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
