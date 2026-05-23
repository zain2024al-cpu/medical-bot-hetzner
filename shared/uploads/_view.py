# shared/uploads/_view.py
# Pure view builders for the upload collector.
# No database, no context, no I/O — data in, (text, keyboard) out.

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

CB           = "upl"
_MAX_SHOWN   = 8    # max file rows shown in the collecting screen
_DIVIDER     = "━━━━━━━━━━━━━━━━━━━━"
_THIN        = "─────────────────────"


# ── Waiting screen (0 files collected) ───────────────────────────────────────

def build_waiting(session_dict: dict) -> tuple[str, InlineKeyboardMarkup]:
    """
    Initial screen before any files are sent.
    """
    title   = session_dict["title"]
    icon    = session_dict.get("icon", "📎")
    min_f   = session_dict.get("min_files", 0)
    max_f   = session_dict.get("max_files", 0)
    allowed = session_dict.get("allowed_types", [])

    type_str    = _type_labels(allowed)
    constraints = _constraints_hint(min_f, max_f)

    lines = [
        _DIVIDER,
        f"{icon}  **{title}**",
    ]
    if constraints:
        lines += ["", constraints]
    lines += [
        "",
        f"📤 أرسل {type_str} الآن.",
        _THIN,
    ]
    text = "\n".join(lines)

    # When min_files=0 the step is optional — show a skip button so the user
    # can proceed without uploading anything.
    if min_f == 0:
        rows = [
            [
                InlineKeyboardButton("⏭️ تخطي",  callback_data=f"{CB}:confirm"),
                InlineKeyboardButton("❌ إلغاء", callback_data=f"{CB}:cancel"),
            ]
        ]
    else:
        rows = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"{CB}:cancel")]]
    return text, InlineKeyboardMarkup(rows)


# ── Collecting screen (1+ files) ─────────────────────────────────────────────

def build_collecting(
    session_dict: dict,
    files: list[dict],
) -> tuple[str, InlineKeyboardMarkup]:
    """
    Screen shown while files accumulate.

    files — list of UploadedFile.to_dict()  (already collected)
    Each file appears as a [🗑️ label (size)] delete button.
    Files beyond _MAX_SHOWN are listed as a count (no delete button).
    """
    title = session_dict["title"]
    icon  = session_dict.get("icon", "📎")
    min_f = session_dict.get("min_files", 0)
    max_f = session_dict.get("max_files", 0)

    count       = len(files)
    constraints = _constraints_hint(min_f, max_f)

    lines = [
        _DIVIDER,
        f"{icon}  **{title}**",
    ]
    if constraints:
        lines += ["", constraints]
    lines.append("")

    if max_f > 0:
        lines.append(f"✅ {count} / {max_f} ملفات محددة")
    else:
        lines.append(f"✅ {count} ملفات محددة")

    # Overflow note
    overflow = count - _MAX_SHOWN
    if overflow > 0:
        lines.append(f"   (يُعرض {_MAX_SHOWN} من {count} — أرسل المزيد أو تأكد)")

    lines.append("")
    lines.append("أرسل المزيد أو اضغط تأكيد.")
    lines.append(_THIN)

    text = "\n".join(lines)

    rows: list = []

    # File rows — each is a delete button
    shown = files[:_MAX_SHOWN]
    for idx, f in enumerate(shown):
        label    = f.get("file_name") or _mime_label(f.get("mime_type", ""))
        size_str = _size_label(f.get("file_size", 0))
        btn_text = f"🗑️ {label} ({size_str})"
        if len(btn_text) > 40:
            btn_text = btn_text[:38] + "…"
        rows.append([InlineKeyboardButton(btn_text, callback_data=f"{CB}:rm:{idx}")])

    # Counter noop
    if max_f > 0:
        counter_text = f"📎 {count} / {max_f}"
    else:
        counter_text = f"📎 {count} ملفات"
    rows.append([InlineKeyboardButton(counter_text, callback_data=f"{CB}:noop")])

    # Confirm / Cancel
    confirm_label = f"✅ تأكيد ({count})"
    rows.append([
        InlineKeyboardButton(confirm_label, callback_data=f"{CB}:confirm"),
        InlineKeyboardButton("❌ إلغاء",    callback_data=f"{CB}:cancel"),
    ])

    return text, InlineKeyboardMarkup(rows)


# ── Min-files warning ─────────────────────────────────────────────────────────

def build_min_warning(
    session_dict: dict,
    files:        list[dict],
    min_files:    int,
) -> tuple[str, InlineKeyboardMarkup]:
    base_text, kb = (
        build_collecting(session_dict, files) if files
        else build_waiting(session_dict)
    )
    warning = f"⚠️ يجب رفع {min_files} {'ملف' if min_files == 1 else 'ملفات'} على الأقل.\n\n"
    return warning + base_text, kb


# ── Error / session-lost screens ─────────────────────────────────────────────

def build_session_lost() -> tuple[str, InlineKeyboardMarkup]:
    text = (
        "⚠️ **انتهت الجلسة**\n\n"
        "انتهت مهلة الجلسة أو أُعيد تشغيل النظام.\n"
        "يرجى بدء العملية من جديد."
    )
    return text, InlineKeyboardMarkup([])


def build_error(message: str = "") -> tuple[str, InlineKeyboardMarkup]:
    body = message or "حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى."
    text = f"❌ **خطأ**\n\n{body}"
    kb   = InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{CB}:cancel"),
    ]])
    return text, kb


# ── Private helpers ───────────────────────────────────────────────────────────

def _size_label(file_size: int) -> str:
    if file_size <= 0:
        return "—"
    kb = file_size / 1024
    if kb < 1024:
        return f"{kb:.0f} KB"
    return f"{kb / 1024:.1f} MB"


def _mime_label(mime_type: str) -> str:
    if mime_type == "application/pdf":
        return "PDF"
    if mime_type.startswith("image/"):
        return "صورة"
    if mime_type:
        return mime_type.split("/")[-1].upper()
    return "صورة"   # compressed Telegram photo (no mime stored)


def _type_labels(allowed_types: list[str]) -> str:
    parts = []
    if "photo" in allowed_types:
        parts.append("الصور")
    if "pdf" in allowed_types:
        parts.append("ملفات PDF")
    if "image_document" in allowed_types and "photo" not in allowed_types:
        parts.append("الصور (ملفات)")
    if (
        "document" in allowed_types
        and "pdf" not in allowed_types
        and "image_document" not in allowed_types
    ):
        parts.append("المستندات")
    return " أو ".join(parts) if parts else "الملفات"


def _constraints_hint(min_f: int, max_f: int) -> str:
    if min_f > 0 and max_f > 0:
        return f"من {min_f} إلى {max_f} ملفات"
    if min_f > 0:
        return f"{min_f} {'ملف' if min_f == 1 else 'ملفات'} على الأقل"
    if max_f > 0:
        return f"الحد الأقصى {max_f} ملفات"
    return ""
