# modules/residency/views.py
# بناء الشاشات — نظام دورة الحياة الكامل.

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from shared.multiselect import Option

from modules.residency.constants import (
    RN, STATUS_ORDER, STATUS_ICONS, STATUS_LABELS, status_line,
    STATUS_WAITING_ARRIVAL, STATUS_ACTIVE, STATUS_EXPIRY_PENDING,
    STATUS_SUBMITTED, STATUS_ISSUED, STATUS_LEGACY_PENDING,
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
    rows.append([InlineKeyboardButton("📤 تصدير جدول (PDF / Excel)", callback_data=f"{RN}:export")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


def build_export_status_picker(counts: dict) -> tuple[str, InlineKeyboardMarkup]:
    """اختيار الحالة المُصدَّرة — العدد بجانب كلٍّ ليعرف المستخدم حجم الجدول."""
    lines = [_DIVIDER, "📤  **تصدير جدول**", "", "اختر الحالة المطلوب تصديرها:"]
    rows = []
    total = 0
    for s in STATUS_ORDER:
        n = counts.get(s, 0)
        total += n
        rows.append([InlineKeyboardButton(
            f"{STATUS_ICONS[s]} {STATUS_LABELS[s]} ({n})",
            callback_data=f"{RN}:exp:{s}")])
    rows.append([InlineKeyboardButton(f"🗂 كل الحالات ({total})",
                                      callback_data=f"{RN}:exp:ALL")])
    rows.append([InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:menu")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


def build_export_format_picker(status: str, label: str, n: int) -> tuple[str, InlineKeyboardMarkup]:
    lines = [_DIVIDER, "📤  **صيغة الملف**", "", f"الحالة: *{label}*",
             f"عدد الطلبات: {n}", _THIN, "اختر الصيغة:"]
    rows = [
        [InlineKeyboardButton("📄 PDF — جاهز للطباعة",
                              callback_data=f"{RN}:expdo:{status}:pdf")],
        [InlineKeyboardButton("📊 Excel — قابل للفرز والتعديل",
                              callback_data=f"{RN}:expdo:{status}:xlsx")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:export")],
    ]
    return "\n".join(lines), InlineKeyboardMarkup(rows)


def _family_summary_line(family: FamilyRow) -> str:
    if family.companions:
        return f"👤 {family.root.name}\n👥 المرافقون: {len(family.companions)}"
    return f"👤 {family.root.name}"

_RN_PER_PAGE = 8


def build_status_list(status: str, families: list[FamilyRow],
                      page: int = 0, per_page: int = _RN_PER_PAGE) -> tuple[str, InlineKeyboardMarkup]:
    """قائمة الحالة **مصفَّحة**.

    ⚠️ كانت تُخرِج زراً لكل طلب دفعةً واحدة — و«الحالات النشطة» وحدها ٥٣
    طلباً. عدا صعوبة التصفّح، تليجرام يرفض الرسالة إن تجاوزت حدّها، فكانت
    القائمة قنبلةً موقوتة تنفجر مع نموّ البيانات لا عطلاً ظاهراً اليوم.
    """
    from modules.residency.days import family_badge
    from modules.residency.repository import get_status_since

    total = len(families)
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(int(page), pages - 1))     # صفحة خارج النطاق تُصحَّح
    chunk = families[page * per_page:(page + 1) * per_page]

    lines = [_DIVIDER, f"{status_line(status)}", ""]
    rows = []
    if not families:
        lines.append("✅ لا توجد طلبات بهذه الحالة حالياً.")
    else:
        # ✅ استعلام واحد لكل الأشخاص المعروضين — لا استعلام داخل الحلقة.
        _ids = [p.id for f in chunk for p in ([f.root] + list(f.companions))]
        _since = get_status_since(_ids)

        lines.append(f"يوجد {total} طلباً — صفحة {page + 1} من {pages}")
        lines.append(_THIN)
        for fam in chunk:
            comp_note = f" (+{len(fam.companions)} مرافق)" if fam.companions else ""
            # شارة العائلة = أشدّ أفرادها إلحاحاً (قد يكون مرافقاً لا المريض)
            bdg = family_badge(fam, _since)
            note = f" — {bdg}" if bdg else ""
            lines.append(f"👤 {fam.root.name}{comp_note}{note}")
            rows.append([InlineKeyboardButton(
                f"📂 {fam.root.name[:22]}{note}", callback_data=f"{RN}:family_{fam.root.id}",
            )])

        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(
                "⬅️ السابق", callback_data=f"{RN}:lpage:{status}:{page - 1}"))
        if page + 1 < pages:
            nav.append(InlineKeyboardButton(
                "التالي ➡️", callback_data=f"{RN}:lpage:{status}:{page + 1}"))
        if nav:
            rows.append(nav)

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
    back_to: str | None = None,
) -> tuple[str, InlineKeyboardMarkup]:
    """`back_to` — وجهة زر الرجوع.

    ⚠️ كانت كل الشاشات ترجع إلى `{RN}:menu` (القائمة الرئيسية) أياً كان
    مصدر الدخول. فمن يفتح حالة من "🟢 الحالات النشطة" يُقذَف للقائمة
    الرئيسية عند الرجوع بدل العودة لقائمته، ويضطر لإعادة التنقّل من الصفر
    بعد كل حالة يفحصها — وهذا معنى "زر الرجوع لا يعمل بشكل صحيح".
    الافتراضي `None` يُبقي السلوك القديم لأي مستدعٍ لم يُمرِّر شيئاً."""
    from modules.residency.days import badge as _day_badge
    from modules.residency.repository import get_status_since

    root = family.root
    _ids = [p.id for p in ([root] + list(family.companions))]
    _since = get_status_since(_ids)

    def _b(person, pad: str) -> list[str]:
        """سطر الأيام لشخص — يُحذَف كلياً إن لا رقم متاحاً."""
        txt = _day_badge(person, _since.get(person.id))
        return [f"{pad}⏳ {txt}"] if txt else []

    lines = [_DIVIDER, "🪪  **تفاصيل الطلب**", "", f"👤 *المريض:* {root.name}", f"  {status_line(root.status)}"]
    lines += _b(root, "  ")
    if root.reminder_date:
        lines.append(f"  🔔 تاريخ التنبيه: {root.reminder_date}")
    if root.expiry_date:
        lines.append(f"  📅 تاريخ الانتهاء: {root.expiry_date}")

    # ⚠️ فجوة بين النظامين: مرافق مسجَّل في الوصول وغائب عن الإقامة
    # (فشل النداء fire-and-forget، أو أُضيف للوصول بعد إنشاء الملف).
    # تُعرَض صراحةً بدل أن يظهر "المرافقون: 0" بلا تفسير.
    _missing = []
    try:
        from modules.residency.repository import get_arrival_companion_names
        _known = {(c.name or "").strip() for c in family.companions}
        _missing = [n for n in get_arrival_companion_names(root.name) if n not in _known]
    except Exception:
        _missing = []

    if _missing:
        lines.append(_THIN)
        lines.append(f"⚠️ *{len(_missing)} مرافق مسجَّل في الوصول وغير مضاف هنا:*")
        for n in _missing:
            lines.append(f"   • {n}")
        lines.append("_اضغط «🔄 إضافة مرافقي الوصول» لإضافتهم._")

    if family.companions:
        lines.append(_THIN)
        lines.append(f"👥 *المرافقون ({len(family.companions)}):*")
        for c in family.companions:
            lines.append(f"  • {c.name} — {status_line(c.status)}")
            lines += _b(c, "     ")
            if c.reminder_date:
                lines.append(f"     🔔 {c.reminder_date}")
            if c.expiry_date:
                lines.append(f"     📅 {c.expiry_date}")
    lines.append(_THIN)

    doc_counts = doc_counts or {}
    rows = []

    # ✅ 🏠 معلّقات من الحالات السابقة — شاشة **مقتصرة على القرار وحده**:
    # زرّان على مستوى العائلة (المسار يعالج المريض ومرافقيه دفعة واحدة ثم
    # ينقلهم معاً للحالة المختارة)، بلا أزرار الوثائق والطباعة.
    #
    # ⚠️ سبب الإخفاء (بطلب المستخدم صراحةً): هذه حالة **عبور** — الغرض
    # الوحيد منها إدخال بيانات الإقامة الناقصة ثم النقل للحالة الطبيعية.
    # وثائق المريض القديم أصلاً لم تُرفَع بعد عبر هذه الوحدة، وطباعة ملف
    # الحالة قبل اكتمال بيانات الإقامة تُخرِج ملفاً ناقصاً. الزرّان يعودان
    # للظهور تلقائياً بمجرد انتقاله لأي من الحالات الخمس الطبيعية.
    if root.status == STATUS_LEGACY_PENDING:
        rows.append([InlineKeyboardButton(
            "✅ توجد إقامة / تمديد", callback_data=f"{RN}:lgc_ext_{root.id}",
        )])
        rows.append([InlineKeyboardButton(
            "❌ لا يوجد تمديد", callback_data=f"{RN}:lgc_noext_{root.id}",
        )])
        rows.append([InlineKeyboardButton(
            "⬅️ رجوع", callback_data=back_to or f"{RN}:menu")])
        return "\n".join(lines), InlineKeyboardMarkup(rows)

    if _missing:
        rows.append([InlineKeyboardButton(
            f"🔄 إضافة مرافقي الوصول ({len(_missing)})",
            callback_data=f"{RN}:syncomp_{root.id}",
        )])

    # ✏️ تصحيح أي بيانات أُدخِلت خطأً — متاح دائماً بعد مغادرة "معلّق الوصول"
    if root.status != STATUS_WAITING_ARRIVAL:
        rows.append([InlineKeyboardButton(
            "✏️ تعديل البيانات", callback_data=f"{RN}:editp_{root.id}")])

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
    rows.append([InlineKeyboardButton("⬅️ رجوع", callback_data=back_to or f"{RN}:menu")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


# ── Documents (📄) ───────────────────────────────────────────────────────────
def build_documents_list(person: PersonRow, documents: list[DocumentRow]) -> tuple[str, InlineKeyboardMarkup]:
    """كل ملفات الشخص — الوثائق **وملف الإقامة والصورة**، مع زرّ عرض لكلٍّ.

    ⚠️ كانت تعرض جدول `res_documents` وحده وبلا أي زرّ عرض إطلاقاً: شخص
    رفع إقامته وصورته يرى «لا توجد وثائق بعد»، ومن رفع وثيقة لا يستطيع
    فتحها — الطريقة الوحيدة لرؤية أي ملف كانت طباعة ملف الحالة كاملاً.
    """
    lines = [_DIVIDER, "📄  **الملفات**", "", f"👤 {person.name}", _THIN]
    rows = []

    has_res   = bool((person.residency_file_id or "").strip())
    has_photo = bool((person.photo_file_id or "").strip())

    if has_res:
        lines.append("- 🪪 ملف الإقامة ✅")
        rows.append([InlineKeyboardButton(
            "🪪 عرض ملف الإقامة", callback_data=f"{RN}:resview_{person.id}")])
    if has_photo:
        lines.append("- 🖼️ الصورة الشخصية ✅")
        rows.append([InlineKeyboardButton(
            "🖼️ عرض الصورة الشخصية", callback_data=f"{RN}:photoview_{person.id}")])

    if documents:
        # ✅ زر حذف لكل وثيقة — كانت تُضاف ولا تُحذَف أبداً، فوثيقة رُفِعت
        # خطأً تبقى في ملف الحالة وتُطبَع معه إلى الأبد.
        for d in documents:
            label = "Form C" if d.doc_type == "form_c" else (d.doc_name or "وثيقة")
            lines.append(f"- 📄 {label} ✅  ({d.created_at})")
            rows.append([
                InlineKeyboardButton(f"👁️ {label[:18]}", callback_data=f"{RN}:docview_{d.id}"),
                InlineKeyboardButton("🗑️ حذف", callback_data=f"{RN}:docdel_{d.id}"),
            ])

    if not (has_res or has_photo or documents):
        lines.append("لا توجد ملفات بعد.")
    elif has_res or has_photo:
        # حذف هذين الملفين له مسار واحد قائم (✏️ تعديل البيانات) — لا يُكرَّر
        # هنا حتى لا يوجد طريقان للحذف يتباعدان مع الوقت.
        lines.append(_THIN)
        lines.append("لتبديل ملف الإقامة أو الصورة أو حذفهما: «✏️ تعديل البيانات».")

    rows.append([InlineKeyboardButton("➕ إضافة وثيقة", callback_data=f"{RN}:doc_add_{person.id}")])
    rows.append([InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:family_{person.parent_id or person.id}")])
    kb = InlineKeyboardMarkup(rows)
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
    back_to: str | None = None,
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
        [InlineKeyboardButton("⬅️ رجوع", callback_data=back_to or f"{RN}:menu")],
    ])
    return "\n".join(lines), kb


def build_onboard_photo_prompt(
    person: PersonRow, idx: int, total: int, back_to: str | None = None,
) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"{_DIVIDER}\n📷  **الصورة الشخصية ({idx}/{total})**\n\n"
        f"الشخص: {person.name}\n\nأرسل الصورة الآن."
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(
        "⬅️ رجوع", callback_data=back_to or f"{RN}:menu")]])
    return text, kb


def build_onboard_review(queue: list[PersonRow], back_to: str | None = None) -> tuple[str, InlineKeyboardMarkup]:
    lines = [_DIVIDER, "✅  **مراجعة قبل الحفظ**", ""]
    for p in queue:
        photo_mark = "✅" if p.photo_file_id else "⬜"
        lines.append(f"👤 {p.name}  —  صورة {photo_mark}  🔔 {p.reminder_date or '—'}")
    lines.append(_THIN)
    root_id = queue[0].id if queue else 0
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ حفظ الإقامة", callback_data=f"{RN}:onboard_save_{root_id}")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data=back_to or f"{RN}:menu")],
    ])
    return "\n".join(lines), kb


