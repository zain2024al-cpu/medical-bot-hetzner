# modules/healthcare/views.py
# Top-level views for the healthcare module.
# Owns the main healthcare menu that lists all 4 sub-modules.
# Sub-module views (woundcare, followup, medications, other) stay in their
# respective packages.

from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def parse_date_input(text: str) -> datetime | None:
    """
    Parse a user-typed date string into a datetime object.
    Accepts: DD/MM/YYYY · DD-MM-YYYY · YYYY-MM-DD
    Returns None if the string cannot be parsed.
    """
    text = (text or "").strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None
from shared.multiselect import Option
from shared.departments import get_department_options as _get_dept_opts
from modules.healthcare.daily_term import get_daily_term

# ── Callback prefix ───────────────────────────────────────────────────────────
HC = "hc"   # shared across the entire healthcare module

_DIVIDER = "━━━━━━━━━━━━━━━━━━━━"
_THIN    = "─────────────────────"

# ── Arabic month / weekday tables ─────────────────────────────────────────────
_MONTHS = [
    "", "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
]
_WEEKDAYS = [
    "الاثنين", "الثلاثاء", "الأربعاء", "الخميس",
    "الجمعة", "السبت", "الأحد",
]


def format_arabic_date(dt: datetime | None = None) -> str:
    """
    Return a human-readable Arabic date string.
    e.g.  "الأربعاء، 21 مايو 2026"
    Falls back to "" on any error.
    """
    try:
        if dt is None:
            dt = datetime.utcnow()
        weekday = _WEEKDAYS[dt.weekday()]
        month   = _MONTHS[dt.month]
        return f"{weekday}، {dt.day} {month} {dt.year}"
    except Exception:
        return ""


def format_arabic_datetime(iso_str: str) -> str:
    """
    Parse a stored ISO datetime string and return an Arabic date.
    Falls back gracefully on bad input.
    """
    if not iso_str:
        return format_arabic_date()
    try:
        dt = datetime.fromisoformat(iso_str)
        return format_arabic_date(dt)
    except Exception:
        return format_arabic_date()


def format_image_count(n: int) -> str:
    """
    Return an Arabic phrase for an attachment count.
    0  → لا توجد صور
    1  → صورة واحدة
    2+ → n صور
    """
    if n == 0:
        return "لا توجد صور"
    if n == 1:
        return "صورة واحدة"
    return f"{n} صور"


# ── Shared medical department options — sourced from the central registry ─────
# All healthcare flows (woundcare · medical_followup · medications) share this
# single list.  To add, remove, or rename a department edit shared/departments.py.
# ─────────────────────────────────────────────────────────────────────────────

DEPARTMENT_OPTIONS: list[Option] = _get_dept_opts()


# ── Healthcare main menu ──────────────────────────────────────────────────────

def build_healthcare_menu() -> tuple[str, InlineKeyboardMarkup]:
    """
    Full 4-item healthcare main menu.
    Triggered by pressing '🏥 الرعاية الصحية' on the reply keyboard.
    Includes today's rotating medical term at the bottom.
    """
    ar_term, en_term, ar_def = get_daily_term()
    text = (
        f"{_DIVIDER}\n"
        f"🏥  **الرعاية الصحية**\n\n"
        f"اختر القسم الصحي:\n\n"
        f"{_THIN}\n"
        f"📚 *مصطلح طبي اليوم*\n"
        f"*{ar_term}*  ·  _{en_term}_\n"
        f"{ar_def}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🩺 المجارحة والعناية بالجرح",          callback_data=f"{HC}:woundcare")],
        [InlineKeyboardButton("📋 المتابعة الطبية والإجراءات العلاجية", callback_data=f"{HC}:followup")],
        [InlineKeyboardButton("💊 صرف الأدوية",                       callback_data=f"{HC}:medications")],
        [InlineKeyboardButton("🏥 المستلزمات الطبية",                  callback_data=f"{HC}:supplies")],
        [InlineKeyboardButton("📝 إجراءات صحية أخرى",                  callback_data=f"{HC}:other")],
    ])
    return text, kb
