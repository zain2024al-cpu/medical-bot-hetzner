# core/access/__init__.py
# Central access-control layer public API.
#
# Single source of truth for all module-level access decisions.
# All handlers should call these functions; no scattered permission checks.

from .access_service import (
    resolve_tg_user_id,
    get_user_modules,
    user_has_module,
    grant_module,
    revoke_module,
    list_user_module_access,
)

__all__ = [
    "resolve_tg_user_id",
    "get_user_modules",
    "user_has_module",
    "grant_module",
    "revoke_module",
    "list_user_module_access",
]
