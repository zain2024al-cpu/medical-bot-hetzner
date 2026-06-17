# core/access/access_service.py
# Module activation access service — the single source of truth for all
# module-level access decisions.
#
# Design rules:
#   - All public functions take tg_user_id (Telegram user ID), not DB row id.
#   - All DB access is wrapped in try/except; failures return safe defaults.
#   - Lazy migration: approved translators with no access records are silently
#     granted "user_reports" on their first access check, keeping production
#     working with zero downtime.
#   - No module name is hardcoded outside this file and modules_bootstrap.py.

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# The default module granted to every approved translator who has no records yet.
# Matches the `name` used in core/modules_bootstrap.py.
_DEFAULT_TRANSLATOR_MODULE = "user_reports"


# ── Public API ────────────────────────────────────────────────────────────────

def resolve_tg_user_id(entity) -> int | None:
    """
    Resolve the Telegram identity used by RBAC from a user-like row.

    Current platform users store it in users.tg_user_id. Legacy translator
    directory rows store the same Telegram id in translators.translator_id.
    """
    if entity is None:
        return None

    for attr in ("tg_user_id", "chat_id", "translator_id"):
        value = getattr(entity, attr, None)
        if isinstance(value, int) and value > 0:
            return value

    return None

def get_user_modules(tg_user_id: int) -> list[str]:
    """
    Return ordered list of active module keys for this user.

    Lazy migration: if the user is an approved, non-suspended translator with
    no module access records, they are silently granted _DEFAULT_TRANSLATOR_MODULE
    and it is persisted to the DB on the spot.
    """
    try:
        from db.session import SessionLocal
        from db.models import UserModuleAccess, Translator, TranslatorDirectory

        with SessionLocal() as s:
            records = (
                s.query(UserModuleAccess)
                .filter_by(tg_user_id=tg_user_id, is_active=True)
                .order_by(UserModuleAccess.granted_at)
                .all()
            )

            if records:
                return [r.module_key for r in records]

            # No records — check if user is an approved platform user.
            user = s.query(Translator).filter_by(tg_user_id=tg_user_id).first()
            if user and getattr(user, "is_approved", False) and not getattr(user, "is_suspended", False):
                _insert_access(s, tg_user_id, _DEFAULT_TRANSLATOR_MODULE, granted_by=None)
                s.commit()
                logger.info(
                    f"[access] lazy-migrated tg_user_id={tg_user_id} "
                    f"→ module={_DEFAULT_TRANSLATOR_MODULE!r}"
                )
                return [_DEFAULT_TRANSLATOR_MODULE]

            if user:
                return []

            # Legacy production compatibility: the translators directory stores
            # Telegram user ids in translator_id for established translators.
            directory_user = (
                s.query(TranslatorDirectory)
                .filter_by(translator_id=tg_user_id)
                .first()
            )
            if directory_user:
                _insert_access(s, tg_user_id, _DEFAULT_TRANSLATOR_MODULE, granted_by=None)
                s.commit()
                logger.info(
                    f"[access] lazy-migrated legacy translator_id={tg_user_id} "
                    f"→ module={_DEFAULT_TRANSLATOR_MODULE!r}"
                )
                return [_DEFAULT_TRANSLATOR_MODULE]

        return []
    except Exception as exc:
        logger.error(f"[access] get_user_modules({tg_user_id}) failed: {exc}", exc_info=True)
        return []


def user_has_module(tg_user_id: int, module_key: str) -> bool:
    """Return True if the user has active access to this module."""
    return module_key in get_user_modules(tg_user_id)


def grant_module(tg_user_id: int, module_key: str, granted_by: int | None = None) -> bool:
    """
    Grant a module to a user.

    Returns True if the grant changed state (new grant or re-activation).
    Returns False if the module was already active (no-op).
    """
    try:
        from db.session import SessionLocal
        from db.models import UserModuleAccess
        from sqlalchemy.exc import IntegrityError

        with SessionLocal() as s:
            existing = (
                s.query(UserModuleAccess)
                .filter_by(tg_user_id=tg_user_id, module_key=module_key)
                .first()
            )

            if existing:
                if existing.is_active:
                    return False  # Already active — nothing to do
                # Re-activate a previously revoked record
                existing.is_active = True
                existing.granted_by = granted_by
                existing.granted_at = datetime.utcnow()
                existing.revoked_by = None
                existing.revoked_at = None
            else:
                _insert_access(s, tg_user_id, module_key, granted_by)

            try:
                s.commit()
            except IntegrityError:
                # Race condition: a concurrent call inserted the row between our
                # SELECT and INSERT. Roll back and activate the existing record.
                s.rollback()
                s.query(UserModuleAccess).filter_by(
                    tg_user_id=tg_user_id, module_key=module_key
                ).update({
                    "is_active": True,
                    "granted_by": granted_by,
                    "granted_at": datetime.utcnow(),
                    "revoked_by": None,
                    "revoked_at": None,
                })
                s.commit()
                logger.info(
                    f"[access] grant_module recovered from race condition "
                    f"module={module_key!r} tg_user_id={tg_user_id}"
                )

            logger.info(
                f"[access] granted module={module_key!r} "
                f"to tg_user_id={tg_user_id} by admin={granted_by}"
            )
            return True
    except Exception as exc:
        logger.error(f"[access] grant_module failed: {exc}", exc_info=True)
        return False


def revoke_module(tg_user_id: int, module_key: str, revoked_by: int | None = None) -> bool:
    """
    Revoke a module from a user.

    Returns True if the record was found and deactivated.
    Returns False if there was no active record to revoke.
    """
    try:
        from db.session import SessionLocal
        from db.models import UserModuleAccess

        with SessionLocal() as s:
            record = (
                s.query(UserModuleAccess)
                .filter_by(tg_user_id=tg_user_id, module_key=module_key, is_active=True)
                .first()
            )
            if not record:
                return False

            record.is_active = False
            record.revoked_by = revoked_by
            record.revoked_at = datetime.utcnow()
            s.commit()
            logger.info(
                f"[access] revoked module={module_key!r} "
                f"from tg_user_id={tg_user_id} by admin={revoked_by}"
            )
            return True
    except Exception as exc:
        logger.error(f"[access] revoke_module failed: {exc}", exc_info=True)
        return False


def list_user_module_access(tg_user_id: int) -> list[dict]:
    """
    Return all module access records for a user (both active and revoked).
    Useful for admin inspection.
    """
    try:
        from db.session import SessionLocal
        from db.models import UserModuleAccess

        with SessionLocal() as s:
            records = (
                s.query(UserModuleAccess)
                .filter_by(tg_user_id=tg_user_id)
                .order_by(UserModuleAccess.granted_at)
                .all()
            )
            return [
                {
                    "module_key": r.module_key,
                    "is_active": r.is_active,
                    "granted_by": r.granted_by,
                    "granted_at": r.granted_at,
                    "revoked_by": r.revoked_by,
                    "revoked_at": r.revoked_at,
                }
                for r in records
            ]
    except Exception as exc:
        logger.error(f"[access] list_user_module_access failed: {exc}", exc_info=True)
        return []


# ── Internal helpers ──────────────────────────────────────────────────────────

def _insert_access(session, tg_user_id: int, module_key: str, granted_by: int | None) -> None:
    """Insert a new active access record into an open SQLAlchemy session (no commit)."""
    from db.models import UserModuleAccess

    record = UserModuleAccess(
        tg_user_id=tg_user_id,
        module_key=module_key,
        granted_by=granted_by,
        granted_at=datetime.utcnow(),
        is_active=True,
    )
    session.add(record)
