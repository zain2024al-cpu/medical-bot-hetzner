# shared/calendar_picker.py
# Shared inline calendar widget — pure view builder.
# Produces a month-grid inline keyboard so users can tap a date instead of typing.
#
# Usage in a flow:
#   from shared.calendar_picker import build_calendar
#   text, kb = build_calendar(year, month, callback_prefix="wca", back_callback="wca:start")
#
# Callback_data format produced:
#   {prefix}:cal_noop             — empty cell / header (no action)
#   {prefix}:cal_prev:{y}:{m}     — navigate to previous month
#   {prefix}:cal_next:{y}:{m}     — navigate to next month
#   {prefix}:cal_pick:{y}:{m}:{d} — user tapped a specific day
#
# Each flow handles these by checking action.startswith("cal_") in its dispatcher,
# then delegating to a _handle_cal_action(update, context, action) function.

import calendar

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

_AR_MONTHS: list[str] = [
    "", "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
]

# Monday-first column headers (ISO week: Mon=0 … Sun=6)
_DAY_HEADERS: list[str] = ["م", "ث", "أر", "خ", "ج", "س", "ح"]


def build_calendar(
    year: int,
    month: int,
    callback_prefix: str,
    back_callback: str,
    quick_jump: bool = False,
) -> tuple[str, InlineKeyboardMarkup]:
    """
    Return (prompt_text, inline_keyboard) for an interactive month calendar.

    callback_prefix  — flow prefix without trailing colon, e.g. "wca" or "hcfu"
    back_callback    — full callback_data for the ⬅️ رجوع button, e.g. "wca:start"
    quick_jump       — add ±1-year buttons and make the month/year label tappable
                       (opens the year picker). Off by default so every existing
                       caller keeps its current single-month stepping unchanged.

    Use quick_jump=True for far-future dates (passport / visa / residence
    expiry): stepping a month at a time to 2032 is ~96 taps, whereas
    year-picker → month-picker → day is three.

    The resulting keyboard is:
        Row 0 : [◀️]  [Month Year]  [▶️]     — navigation header
                (quick_jump adds Row 0b: [« سنة سابقة] [سنة تالية »])
        Row 1 : [م]  [ث]  [أر]  [خ]  [ج]  [س]  [ح]  — weekday labels
        Row 2+ : day numbers (empty cells are invisible noop buttons)
        Last  : [⬅️ رجوع]
    """
    noop = f"{callback_prefix}:cal_noop"

    # Previous / next month with year wrap
    prev_y = year if month > 1 else year - 1
    prev_m = month - 1 if month > 1 else 12
    next_y = year if month < 12 else year + 1
    next_m = month + 1 if month < 12 else 1

    month_label = f"{_AR_MONTHS[month]} {year}"

    rows: list[list[InlineKeyboardButton]] = []

    # ── Row 0: navigation ─────────────────────────────────────────────────────
    if quick_jump:
        # ⚠️ لا تحشر أزرار قفز السنة في نفس صف الشهر/السنة: 5 أزرار بجانب
        # بعضها تُضغِط عرض زر "الشهر السنة" حتى يختفي النص فعلياً على
        # شاشات الجوال (هذا هو سبب "لا يظهر أي سنة" الذي أبلغ عنه المستخدم،
        # وليس حد أحرف). الحل: صفّان منفصلان — صف الشهر بـ3 أزرار (نفس عرض
        # المسار العادي أدناه الذي يعمل بلا مشاكل)، وصف ثانٍ مخصص لقفز السنة.
        rows.append([
            InlineKeyboardButton(
                "◀️", callback_data=f"{callback_prefix}:cal_prev:{prev_y}:{prev_m}"
            ),
            # Tappable label → year picker (the entry point to the fast path)
            InlineKeyboardButton(
                month_label, callback_data=f"{callback_prefix}:cal_years:{year}"
            ),
            InlineKeyboardButton(
                "▶️", callback_data=f"{callback_prefix}:cal_next:{next_y}:{next_m}"
            ),
        ])
        rows.append([
            InlineKeyboardButton(
                "« سنة سابقة",
                callback_data=f"{callback_prefix}:cal_yprev:{year - 1}:{month}",
            ),
            InlineKeyboardButton(
                "سنة تالية »",
                callback_data=f"{callback_prefix}:cal_ynext:{year + 1}:{month}",
            ),
        ])
    else:
        rows.append([
            InlineKeyboardButton(
                "◀️", callback_data=f"{callback_prefix}:cal_prev:{prev_y}:{prev_m}"
            ),
            InlineKeyboardButton(month_label, callback_data=noop),
            InlineKeyboardButton(
                "▶️", callback_data=f"{callback_prefix}:cal_next:{next_y}:{next_m}"
            ),
        ])

    # ── Row 1: weekday column headers ─────────────────────────────────────────
    rows.append([InlineKeyboardButton(d, callback_data=noop) for d in _DAY_HEADERS])

    # ── Rows 2–7: day grid ────────────────────────────────────────────────────
    # calendar.monthcalendar() returns ISO weeks (Mon=0); 0 means empty cell.
    for week in calendar.monthcalendar(year, month):
        row: list[InlineKeyboardButton] = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data=noop))
            else:
                row.append(InlineKeyboardButton(
                    str(day),
                    callback_data=f"{callback_prefix}:cal_pick:{year}:{month}:{day}",
                ))
        rows.append(row)

    # ── Last row: back button ─────────────────────────────────────────────────
    rows.append([InlineKeyboardButton("⬅️ رجوع", callback_data=back_callback)])

    text = "📆 *اختر التاريخ*"
    return text, InlineKeyboardMarkup(rows)


