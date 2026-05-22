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
) -> tuple[str, InlineKeyboardMarkup]:
    """
    Return (prompt_text, inline_keyboard) for an interactive month calendar.

    callback_prefix  — flow prefix without trailing colon, e.g. "wca" or "hcfu"
    back_callback    — full callback_data for the ⬅️ رجوع button, e.g. "wca:start"

    The resulting keyboard is:
        Row 0 : [◀️]  [Month Year]  [▶️]     — navigation header
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
