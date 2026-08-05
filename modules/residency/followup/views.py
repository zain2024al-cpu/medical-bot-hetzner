# modules/residency/followup/views.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from modules.residency.views import (
    format_status_icon, format_expiry_date, format_days_remaining,
    _DIVIDER, _THIN, _NONE,
)

RN  = "rn"
RNF = "rnf"


# ── المتابعة (expiring soon) ──────────────────────────────────────────────────

def _passport_section_lines() -> list[str]:
    """
    قسم إعلامي بالجوازات القاربة على الانتهاء (6 أشهر).

    ✅ بلا أزرار إجراء عمداً: تجديد الجواز ليس من إجراءات هذا البوت
    (بخلاف تجديد الإقامة الذي له مسار كامل) — الغرض إظهاره للمتابعة فقط،
    ونفس القائمة تصل يومياً عبر التنبيه التلقائي.
    """
    from modules.residency.followup.repository import get_passport_expiring_soon
    from modules.residency.constants import PASSPORT_EXPIRING_SOON_DAYS
    from modules.residency.views import format_expiry_date

    entries = get_passport_expiring_soon()
    if not entries:
        return []

    months = PASSPORT_EXPIRING_SOON_DAYS // 30
    out = ["", _THIN, "", f"🛂 **جوازات تنتهي خلال {months} أشهر** ({len(entries)})"]
    for e in entries:
        who = f"{e.name} › {e.companion_name}" if e.is_companion else e.name
        out.append(f"  • {who} — {format_expiry_date(e.expiry_date)} ({e.days_remaining} يوم)")
    return out


def build_followup_list(entries) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER,
        "⏰  **المتابعة**",
        "",
    ]

    passport_lines = _passport_section_lines()

    if not entries:
        lines += ["✅ لا توجد إقامات منتهية أو قريبة الانتهاء خلال الـ 30 يوم القادمة."]
        lines += passport_lines
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:uploads"),
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

    lines += passport_lines

    rows.append([InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:uploads")])
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
            InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:uploads"),
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

    rows.append([InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:uploads")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)
