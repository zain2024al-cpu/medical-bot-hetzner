# shared/multiselect/_view.py
# Pure view builders for the multiselect engine.
# No database, no context, no I/O — data in, (text, keyboard) out.

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from shared.ui_primitives import paginate, pagination_buttons, screen_header

CB       = "msel"       # callback prefix  — must match engine.py
PER_PAGE = 8            # options per page (one per row → 8 rows of options)

# ── Selection screen ──────────────────────────────────────────────────────────

def build_selection(
    state_dict: dict,
    selected_ids: set,
) -> tuple[str, InlineKeyboardMarkup]:
    """
    Build the main multi-select screen.

    state_dict  — raw session dict with keys: title, icon, options, page,
                  min_select, max_select
    selected_ids — current set of selected option ids

    Returns (message_text, keyboard).
    """
    options    = state_dict["options"]      # list[dict]
    page       = state_dict["page"]
    min_sel    = state_dict.get("min_select", 0)
    max_sel    = state_dict.get("max_select", 0)
    title      = state_dict["title"]
    icon       = state_dict.get("icon", "☑️")

    total_opts   = len(options)
    selected_cnt = len(selected_ids)

    page_opts, page, total_pages = paginate(options, page, PER_PAGE)
    start_idx = page * PER_PAGE

    # ── Option toggle rows (one per row) ──────────────────────────────────────
    rows: list = []
    for i, opt in enumerate(page_opts):
        idx        = start_idx + i
        is_sel     = opt["id"] in selected_ids
        prefix     = "✅ " if is_sel else "☐  "
        opt_icon   = opt.get("icon", "")
        body       = f"{opt_icon} {opt['label']}" if opt_icon else opt["label"]
        label      = prefix + body
        if len(label) > 35:
            label = label[:33] + "…"
        rows.append([
            InlineKeyboardButton(label, callback_data=f"{CB}:tog:{idx}")
        ])

    # ── Pagination row ────────────────────────────────────────────────────────
    nav = pagination_buttons(page, total_pages, prefix=f"{CB}:page")
    if nav:
        rows.append(nav)

    # ── Selection counter (non-interactive) ───────────────────────────────────
    if max_sel > 0:
        counter_text = f"✅ {selected_cnt} / {max_sel} مختار"
    else:
        counter_text = f"✅ {selected_cnt} مختار"
    rows.append([InlineKeyboardButton(counter_text, callback_data=f"{CB}:noop")])

    # ── Confirm / Cancel row ──────────────────────────────────────────────────
    confirm_label = _confirm_label(selected_cnt, min_sel)
    rows.append([
        InlineKeyboardButton(confirm_label, callback_data=f"{CB}:confirm"),
        InlineKeyboardButton("❌ إلغاء",     callback_data=f"{CB}:cancel"),
    ])

    # ── Header text ───────────────────────────────────────────────────────────
    context_line = _constraints_hint(min_sel, max_sel)
    text = screen_header(
        icon=icon,
        title=title,
        step=selected_cnt if selected_cnt else 1,
        total_steps=max(total_opts, 1),
        count=total_opts,
        count_label="خيار",
        page=page,
        total_pages=total_pages,
        context_line=context_line,
    )

    return text, InlineKeyboardMarkup(rows)


# ── Validation warning ────────────────────────────────────────────────────────

def build_min_warning(
    state_dict: dict,
    selected_ids: set,
    min_select: int,
) -> tuple[str, InlineKeyboardMarkup]:
    """
    Re-render selection screen with a warning that minimum is not yet met.
    The warning is prepended to the normal header.
    """
    text, kb = build_selection(state_dict, selected_ids)
    warning = (
        f"⚠️ يجب اختيار {min_select} على الأقل.\n\n"
    )
    return warning + text, kb


# ── Error / session-lost screen ───────────────────────────────────────────────

def build_session_lost() -> tuple[str, InlineKeyboardMarkup]:
    """Shown when session state cannot be recovered."""
    text = (
        "⚠️ **انتهت الجلسة**\n\n"
        "انتهت مهلة الجلسة أو أُعيد تشغيل النظام.\n"
        "يرجى بدء العملية من جديد."
    )
    keyboard = InlineKeyboardMarkup([])
    return text, keyboard


def build_error(message: str = "") -> tuple[str, InlineKeyboardMarkup]:
    body = message or "حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى."
    text = f"❌ **خطأ**\n\n{body}"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"{CB}:cancel")],
    ])
    return text, keyboard


# ── Private helpers ───────────────────────────────────────────────────────────

def _confirm_label(selected_cnt: int, min_sel: int) -> str:
    if selected_cnt == 0:
        return "✅ تأكيد"
    return f"✅ تأكيد ({selected_cnt})"


def _constraints_hint(min_sel: int, max_sel: int) -> str:
    if min_sel > 0 and max_sel > 0:
        return f"اختر من {min_sel} إلى {max_sel} خيارات"
    if min_sel > 0:
        return f"اختر {min_sel} على الأقل"
    if max_sel > 0:
        return f"الحد الأقصى {max_sel} خيارات"
    return ""