# ── Fast path: year → month → day (for far-future expiry dates) ───────────────
# Only reachable from a calendar built with quick_jump=True.

_YEAR_PAGE_SIZE = 16   # 4 rows × 4 columns


def build_year_picker(
    base_year: int,
    callback_prefix: str,
    back_callback: str,
) -> tuple[str, InlineKeyboardMarkup]:
    """
    Grid of years starting at base_year, with page navigation.

    Callbacks produced:
        {prefix}:cal_yearpage:{y}  — show another block of years
        {prefix}:cal_setyear:{y}   — year chosen → month picker
    """
    rows: list[list[InlineKeyboardButton]] = []

    years = list(range(base_year, base_year + _YEAR_PAGE_SIZE))
    for i in range(0, len(years), 4):
        rows.append([
            InlineKeyboardButton(
                str(y), callback_data=f"{callback_prefix}:cal_setyear:{y}"
            )
            for y in years[i:i + 4]
        ])

    rows.append([
        InlineKeyboardButton(
            "◀️ أقدم",
            callback_data=f"{callback_prefix}:cal_yearpage:{base_year - _YEAR_PAGE_SIZE}",
        ),
        InlineKeyboardButton(
            "أحدث ▶️",
            callback_data=f"{callback_prefix}:cal_yearpage:{base_year + _YEAR_PAGE_SIZE}",
        ),
    ])
    rows.append([InlineKeyboardButton("⬅️ رجوع", callback_data=back_callback)])

    return "📆 *اختر السنة*", InlineKeyboardMarkup(rows)


def build_month_picker(
    year: int,
    callback_prefix: str,
    back_callback: str,
) -> tuple[str, InlineKeyboardMarkup]:
    """
    Grid of the 12 months for `year`.

    Callback produced:
        {prefix}:cal_setmonth:{y}:{m}  — month chosen → back to the day grid
    """
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(1, 13, 3):
        rows.append([
            InlineKeyboardButton(
                _AR_MONTHS[m],
                callback_data=f"{callback_prefix}:cal_setmonth:{year}:{m}",
            )
            for m in range(i, min(i + 3, 13))
        ])
    rows.append([InlineKeyboardButton("⬅️ رجوع", callback_data=back_callback)])

    return f"📆 *اختر الشهر — {year}*", InlineKeyboardMarkup(rows)
