# modules/residency/views.py
# بناء الشاشات — نظام دورة الحياة الكامل.

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from shared.multiselect import Option

from modules.residency.constants import (
    RN, STATUS_ORDER, STATUS_ICONS, STATUS_LABELS, status_line,
    STATUS_WAITING_ARRIVAL, STATUS_ACTIVE, STATUS_EXPIRY_PENDING,
    STATUS_SUBMITTED, STATUS_ISSUED,
)
from modules.residency.repository import FamilyRow, PersonRow, LogEntry, DocumentRow, ArrivalDocsRow

_DIVIDER = "━━━━━━━━━━━━━━━━━━━━"
_THIN = "─────────────────────"

# ── "🖨️ طباعة ملف الحالة" — فئات الوثائق القابلة للاختيار قبل الطباعة ──────
PRINT_DOC_OPTIONS = [
    Option(id="photo",     label="الصورة الشخصية", icon="📷"),
    Option(id="passport",  label="جوازات السفر",   icon="🛂"),
    Option(id="visa",      label="التأشيرات",       icon="📋"),
    Option(id="residence", label="صورة الإقامة",    icon="🪪"),
    Option(id="tickets",   label="التذاكر",         icon="🎫"),
    Option(id="formc",     label="فورم سي",         icon="📋"),
    Option(id="otherdocs", label="وثائق أخرى",      icon="📄"),
]


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
            f"🔵 تم التقديم(قيد الانتظار) — {person.name[:20]}", callback_data=f"{RN}:submit_{person.id}",
        )
    if person.status == STATUS_SUBMITTED:
        return InlineKeyboardButton(
            f"🟣 توثيق التمديدات المصدره — {person.name[:20]}", callback_data=f"{RN}:issue_start_{person.id}",
        )
    if person.status == STATUS_ISSUED:
        return InlineKeyboardButton(
            f"📂 متابعة الإصدار — {person.name[:20]}", callback_data=f"{RN}:issue_view_{person.id}",
        )
    return None


def build_family_detail(
    family: FamilyRow, *, is_admin: bool, doc_counts: dict[int, int] | None = None,
) -> tuple[str, InlineKeyboardMarkup]:
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

    doc_counts = doc_counts or {}
    rows = []
    btn = _person_action_button(root, is_root=True)
    if btn:
        rows.append([btn])
    n = doc_counts.get(root.id, 0)
    rows.append([InlineKeyboardButton(
        f"📄 الوثائق ({n}) — {root.name[:18]}", callback_data=f"{RN}:docs_{root.id}",
    )])
    for c in family.companions:
        btn = _person_action_button(c, is_root=False)
        if btn:
            rows.append([btn])
        n = doc_counts.get(c.id, 0)
        rows.append([InlineKeyboardButton(
            f"📄 الوثائق ({n}) — {c.name[:18]}", callback_data=f"{RN}:docs_{c.id}",
        )])

    rows.append([InlineKeyboardButton("🖨️ طباعة ملف الحالة", callback_data=f"{RN}:print_{root.id}")])
    rows.append([InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:menu")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


# ── Documents (📄) ───────────────────────────────────────────────────────────

def build_documents_list(person: PersonRow, documents: list[DocumentRow]) -> tuple[str, InlineKeyboardMarkup]:
    lines = [_DIVIDER, "📄  **الوثائق**", "", f"👤 {person.name}", _THIN]
    if not documents:
        lines.append("لا توجد وثائق بعد.")
    else:
        for d in documents:
            label = "Form C" if d.doc_type == "form_c" else (d.doc_name or "وثيقة")
            lines.append(f"- {label} ✅  ({d.created_at})")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة وثيقة", callback_data=f"{RN}:doc_add_{person.id}")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:family_{person.parent_id or person.id}")],
    ])
    return "\n".join(lines), kb


def build_doc_type_prompt(person: PersonRow) -> tuple[str, InlineKeyboardMarkup]:
    text = f"{_DIVIDER}\n📄  **إضافة وثيقة**\n\n👤 {person.name}\n\nاختر نوع الوثيقة:"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Form C", callback_data=f"{RN}:doc_add_formc_{person.id}")],
        [InlineKeyboardButton("📋 أخرى", callback_data=f"{RN}:doc_add_other_{person.id}")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:docs_{person.id}")],
    ])
    return text, kb


def build_doc_name_prompt(person: PersonRow) -> tuple[str, InlineKeyboardMarkup]:
    text = f"{_DIVIDER}\n📄  **اسم الوثيقة**\n\n👤 {person.name}\n\nاكتب اسم الوثيقة الآن."
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:docs_{person.id}")]])
    return text, kb


def build_doc_file_prompt(person: PersonRow, doc_name: str) -> tuple[str, InlineKeyboardMarkup]:
    text = f"{_DIVIDER}\n📎  **رفع الوثيقة**\n\n👤 {person.name}\n📄 {doc_name}\n\nأرسل الصورة/الملف الآن."
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:docs_{person.id}")]])
    return text, kb


# ── Onboarding (🟡) ──────────────────────────────────────────────────────────

def build_arrival_summary(
    root: PersonRow, arrival: ArrivalDocsRow | None, companions: list[PersonRow],
) -> tuple[str, InlineKeyboardMarkup]:
    """شاشة ملخّص بيانات الوصول — تظهر عند فتح طلب ضمن "🟡 معلّق من
    الوصول"، قبل بدء استكمال الصورة/تاريخ التنبيه، حتى يراجع الإداري
    بيانات المريض كاملة أولاً بدل الانتقال المباشر لطلب الصورة."""
    def _v(val: str) -> str:
        return val if val else "—"

    def _mark(file_id: str) -> str:
        return "✅" if file_id else "⬜"

    lines = [
        _DIVIDER, "📋  **ملخّص بيانات الوصول**", "",
        f"👤 {root.name}", _THIN, "",
    ]

    if arrival is None:
        lines.append("⚠️ لا توجد بيانات وصول مطابقة لهذا الاسم.")
    else:
        lines += [
            f"📅 تاريخ الوصول: {_v(arrival.arrival_date)}",
            f"🛂 انتهاء الجواز: {_v(arrival.passport_expiry)}",
            f"📋 انتهاء التأشيرة: {_v(arrival.visa_expiry)}",
            f"🪪 انتهاء الإقامة: {_v(arrival.residence_expiry)}",
            "",
            "📎 *حالة الوثائق المرفوعة:*",
            f"  جواز السفر: {_mark(arrival.passport_file_id)}",
            f"  التأشيرة: {_mark(arrival.visa_file_id)}",
            f"  التذاكر: {_mark(arrival.tickets_file_id)}",
            f"  الإقامة: {_mark(arrival.residence_file_id)}",
        ]

    if companions:
        lines += ["", f"🤝 *المرافقون ({len(companions)}):*"]
        for c in companions:
            lines.append(f"  • {c.name}")

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ ابدأ استكمال البيانات", callback_data=f"{RN}:onboard_resume_{root.id}")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:menu")],
    ])
    return "\n".join(lines), kb


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
        _DIVIDER, "🟣  **توثيق التمديدات المصدره — استكمال البيانات**", "",
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
