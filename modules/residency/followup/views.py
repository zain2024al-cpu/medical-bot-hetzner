# modules/residency/followup/views.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from modules.residency.views import (
    format_status_icon, format_expiry_date, format_days_remaining,
    _DIVIDER, _THIN, _NONE,
)

RN  = "rn"
RNF = "rnf"


# ── المتابعة (expiring soon) ──────────────────────────────────────────────────

def build_followup_list(entries) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER,
        "⏰  **المتابعة**",
        "",
    ]

    if not entries:
        lines += ["✅ لا توجد إقامات منتهية أو قريبة الانتهاء خلال الـ 30 يوم القادمة."]
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:main"),
        ]])
        return "\n".join(lines), kb

    lines.append(f"يوجد {len(entries)} إقامة تتطلب المتابعة:")
    lines.append(_THIN)

    rows: list[list[InlineKeyboardButton]] = []
    for e in entries:
        icon     = format_status_icon(e.status)
        days_str = format_days_remaining(e.expiry_date)
        if e.is_companion:
            label = f"{icon} {e.name} › {e.companion_name}  ({days_str})"
        else:
            label = f"{icon} {e.name}  ({days_str})"
        lines.append(f"  {label}")
        if e.residency_number:
            lines.append(f"    🪪 {e.residency_number}")

        # Action row for this entry
        if e.is_companion:
            btn_submit  = InlineKeyboardButton(
                "📋 تقديم",
                callback_data=f"{RNF}:submitted_c_{e.companion_id}_{e.profile_id}",
            )
            btn_issue   = InlineKeyboardButton(
                "🪪 إصدار",
                callback_data=f"rnr:start_{e.profile_id}",
            )
        else:
            btn_submit  = InlineKeyboardButton(
                "📋 تقديم",
                callback_data=f"{RNF}:submitted_{e.profile_id}",
            )
            btn_issue   = InlineKeyboardButton(
                "🪪 إصدار",
                callback_data=f"rnr:start_{e.profile_id}",
            )
        btn_view = InlineKeyboardButton(
            "👁",
            callback_data=f"rna:view_{e.profile_id}",
        )
        rows.append([btn_submit, btn_issue, btn_view])

    rows.append([InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:main")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


# ── التحديثات المعلقة (dependent_pending) ────────────────────────────────────

def build_pending_list(entries) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER,
        "📦  **التحديثات المعلقة**",
        "",
    ]

    if not entries:
        lines += ["✅ لا توجد تحديثات معلقة."]
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:main"),
        ]])
        return "\n".join(lines), kb

    lines.append(f"يوجد {len(entries)} مريض بمرافقين معلقين:")
    lines.append(_THIN)

    rows: list[list[InlineKeyboardButton]] = []
    for e in entries:
        lines.append(f"⏳ {e.name}  •  {e.pending_companion_count} مرافق معلق")
        rows.append([
            InlineKeyboardButton(
                f"📋 استكمال — {e.name[:20]}",
                callback_data=f"{RNF}:complete_{e.profile_id}",
            )
        ])

    rows.append([InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:main")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)
