# core/routing/landing.py
# Centralized, role-aware landing-interface resolver.
#
# Called ONCE per /start invocation after the user has been confirmed to be
# approved and not suspended.  Returns the single role that controls which
# welcome screen and keyboard the user receives.
#
# Priority order
# ──────────────
#   admin  > translator > healthcare > public
#
# "translator" takes priority over "healthcare" so that users who have BOTH
# modules land on the translator interface (the primary role). They can still
# reach healthcare through the "▶️ ابدأ الآن" button in their reply keyboard.
#
# Architecture note
# ─────────────────
# This module lives in core/ and must NOT import from bot/.
# Admin detection uses config.settings.ADMIN_IDS directly (pure config).
# Module detection uses core.access.access_service (same layer).

import logging
from typing import Literal

logger = logging.getLogger(__name__)

# Canonical landing-role strings consumed by user_start.py and handle_start_main_menu.
LandingRole = Literal["admin", "healthcare", "translator", "public"]


def resolve_user_landing_interface(tg_user_id: int) -> LandingRole:
    """
    Return the single landing role for this Telegram user.

    Args:
        tg_user_id: Telegram numeric user ID.

    Returns:
        "admin"       — user is in ADMIN_IDS
        "translator"  — user has the user_reports module (with or without healthcare)
        "healthcare"  — user has ONLY the healthcare module
        "public"      — user has no active modules (pending / no access granted)

    Never raises — returns "public" on any unexpected error.
    """
    # ── Admin check ───────────────────────────────────────────────────────────
    try:
        from config.settings import ADMIN_IDS
        if tg_user_id in (ADMIN_IDS or []):
            return "admin"
    except Exception as exc:
        logger.warning(f"[landing] admin check failed for {tg_user_id}: {exc}")

    # ── Module check ─────────────────────────────────────────────────────────
    try:
        from core.access.access_service import get_user_modules
        modules = get_user_modules(tg_user_id)

        if "user_reports" in modules:
            # Translator (may also have healthcare — translator lands first).
            return "translator"

        if "healthcare" in modules:
            return "healthcare"

    except Exception as exc:
        logger.error(f"[landing] module check failed for {tg_user_id}: {exc}", exc_info=True)

    # ── Default: no active modules ────────────────────────────────────────────
    return "public"
