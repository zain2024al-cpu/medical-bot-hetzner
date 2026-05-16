"""
Shared UI primitives for the user-report selection flow.

These functions are pure and stateless — they take data in and return
keyboard fragments out. No context reads or writes happen here.

========================================================================
IDX SELECTOR PROTOCOL — ARCHITECTURAL DOCTRINE
========================================================================

Any selector that emits  {type}_idx:{n}  callback buttons MUST follow
this three-rule protocol:

  1. SNAPSHOT AT RENDER TIME
     Store the full ordered list in report_tmp (not bare user_data) before
     emitting IDX buttons.  Key naming convention: {type}s_list
     (e.g. hospitals_list, departments_list, _doctors_list, _patient_names_list).

  2. DETECT SNAPSHOT LOSS AT CONSUME TIME
     In the callback consumer, check  `if not snapshot_list`  BEFORE
     attempting IDX resolution.  A missing snapshot means PM2 restarted
     and user_data was cleared — the stale button is now a dead reference.

  3. RE-RENDER, NEVER REBUILD-AND-RESOLVE
     When the snapshot is missing: call the selector's render function
     directly and return the same state.  Do NOT fetch a fresh live list
     and resolve the stale IDX into it — that is drift injection and can
     silently produce the wrong selection if list order changed.

     When the snapshot is present but the index is out of bounds: emit an
     error alert (the index itself is corrupt, not just the session state).

     Cascaded selectors (subdepartment depends on main_department): if the
     immediate snapshot is missing, check the parent context key; if the
     parent is present, re-render the child screen; if both are missing,
     re-render the grandparent screen.

Recovery implementations:
  hospital      → render_hospital_selection()        (B-DA.5.2a)
  doctor        → render_doctor_selection()           (B-DA.5.1a)
  patient       → show_patient_list(update, ctx, 0)  (Phase 4a)
  department    → render_department_selection()       (Phase 4c)
  subdepartment → show_subdepartment_options() or
                  render_department_selection()       (Phase 4c, cascaded)
========================================================================
"""

from telegram import InlineKeyboardButton
from typing import List, Tuple

# ─── حدود الطول لتقرير عرض الزر (حرف) ───────────────────────────
_SINGLE_THRESHOLD = 22   # اسم أطول من هذا → صف منفرد
_DISPLAY_TRUNCATE = 28   # حد اقتطاع النص داخل الزر


def progress_bar(current: int, total: int, filled: str = "●", empty: str = "○") -> str:
    """يبني شريط تقدم نقطي.  مثال:  ● ● ● ○ ○  الخطوة 3 من 5"""
    bar = " ".join(filled if i < current else empty for i in range(total))
    return f"{bar}  الخطوة {current} من {total}"


def screen_header(icon: str, title: str, step: int, total_steps: int,
                  count: int = 0, count_label: str = "",
                  page: int = 0, total_pages: int = 1,
                  context_line: str = "") -> str:
    """
    يبني نص الشاشة الموحّد:
      ● ● ● ○ ○  الخطوة 3 من 5
      ━━━━━━━━━━━━━━━━━━━━
      🏥  اختيار المستشفى

      [بطاقة السياق إن وُجدت]
      📋 32 مستشفى  │  صفحة 1 من 4
      ─────────────────────
      اختر من القائمة:
    """
    lines = []
    lines.append(progress_bar(step, total_steps))
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"{icon}  **{title}**")
    if context_line:
        lines.append("")
        lines.append(context_line)
    lines.append("")
    meta_parts = []
    if count and count_label:
        meta_parts.append(f"📋 {count} {count_label}")
    if total_pages > 1:
        meta_parts.append(f"صفحة {page + 1} من {total_pages}")
    if meta_parts:
        lines.append("  │  ".join(meta_parts))
    lines.append("─────────────────────")
    lines.append("اختر من القائمة:")
    return "\n".join(lines)


def smart_rows(items: list, make_button) -> list:
    """
    يحوّل قائمة عناصر إلى صفوف ذكية:
    - الاسم الطويل (> _SINGLE_THRESHOLD) → صف منفرد
    - الأسماء القصيرة → اثنان في صف واحد

    make_button(item) → InlineKeyboardButton
    """
    rows = []
    pending = None
    for item in items:
        label = item if isinstance(item, str) else item.get("name", str(item))
        btn = make_button(item)
        if len(label) > _SINGLE_THRESHOLD:
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


def paginate(items: list, page: int, per_page: int) -> Tuple[list, int, int]:
    """
    Slice *items* to one page and return the page slice, the clamped page
    number, and the total page count.

    Returns: (page_items, clamped_page, total_pages)
    """
    total = len(items)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    end = min(start + per_page, total)
    return items[start:end], page, total_pages


def pagination_buttons(page: int, total_pages: int, prefix: str) -> List[InlineKeyboardButton]:
    """
    Build the standard [← prev | counter | next →] navigation row.

    Returns an empty list when there is only one page (caller should not
    append an empty row to the keyboard).

    *prefix* is the callback_data prefix, e.g. "hosp_page", "dept_page",
    "subdept_page".  Buttons emit "{prefix}:{page_number}".
    """
    if total_pages <= 1:
        return []
    row = []
    if page > 0:
        row.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"{prefix}:{page - 1}"))
    row.append(InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        row.append(InlineKeyboardButton("➡️ التالي", callback_data=f"{prefix}:{page + 1}"))
    return row
