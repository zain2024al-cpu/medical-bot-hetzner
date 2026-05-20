# shared/selectors/patient_selector/_view.py
# Pure view builders — data in, (text, InlineKeyboardMarkup) out.
# No database, no context, no I/O.

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from shared.ui_primitives import smart_rows, paginate, pagination_buttons, screen_header

CB   = "sel_pat"          # callback prefix used by selector.py
PER_PAGE = 10             # patient names per page


# ── Screen texts ──────────────────────────────────────────────────────────────

def _list_header(total: int, page: int, total_pages: int, search_query: str) -> str:
    label   = f"نتائج البحث: «{search_query}»" if search_query else "قائمة المرضى"
    context = f"\U0001f50d فلتر: {search_query}" if search_query else ""
    return screen_header(
        icon="👤",
        title=label,
        step=1,
        total_steps=1,
        count=total,
        count_label="مريض",
        page=page,
        total_pages=total_pages,
        context_line=context,
    )


# ── View builders ─────────────────────────────────────────────────────────────

def build_list(
    names: list[str],
    page: int,
    search_query: str = "",
    back_label: str = "🔙 رجوع",
) -> tuple[str, InlineKeyboardMarkup]:
    """
    Build the paginated patient list screen.

    names       — full ordered snapshot (all pages combined)
    page        — requested page number (0-based, will be clamped)
    search_query — shown in header when non-empty
    back_label  — text for the back button

    Returns (message_text, keyboard).
    """
    page_names, page, total_pages = paginate(names, page, PER_PAGE)
    total = len(names)
    start_idx = page * PER_PAGE

    # Patient selection buttons — smart 2-per-row layout
    rows = smart_rows(
        [{"name": n, "_idx": start_idx + i} for i, n in enumerate(page_names)],
        lambda item: InlineKeyboardButton(
            f"👤 {item['name']}",
            callback_data=f"{CB}:idx:{item['_idx']}",
        ),
    )

    # Pagination row
    nav = pagination_buttons(page, total_pages, prefix=f"{CB}:list")
    if nav:
        rows.append(nav)

    # Search + back row
    rows.append([
        InlineKeyboardButton("🔍 بحث", switch_inline_query_current_chat=""),
        InlineKeyboardButton(back_label, callback_data=f"{CB}:back"),
    ])

    text = _list_header(total, page, total_pages, search_query)
    return text, InlineKeyboardMarkup(rows)


def build_empty(search_query: str = "") -> tuple[str, InlineKeyboardMarkup]:
    """Screen shown when no patients match the current filter."""
    if search_query:
        text = (
            f"\U0001f50d **لا توجد نتائج لـ"
            f" «{search_query}»**\n\n"
            "جرّب كلمة بحث"
            " مختلفة أو اعرض"
            " القائمة الكاملة."
        )
    else:
        text = "⚠️ **لا يوجد مرضى في قاعدة البيانات.**"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data=f"{CB}:back")],
    ])
    return text, keyboard


def build_confirmation(name: str) -> tuple[str, InlineKeyboardMarkup]:
    """
    Brief confirmation screen shown immediately after the user picks a patient.
    The calling module replaces this with its own next-step screen.
    """
    text = f"✅ **تم اختيار المريض**\n\n👤 {name}"
    keyboard = InlineKeyboardMarkup([])
    return text, keyboard


def build_error(message: str = "") -> tuple[str, InlineKeyboardMarkup]:
    """Fallback screen for unexpected errors."""
    body = message or "حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى."
    text = f"❌ **خطأ**\n\n{body}"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data=f"{CB}:back")],
    ])
    return text, keyboard