# ── Issuance (🟣) ────────────────────────────────────────────────────────────

def build_issuance_view(person: PersonRow, back_to: str | None = None) -> tuple[str, InlineKeyboardMarkup]:
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
    rows.append([InlineKeyboardButton("⬅️ رجوع", callback_data=back_to or f"{RN}:menu")])
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

_LOG_PER_PAGE = 8          # نفس حجم صفحة شاشة المراقبة الإدارية


def _day_label(iso_date: str) -> str:
    """«اليوم» / «أمس» / التاريخ — أوضح من تكرار السنة في كل سطر."""
    from datetime import date, timedelta
    try:
        y, m, d = (int(x) for x in iso_date.split("-"))
        day = date(y, m, d)
    except Exception:
        return iso_date
    today = date.today()
    if day == today:
        return f"اليوم · {iso_date}"
    if day == today - timedelta(days=1):
        return f"أمس · {iso_date}"
    return iso_date


def build_log_view(entries: list[LogEntry], page: int = 0,
                   pages: int = 1, total: int = 0) -> tuple[str, InlineKeyboardMarkup]:
    """سجل الأحداث — مجمَّعاً بالأيام ومصفَّحاً.

    ⚠️ كان ٣٠ حدثاً في رسالة واحدة (~٣٠٩٠ حرفاً، ٧٥٪ من حدّ تليجرام)،
    كل سطر ~١٠٠ حرف لأنه يحمل الاسم كاملاً والتسميتين كاملتين والتاريخ
    بالسنة — فيلتفّ ثلاث مرات على الجوال ويصير جداراً من النصّ.
    الآن: عنوان يوم لكل مجموعة، ووقت فقط في السطر، وتسميات مختصرة،
    واسم مقصوص، وصفحات.
    """
    from modules.residency.constants import status_chip

    lines = [_DIVIDER, "📋  **سجل الإقامات**", ""]
    rows = []

    if not entries:
        lines.append("لا توجد أحداث بعد.")
    else:
        lines.append(f"{total} حدثاً — صفحة {page + 1} من {pages}")
        current_day = None
        for e in entries:
            stamp = e.created_at or ""
            day, _, clock = stamp.partition(" ")
            if day != current_day:
                current_day = day
                lines.append("")
                lines.append(f"📅 *{_day_label(day)}*")
                lines.append(_THIN)
            old = status_chip(e.old_status) if e.old_status else "—"
            new = status_chip(e.new_status)
            # ⚙️ = نقلته المهمة اليومية لا مستخدم. تمييزٌ مفيد عند مراجعة
            # سبب تحرّك حالة لم يلمسها أحد.
            who = "" if e.performed_by else "  ⚙️"
            lines.append(f"🕐 {clock} · {e.person_name[:22]}")
            lines.append(f"      {old} ⟵ {new}{who}")

        # رمز بلا مفتاح لغز — يُشرح عند ظهوره فقط لا في كل صفحة
        if any(not e.performed_by for e in entries):
            lines.append("")
            lines.append("⚙️ = نقلٌ تلقائي بالمهمة اليومية (بلا تدخّل مستخدم)")

        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"{RN}:logp:{page - 1}"))
        if page + 1 < pages:
            nav.append(InlineKeyboardButton("التالي ➡️", callback_data=f"{RN}:logp:{page + 1}"))
        if nav:
            rows.append(nav)

    rows.append([InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:menu")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


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


# ── 🏠 معالجة "معلّقات من الحالات السابقة" ────────────────────────────────────
# شاشات إدخال بيانات إقامة المريض القديم (ومرافقيه) ثم نقلهم للحالة المختارة.

_LEGACY_STEP_TITLES = {
    "last_issue": "📆 تاريخ **آخر إصدار** للإقامة",
    "expiry":     "📅 تاريخ **انتهاء** الإقامة",
    "reminder":   "🔔 تاريخ **التنبيه القادم**",
    "res_file":   "🪪 صورة **آخر إقامة**",
    "photo":      "📷 **الصورة الشخصية**",
}


def legacy_step_header(person: PersonRow, step: str, idx: int, total: int) -> str:
    """ترويسة موحَّدة لكل خطوات هذا المسار — تُظهر لمن ندخل البيانات الآن
    وأين نحن من الطابور (المريض ثم مرافقوه)."""
    who = f"👤 {person.name}" if idx == 1 else f"🤝 {person.name}"
    return (
        f"🏠 **معالجة حالة سابقة** — ({idx}/{total})\n"
        f"{who}\n\n"
        f"{_LEGACY_STEP_TITLES.get(step, step)}"
    )


def build_legacy_upload_prompt(
    person: PersonRow, step: str, idx: int, total: int, back_to: str | None = None,
) -> tuple[str, InlineKeyboardMarkup]:
    """شاشة رفع ملف (صورة آخر إقامة / الصورة الشخصية)."""
    text = legacy_step_header(person, step, idx, total) + "\n\nأرسل الصورة أو الملف الآن 📎"
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ رجوع", callback_data=back_to or f"{RN}:menu"),
    ]])
    return text, kb


