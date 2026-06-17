# modules/residency/views.py
# Shared display helpers for the residency module.

from datetime import datetime
from modules.residency.constants import RESIDENCY_STATUS_LABELS, RESIDENCY_STATUS_ICONS

_DIVIDER = "━━━━━━━━━━━━━━━━━━━━"
_THIN    = "─────────────────────"
_NONE    = "—"


def format_status(status: str) -> str:
    """Return Arabic label for a residency status key."""
    return RESIDENCY_STATUS_LABELS.get(status, status or _NONE)


def format_status_icon(status: str) -> str:
    """Return emoji icon for a residency status key."""
    return RESIDENCY_STATUS_ICONS.get(status, "•")


def _parse_expiry_date(expiry_date: str):
    """
    Try to parse a date string in either YYYY-MM-DD or DD/MM/YYYY format.
    Returns a datetime.date object or None.
    """
    if not expiry_date:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(expiry_date[:10], fmt).date()
        except Exception:
            continue
    return None


def format_expiry_date(expiry_date: str) -> str:
    """
    Return a human-readable date string: DD/MM/YYYY
    Accepts ISO format YYYY-MM-DD or legacy DD/MM/YYYY.
    """
    if not expiry_date:
        return _NONE
    dt = _parse_expiry_date(expiry_date)
    if dt is None:
        return expiry_date          # fallback: show raw value
    return f"{dt.day:02d}/{dt.month:02d}/{dt.year}"


def format_days_remaining(expiry_date: str) -> str:
    """
    Return Arabic string for days remaining until expiry.
    Accepts ISO format YYYY-MM-DD or legacy DD/MM/YYYY.
    Negative = already expired.
    """
    if not expiry_date:
        return _NONE
    expiry = _parse_expiry_date(expiry_date)
    if expiry is None:
        return _NONE
    today = datetime.utcnow().date()
    delta = (expiry - today).days
    if delta < 0:
        return f"انتهت منذ {abs(delta)} يوم"
    if delta == 0:
        return "تنتهي اليوم ⚠️"
    if delta == 1:
        return "يوم واحد متبقٍ 🔴"
    if delta <= 7:
        return f"{delta} أيام متبقية 🔴"
    if delta <= 30:
        return f"{delta} يوم متبقٍ ⚠️"
    return f"{delta} يوم متبقٍ"


def format_expiry_warning_inline(expiry_date: str) -> str:
    """Short inline warning label — empty if more than 30 days remaining."""
    if not expiry_date:
        return ""
    try:
        expiry = datetime.strptime(expiry_date[:10], "%Y-%m-%d").date()
        today  = datetime.utcnow().date()
        delta  = (expiry - today).days
        if delta < 0:
            return " ❌"
        if delta <= 7:
            return f" 🔴({delta}د)"
        if delta <= 30:
            return f" ⚠️({delta}د)"
        return ""
    except Exception:
        return ""


def doc_icon(file_id: str) -> str:
    """Return ✅ if file_id is set, ⬜ otherwise."""
    return "✅" if file_id else "⬜"
