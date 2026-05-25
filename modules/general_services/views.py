# modules/general_services/views.py
# Shared display helpers + main GS menu builder.

from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

GS = "gs"

_DIVIDER = "━━━━━━━━━━━━━━━━━━━━"
_THIN    = "─────────────────────"
_NONE    = "➖ غير مضاف"

_MONTHS = [
    "", "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
]
_WEEKDAYS = [
    "الاثنين", "الثلاثاء", "الأربعاء", "الخميس",
    "الجمعة", "السبت", "الأحد",
]


def format_arabic_date(dt: datetime | None = None) -> str:
    try:
        if dt is None:
            dt = datetime.utcnow()
        weekday = _WEEKDAYS[dt.weekday()]
        month   = _MONTHS[dt.month]
        return f"{weekday}، {dt.day} {month} {dt.year}"
    except Exception:
        return ""


def format_arabic_datetime(iso_str: str) -> str:
    if not iso_str:
        return format_arabic_date()
    try:
        dt = datetime.fromisoformat(iso_str)
        return format_arabic_date(dt)
    except Exception:
        return format_arabic_date()


def format_image_count(n: int) -> str:
    if n == 0:
        return "لا توجد صور"
    if n == 1:
        return "صورة واحدة"
    return f"{n} صور"


def parse_date_input(text: str) -> datetime | None:
    text = (text or "").strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None


# ── Main GS menu ──────────────────────────────────────────────────────────────

def build_gs_menu() -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"{_DIVIDER}\n"
        f"🔧  **الخدمات العامة**\n\n"
        "اختر القسم:"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛬 الوصول",                callback_data=f"{GS}:arrivals")],
        [InlineKeyboardButton("🛫 المغادرة",              callback_data=f"{GS}:departures")],
        [InlineKeyboardButton("🧾 الخدمات العامة",        callback_data=f"{GS}:public_services")],
    ])
    return text, kb