def build_legacy_target_chooser(family: FamilyRow) -> tuple[str, InlineKeyboardMarkup]:
    """الخطوة الأخيرة: اختيار القائمة التي ينتقل إليها المريض ومرافقوه.

    تُعرض كل الحالات عدا LEGACY_PENDING نفسها (لا معنى للبقاء فيها بعد
    اكتمال الإدخال) — مشتقّة من STATUS_ORDER فتتبع أي تغيير مستقبلي تلقائياً.
    """
    total = 1 + len(family.companions)
    lines = [
        _DIVIDER,
        "✅ **اكتملت بيانات الإقامة**",
        "",
        f"👤 {family.root.name}",
    ]
    if family.root.expiry_date:
        lines.append(f"  📅 الانتهاء: {family.root.expiry_date}")
    if family.root.last_issue_date:
        lines.append(f"  📆 آخر إصدار: {family.root.last_issue_date}")
    for c in family.companions:
        lines.append(f"🤝 {c.name}")
        if c.expiry_date:
            lines.append(f"  📅 الانتهاء: {c.expiry_date}")
    lines += [
        _THIN,
        f"👥 سيُنقَل **{total}** شخص معاً.",
        "",
        "اختر القائمة التي ينتقلون إليها:",
    ]

    rows = [
        [InlineKeyboardButton(
            f"{STATUS_ICONS.get(s, '⚪')} {STATUS_LABELS.get(s, s)}",
            callback_data=f"{RN}:lgc_to_{s}_{family.root.id}",
        )]
        for s in STATUS_ORDER if s != STATUS_LEGACY_PENDING
    ]
    rows.append([InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:family_{family.root.id}")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)
