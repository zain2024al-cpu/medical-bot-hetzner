# modules/residency/uploads/views.py
# شاشات وحدة «📤 الرفع والمتابعة».
#
# مبدأ الشاشة الأولى: **زر واحد لكل مريض** نصّه يتغيّر حسب مرحلته، فلا يحتاج
# المستخدم أن يتذكّر أي إجراء يناسب أي حالة — نصّ الزر يقرأ من `PAPERS_ADVANCE`
# في constants.py مباشرةً، فلا يمكن أن يعرض زراً لا يطابق ما ينفّذه المستودع.

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from modules.residency.views import (
    format_status, format_status_icon, format_expiry_date, format_days_remaining,
    _DIVIDER, _THIN, _NONE,
)

RN  = "rn"
RNU = "rnu"


def _short(name: str, limit: int = 18) -> str:
    """
    يقصّ الاسم عند حدّ كلمة لا في منتصفها.

    القصّ الخام كان ينتج «عبدالله سالم الأ» على الزر — يبدو كعطل لا كاختصار.
    """
    if len(name) <= limit:
        return name
    cut = name[:limit].rsplit(" ", 1)[0]
    return (cut or name[:limit]) + "…"


# ── شاشة الوحدة ───────────────────────────────────────────────────────────────

def build_uploads_hub(counts: dict[str, int]) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER,
        "📤  **الرفع والمتابعة**",
        "",
        f"⏰ إقامات تنتهي قريباً: {counts['expiring']}",
        f"📤 بانتظار الإقامة الجديدة: {counts['submitted']}",
        f"📥 تمديد مستلَم — بانتظار التسجيل: {counts['received']}",
        _THIN,
        f"🛂 جوازات تنتهي خلال 6 أشهر: {counts['passports']}",
        f"⏳ مرافقون معلقون: {counts['pending']}",
    ]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 متابعة أوراق المستشفى", callback_data=f"{RNU}:papers")],
        [InlineKeyboardButton("➕ إضافة خدمة",             callback_data=f"{RNU}:service")],
        [InlineKeyboardButton(f"⏰ المتابعة ({counts['expiring']})",
                              callback_data=f"{RN}:followup")],
        [InlineKeyboardButton(f"⏳ المرافقون المعلقون ({counts['pending']})",
                              callback_data=f"{RN}:pending")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:main")],
    ])
    return "\n".join(lines), kb


# ── متابعة أوراق المستشفى ─────────────────────────────────────────────────────

def build_papers_list(entries) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER,
        "📋  **متابعة أوراق المستشفى**",
        "",
    ]

    if not entries:
        lines += ["✅ لا يوجد مرضى تحتاج أوراقهم متابعة حالياً."]
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RNU}:hub"),
        ]])
        return "\n".join(lines), kb

    lines += [
        f"عدد المرضى: {len(entries)}",
        "الزر ينقل المريض **ومرافقيه** معاً للمرحلة التالية.",
        _THIN,
    ]

    rows: list[list[InlineKeyboardButton]] = []
    for i, e in enumerate(entries):
        icon = format_status_icon(e.status)
        comp = f"  +{e.companion_count}م" if e.companion_count else ""
        if i:
            lines.append("")
        lines.append(f"{icon} *{e.name}*{comp}")
        lines.append(f"    {format_status(e.status)}")
        if e.expiry_date:
            lines.append(
                f"    📅 {format_expiry_date(e.expiry_date)}"
                f"  ({format_days_remaining(e.expiry_date)})"
            )

        row = [InlineKeyboardButton(
            f"{e.next_label} — {_short(e.name)}",
            callback_data=f"{RNU}:adv_{e.profile_id}",
        )]
        # التراجع يظهر فقط لمن له حدث مرحلة سابق — لا زر بلا أثر
        if e.can_undo:
            row.append(InlineKeyboardButton("↩️", callback_data=f"{RNU}:undo_{e.profile_id}"))
        rows.append(row)

    rows.append([InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RNU}:hub")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


# ── إضافة خدمة ────────────────────────────────────────────────────────────────

def build_service_patient_list(profiles, *, page: int, total: int, page_size: int
                               ) -> tuple[str, InlineKeyboardMarkup]:
    total_pages = max(1, -(-total // page_size))
    lines = [
        _DIVIDER,
        "➕  **إضافة خدمة**",
        "",
        "اختر المريض:",
        f"الصفحة {page + 1} من {total_pages}  •  إجمالي: {total}",
        _THIN,
    ]
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton("🔍 بحث", callback_data="rna:search")],
    ]
    for p in profiles:
        rows.append([InlineKeyboardButton(
            f"{format_status_icon(p.status)} {p.name[:25]}",
            callback_data=f"{RNU}:svc_{p.id}",
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ السابق", callback_data=f"{RNU}:spage_{page - 1}"))
    if (page + 1) < total_pages:
        nav.append(InlineKeyboardButton("التالي ▶️", callback_data=f"{RNU}:spage_{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RNU}:hub")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


def build_service_menu(profile, companions) -> tuple[str, InlineKeyboardMarkup]:
    has_form_c = bool(getattr(profile, "form_c_file_id", ""))
    lines = [
        _DIVIDER,
        "➕  **إضافة خدمة**",
        "",
        f"👤 *{profile.name}*",
        f"📊 {format_status(profile.status)}",
        f"📅 انتهاء الإقامة: {format_expiry_date(profile.expiry_date)}",
        f"👥 المرافقون: {len(companions)}",
        _THIN,
        f"📄 فورم C: {'✅ مرفوع' if has_form_c else '⬜ غير مرفوع'}",
    ]
    if companions:
        lines += [
            "",
            "ℹ️ رفع التمديد الجديد يمرّ على المريض ثم على كل مرافق"
            " مع تقويم ورفع ملف لكلٍّ منهم.",
        ]

    form_c_label = "📄 استبدال فورم C" if has_form_c else "📄 رفع فورم C"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(form_c_label,             callback_data=f"{RNU}:formc_{profile.id}")],
        [InlineKeyboardButton("🪪 رفع التمديد الجديد",  callback_data=f"rnr:start_{profile.id}")],
        [InlineKeyboardButton("👁 عرض الملف",           callback_data=f"rna:view_{profile.id}")],
        [InlineKeyboardButton("⬅️ رجوع",                callback_data=f"{RNU}:service")],
    ])
    return "\n".join(lines), kb


# ── نتائج ─────────────────────────────────────────────────────────────────────

def build_form_c_saved(name: str) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER,
        "✅  **تم رفع فورم C**",
        "",
        f"👤 {name}",
        "",
        "الاستمارة محفوظة على ملف العائلة، وتُرسَل مع «📎 إرسال الوثائق».",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("➕ خدمة أخرى", callback_data=f"{RNU}:service"),
        InlineKeyboardButton("⬅️ رجوع",      callback_data=f"{RNU}:hub"),
    ]])
    return "\n".join(lines), kb


def build_not_found() -> tuple[str, InlineKeyboardMarkup]:
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RNU}:hub"),
    ]])
    return f"{_DIVIDER}\n❌ لم يتم العثور على الملف.", kb
