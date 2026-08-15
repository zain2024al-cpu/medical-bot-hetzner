# modules/residency/views.py
# بناء الشاشات — نظام دورة الحياة الكامل.

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from modules.residency.constants import (
    RN, STATUS_ORDER, STATUS_ICONS, STATUS_LABELS, status_line,
    STATUS_WAITING_ARRIVAL, STATUS_ACTIVE, STATUS_EXPIRY_PENDING,
    STATUS_SUBMITTED, STATUS_ISSUED,
)
from modules.residency.repository import FamilyRow, PersonRow, LogEntry

_DIVIDER = "━━━━━━━━━━━━━━━━━━━━"
_THIN = "─────────────────────"


def build_main_menu(counts: dict) -> tuple[str, InlineKeyboardMarkup]:
    lines = [_DIVIDER, "🪪  **الإقامة**", "", "اختر القسم:"]
    rows = []
    for s in STATUS_ORDER:
        icon = STATUS_ICONS[s]
        label = STATUS_LABELS[s]
        n = counts.get(s, 0)
        rows.append([InlineKeyboardButton(f"{icon} {label} ({n})", callback_data=f"{RN}:status_{s}")])
    rows.append([InlineKeyboardButton("🔍 البحث", callback_data=f"{RN}:search")])
    rows.append([InlineKeyboardButton("📋 سجل الإقامات", callback_data=f"{RN}:log")])
    rows.append([InlineKeyboardButton("📊 التقارير", callback_data=f"{RN}:reports")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


def _family_summary_line(family: FamilyRow) -> str:
    if family.companions:
        return f"👤 {family.root.name}\n👥 المرافقون: {len(family.companions)}"
    return f"👤 {family.root.name}"


def build_status_list(status: str, families: list[FamilyRow]) -> tuple[str, InlineKeyboardMarkup]:
    lines = [_DIVIDER, f"{status_line(status)}", ""]
    rows = []
    if not families:
        lines.append("✅ لا توجد طلبات بهذه الحالة حالياً.")
    else:
        lines.append(f"يوجد {len(families)} طلباً — اضغط لفتح التفاصيل:")
        lines.append(_THIN)
        for fam in families:
            comp_note = f" (+{len(fam.companions)} مرافق)" if fam.companions else ""
            lines.append(f"👤 {fam.root.name}{comp_note}")
            rows.append([InlineKeyboardButton(
                f"📂 {fam.root.name[:25]}", callback_data=f"{RN}:family_{fam.root.id}",
            )])
    rows.append([InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:menu")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


def _person_action_button(person: PersonRow, *, is_root: bool) -> InlineKeyboardButton | None:
    role = "المريض" if is_root else f"مرافق"
    if person.status == STATUS_WAITING_ARRIVAL:
        return InlineKeyboardButton(
            f"▶️ استكمال بيانات {role}: {person.name[:20]}",
            callback_data=f"{RN}:onboard_resume_{person.id}",
        )
    if person.status == STATUS_EXPIRY_PENDING:
        return InlineKeyboardButton(
            f"🔵 تم التقديم — {person.name[:20]}", callback_data=f"{RN}:submit_{person.id}",
        )
    if person.status == STATUS_SUBMITTED:
        return InlineKeyboardButton(
            f"🟣 تم الإصدار — {person.name[:20]}", callback_data=f"{RN}:issue_start_{person.id}",
        )
    if person.status == STATUS_ISSUED:
        return InlineKeyboardButton(
            f"📂 متابعة الإصدار — {person.name[:20]}", callback_data=f"{RN}:issue_view_{person.id}",
        )
    return None


def build_family_detail(family: FamilyRow, *, is_admin: bool) -> tuple[str, InlineKeyboardMarkup]:
    root = family.root
    lines = [_DIVIDER, "🪪  **تفاصيل الطلب**", "", f"👤 *المريض:* {root.name}", f"  {status_line(root.status)}"]
    if root.reminder_date:
        lines.append(f"  🔔 تاريخ التنبيه: {root.reminder_date}")
    if root.expiry_date:
        lines.append(f"  📅 تاريخ الانتهاء: {root.expiry_date}")

    if family.companions:
        lines.append(_THIN)
        lines.append(f"👥 *المرافقون ({len(family.companions)}):*")
        for c in family.companions:
            lines.append(f"  • {c.name} — {status_line(c.status)}")
            if c.reminder_date:
                lines.append(f"     🔔 {c.reminder_date}")
            if c.expiry_date:
                lines.append(f"     📅 {c.expiry_date}")
    lines.append(_THIN)

    rows = []
    btn = _person_action_button(root, is_root=True)
    if btn:
        rows.append([btn])
    for c in family.companions:
        btn = _person_action_button(c, is_root=False)
        if btn:
            rows.append([btn])

    rows.append([InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:menu")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


# ── Onboarding (🟡) ──────────────────────────────────────────────────────────

def build_onboard_photo_prompt(person: PersonRow, idx: int, total: int) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"{_DIVIDER}\n📷  **الصورة الشخصية ({idx}/{total})**\n\n"
        f"الشخص: {person.name}\n\nأرسل الصورة الآن."
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:menu")]])
    return text, kb


def build_onboard_review(queue: list[PersonRow]) -> tuple[str, InlineKeyboardMarkup]:
    lines = [_DIVIDER, "✅  **مراجعة قبل الحفظ**", ""]
    for p in queue:
        photo_mark = "✅" if p.photo_file_id else "⬜"
        lines.append(f"👤 {p.name}  —  صورة {photo_mark}  🔔 {p.reminder_date or '—'}")
    lines.append(_THIN)
    root_id = queue[0].id if queue else 0
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ حفظ الإقامة", callback_data=f"{RN}:onboard_save_{root_id}")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:menu")],
    ])
    return "\n".join(lines), kb


# ── Issuance (🟣) ────────────────────────────────────────────────────────────

def build_issuance_view(person: PersonRow) -> tuple[str, InlineKeyboardMarkup]:
    expiry_mark = person.expiry_date if person.expiry_date else "➖ غير محدَّد"
    file_mark = "✅ مرفوع" if person.residency_file_id else "⬜ غير مرفوع"
    lines = [
        _DIVIDER, "🟣  **تم الإصدار — استكمال البيانات**", "",
        f"👤 {person.name}",
        f"📅 تاريخ الانتهاء الجديد: {expiry_mark}",
        f"📎 ملف الإقامة الجديدة: {file_mark}",
    ]
    rows = [
        [InlineKeyboardButton("📅 تاريخ الانتهاء الجديد", callback_data=f"{RN}:issue_expiry_{person.id}")],
        [InlineKeyboardButton("📎 رفع ملف الإقامة الجديدة", callback_data=f"{RN}:issue_file_{person.id}")],
    ]
    if person.expiry_date and person.residency_file_id:
        rows.append([InlineKeyboardButton("✅ تأكيد الإصدار", callback_data=f"{RN}:issue_confirm_{person.id}")])
    rows.append([InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:menu")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


def build_issuance_file_prompt(person: PersonRow) -> tuple[str, InlineKeyboardMarkup]:
    text = f"{_DIVIDER}\n📎  **رفع ملف الإقامة الجديدة**\n\nالشخص: {person.name}\n\nأرسل الصورة/الملف الآن."
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:issue_view_{person.id}")]])
    return text, kb


# ── Search / Log / Reports ───────────────────────────────────────────────────

def build_search_prompt() -> tuple[str, InlineKeyboardMarkup]:
    text = f"{_DIVIDER}\n🔍  **البحث**\n\nاكتب اسم المريض أو المرافق."
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:menu")]])
    return text, kb


def build_search_results(query: str, results: list[PersonRow]) -> tuple[str, InlineKeyboardMarkup]:
    lines = [_DIVIDER, f"🔍  **نتائج البحث عن:** {query}", ""]
    rows = []
    if not results:
        lines.append("لا توجد نتائج.")
    else:
        for p in results:
            lines.append(f"👤 {p.name}  —  {status_line(p.status)}")
            rows.append([InlineKeyboardButton(
                f"📂 {p.name[:25]}", callback_data=f"{RN}:person_{p.id}",
            )])
    rows.append([InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:menu")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


def build_log_view(entries: list[LogEntry]) -> tuple[str, InlineKeyboardMarkup]:
    lines = [_DIVIDER, "📋  **سجل الإقامات**", ""]
    if not entries:
        lines.append("لا توجد أحداث بعد.")
    else:
        for e in entries:
            old = status_line(e.old_status) if e.old_status else "—"
            new = status_line(e.new_status)
            lines.append(f"• {e.person_name}: {old} ← {new}  ({e.created_at})")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:menu")]])
    return "\n".join(lines), kb


def build_reports_view(counts: dict) -> tuple[str, InlineKeyboardMarkup]:
    lines = [_DIVIDER, "📊  **التقارير**", ""]
    total = 0
    for s in STATUS_ORDER:
        n = counts.get(s, 0)
        total += n
        lines.append(f"{STATUS_ICONS[s]} {STATUS_LABELS[s]}: {n}")
    lines.append(_THIN)
    lines.append(f"الإجمالي: {total} طلباً")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:menu")]])
    return "\n".join(lines), kb
