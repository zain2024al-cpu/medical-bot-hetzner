# shared/ui_primitives.py
# Pure, stateless view helpers shared across all platform modules.
#
# No context reads, no database calls, no I/O — only data-in / UI-out.
# Safe to call from any thread.

from telegram import InlineKeyboardButton
from typing import Any, Callable, List, Tuple

# ── Name-length thresholds ────────────────────────────────────────────────────
_SINGLE_ROW_THRESHOLD = 22   # names longer than this get their own row
_DISPLAY_TRUNCATE     = 28   # hard cap for button label length


# ── Progress / headers ────────────────────────────────────────────────────────

def progress_bar(current: int, total: int,
                 filled: str = "●", empty: str = "○") -> str:
    """Dotted progress indicator.  Example:  ● ● ● ○ ○  الخطوة 3 من 5"""
    bar = " ".join(filled if i < current else empty for i in range(total))
    return f"{bar}  الخطوة {current} من {total}"


def screen_header(
    icon: str,
    title: str,
    step: int,
    total_steps: int,
    count: int = 0,
    count_label: str = "",
    page: int = 0,
    total_pages: int = 1,
    context_line: str = "",
) -> str:
    """
    Uniform screen header used by all selectors.

    Output:
        ● ● ● ○ ○  الخطوة 3 من 6
        ━━━━━━━━━━━━━━━━━━━━
        👤  **اختيار المريض**

        [context_line if provided]
        📋 45 مريض  │  صفحة 2 من 5
        ─────────────────────
        اختر من القائمة:
    """
    lines = [
        progress_bar(step, total_steps),
        "━━━━━━━━━━━━━━━━━━━━",
        f"{icon}  **{title}**",
    ]
    if context_line:
        lines += ["", context_line]
    lines.append("")

    meta = []
    if count and count_label:
        meta.append(f"📋 {count} {count_label}")
    if total_pages > 1:
        meta.append(f"صفحة {page + 1} من {total_pages}")
    if meta:
        lines.append("  │  ".join(meta))

    lines += ["─────────────────────", "اختر من القائمة:"]
    return "\n".join(lines)


# ── Smart row layout ──────────────────────────────────────────────────────────

def smart_rows(items: list, make_button: Callable[[Any], InlineKeyboardButton]) -> list:
    """
    Build keyboard rows from a list of items:
    - Long labels (> _SINGLE_ROW_THRESHOLD chars) → one button per row
    - Short labels → two buttons per row

    make_button(item) must return InlineKeyboardButton.
    """
    rows: list = []
    pending = None
    for item in items:
        label = item if isinstance(item, str) else item.get("name", str(item))
        btn = make_button(item)
        if len(label) > _SINGLE_ROW_THRESHOLD:
            if pending is not None:
                rows.append([pending])
                pending = None
            rows.append([btn])
        else:
            if pending is None:
                pending = btn
            else:
                rows.append([pending, btn])
                pending = None
    if pending is not None:
        rows.append([pending])
    return rows


# ── Pagination ────────────────────────────────────────────────────────────────

def paginate(items: list, page: int, per_page: int) -> Tuple[list, int, int]:
    """
    Slice items to a single page.

    Returns:
        (page_items, clamped_page_number, total_pages)
    """
    total = len(items)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    return items[start : start + per_page], page, total_pages


def pagination_buttons(
    page: int,
    total_pages: int,
    prefix: str,
) -> List[InlineKeyboardButton]:
    """
    Standard [← prev | counter | next →] navigation row.

    Returns an empty list when there is only one page (do not append an
    empty row to the keyboard).

    prefix: callback_data prefix, e.g. "sel_pat:list" → emits "sel_pat:list:2"
    """
    if total_pages <= 1:
        return []
    row: List[InlineKeyboardButton] = []
    if page > 0:
        row.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"{prefix}:{page - 1}"))
    row.append(InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        row.append(InlineKeyboardButton("➡️ التالي", callback_data=f"{prefix}:{page + 1}"))
    return row
