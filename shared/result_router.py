# shared/result_router.py
# Neutral re-export of the shared completion handler registry.
#
# Both shared/selectors/ and shared/multiselect/ import from here so that
# neither package depends on the other.  The canonical implementation lives
# in shared/selectors/result_router.py; this shim keeps import paths clean.

from shared.selectors.result_router import (  # noqa: F401
    register,
    route,
    registered_keys,
    ResultHandler,
)

__all__ = ["register", "route", "registered_keys", "ResultHandler"]
