# modules/residency/profiles/views.py
# All view builders for the profiles sub-module:
# main menu, archive list, profile detail, add-patient steps.

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from modules.residency.constants import PROFILES_PAGE_SIZE, HISTORY_DISPLAY_LIMIT
from modules.residency.views import (
    format_status, format_status_icon, format_expiry_date,
    format_days_remaining, format_expiry_warning_inline, doc_icon,
    _DIVIDER, _THIN, _NONE,
)

RN  = "rn"
RNA = "rna"


# ── Main menu ─────────────────────────────────────────────────────────────────

def build_residency_main_menu() -> tuple[str, InlineKeyboardMarkup]:
    text = f"{_DIVIDER}\n🪪  **الإقامات**\n\nاختر القسم:"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📁 أرشيف المرضى",      callback_data=f"{RN}:archive")],
        [InlineKeyboardButton("➕ إضافة مريض جديد",   callback_data=f"{RNA}:start")],
        [InlineKeyboardButton("⏰ المتابعة",           callback_data=f"{RN}:followup")],
        [InlineKeyboardButton("📦 التحديثات المعلقة", callback_data=f"{RN}:pending")],
    ])
    return text, kb


# ── Archive list ──────────────────────────────────────────────────────────────

def build_archive_list(profiles, *, page: int, total: int) -> tuple[str, InlineKeyboardMarkup]:
    total_pages = max(1, -(-total // PROFILES_PAGE_SIZE))  # ceil division
    lines = [
        _DIVIDER,
        "📁  **أرشيف المرضى**",
        "",
        f"الصفحة {page + 1} من {total_pages}  •  إجمالي: {total} مريض",
        _THIN,
    ]
    if not profiles:
        lines += ["", "لا يوجد مرضى مسجلون حتى الآن."]
    else:
        for p in profiles:
            icon    = format_status_icon(p.status)
            warning = format_expiry_warning_inline(p.expiry_date)
            comp    = f" +{p.companion_count}م" if p.companion_count else ""
            lines.append(f"{icon} {p.name}{comp}{warning}")

    rows: list[list[InlineKeyboardButton]] = []

    # Search button at the top
    rows.append([InlineKeyboardButton("🔍 بحث", callback_data=f"{RNA}:search")])

    # Patient buttons (one per row)
    for p in profiles:
        icon = format_status_icon(p.status)
        rows.append([
            InlineKeyboardButton(
                f"{icon} {p.name[:25]}",
                callback_data=f"{RNA}:view_{p.id}",
            )
        ])

    # Pagination row
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ السابق", callback_data=f"{RNA}:page_{page - 1}"))
    if (page + 1) < total_pages:
        nav.append(InlineKeyboardButton("التالي ▶️", callback_data=f"{RNA}:page_{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([
        InlineKeyboardButton("➕ إضافة جديد", callback_data=f"{RNA}:start"),
        InlineKeyboardButton("⬅️ رجوع",       callback_data=f"{RN}:main"),
    ])

    return "\n".join(lines), InlineKeyboardMarkup(rows)


# ── Profile detail ────────────────────────────────────────────────────────────

def build_profile_detail(profile, companions, history) -> tuple[str, InlineKeyboardMarkup]:
    comp_count   = len(companions)
    status_icon  = format_status_icon(profile.status)
    status_label = format_status(profile.status)

    lines = [
        _DIVIDER,
        "🪪  **ملف المريض**",
        "",
        f"👤 *{profile.name}*",
        f"🪪 *رقم الإقامة:*  {profile.residency_number or _NONE}",
        f"📅 *تاريخ الانتهاء:*  {format_expiry_date(profile.expiry_date)}",
        f"⏳ *الأيام المتبقية:*  {format_days_remaining(profile.expiry_date)}",
        f"📊 *الحالة:*  {status_icon} {status_label}",
        "",
        f"👥 *عدد المرافقين:*  {comp_count}",
        _THIN,
    ]

    # ── Companions — full block per person ────────────────────────────────────
    if comp_count == 0:
        lines.append("  لا يوجد مرافقون")
    else:
        for i, c in enumerate(companions, 1):
            c_icon  = format_status_icon(c.status)
            c_label = format_status(c.status)
            c_exp   = format_expiry_date(c.expiry_date)
            c_days  = format_days_remaining(c.expiry_date)
            c_num   = c.residency_number or _NONE
            lines += [
                "",
                f"  *{i}.* 👤 *{c.name}*",
                f"  🪪 {c_num}",
                f"  📅 {c_exp}",
                f"  ⏳ {c_days}",
                f"  📊 {c_icon} {c_label}",
            ]

    lines.append(_THIN)

    # ── Documents ─────────────────────────────────────────────────────────────
    lines += [
        "📎 *الوثائق:*",
        f"  {doc_icon(profile.passport_file_id)} جواز   "
        f"{doc_icon(profile.visa_file_id)} تأشيرة   "
        f"{doc_icon(profile.latest_residency_file_id)} إقامة",
    ]

    lines.append(_THIN)

    # ── History ───────────────────────────────────────────────────────────────
    if history:
        lines.append(f"🕓 *آخر {min(len(history), HISTORY_DISPLAY_LIMIT)} أحداث:*")
        for h in history[:HISTORY_DISPLAY_LIMIT]:
            date_part = h.created_at[:10] if h.created_at else ""
            comp_tag  = " (مرافق)" if h.companion_id else ""
            lines.append(f"  • {h.action_label}{comp_tag}  {date_part}")
    else:
        lines.append("🕓 *السجل:*  لا توجد أحداث مسجلة")

    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton("🪪 تجديد الإقامة",  callback_data=f"rnr:start_{profile.id}"),
            InlineKeyboardButton("📋 تم التقديم",     callback_data=f"rnf:submitted_{profile.id}"),
        ],
        [
            InlineKeyboardButton("📄 ملف PDF",         callback_data=f"{RNA}:pdf_{profile.id}"),
            InlineKeyboardButton("📎 إرسال الوثائق",  callback_data=f"{RNA}:send_docs_{profile.id}"),
        ],
        [
            InlineKeyboardButton("⬅️ رجوع",            callback_data=f"{RN}:archive"),
        ],
    ]
    # Show quick-edit button only when expiry date is missing
    if not profile.expiry_date:
        rows.insert(1, [
            InlineKeyboardButton(
                "📅 تعديل تاريخ الانتهاء",
                callback_data=f"{RNA}:edit_expiry_{profile.id}",
            ),
        ])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


# ── Search ────────────────────────────────────────────────────────────────────

def build_search_prompt(*, error: bool = False) -> tuple[str, InlineKeyboardMarkup]:
    lines = [_DIVIDER, "🔍  **البحث عن مريض**", ""]
    if error:
        lines += ["⚠️ لم يتم العثور على نتائج. حاول مجدداً.", ""]
    lines.append("أرسل اسم المريض أو جزء من الاسم:")
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ رجوع للأرشيف", callback_data=f"{RN}:archive"),
    ]])
    return "\n".join(lines), kb


def build_search_results(results, query: str) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER,
        f"🔍  **نتائج البحث:** _{query}_",
        "",
        f"تم العثور على {len(results)} نتيجة:",
        _THIN,
    ]
    rows: list[list[InlineKeyboardButton]] = []
    for p in results:
        icon    = format_status_icon(p.status)
        warning = format_expiry_warning_inline(p.expiry_date)
        rows.append([
            InlineKeyboardButton(
                f"{icon} {p.name[:28]}{warning}",
                callback_data=f"{RNA}:view_{p.id}",
            )
        ])
    rows.append([
        InlineKeyboardButton("🔍 بحث جديد",      callback_data=f"{RNA}:search"),
        InlineKeyboardButton("⬅️ رجوع للأرشيف", callback_data=f"{RN}:archive"),
    ])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


# ── Add patient — batch flow (mirrors arrivals) ───────────────────────────────

def build_date_prompt() -> tuple[str, InlineKeyboardMarkup]:
    text = f"{_DIVIDER}\n➕  **إضافة دفعة جديدة**\n\nاختر تاريخ التسجيل:"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 اليوم",           callback_data=f"{RNA}:date_today")],
        [InlineKeyboardButton("🗓️ اختر من التقويم", callback_data=f"{RNA}:date_calendar")],
        [InlineKeyboardButton("❌ إلغاء",            callback_data=f"{RN}:main")],
    ])
    return text, kb


def build_date_calendar_prompt(*, error: bool = False) -> tuple[str, InlineKeyboardMarkup]:
    lines = [_DIVIDER, "🗓️  **اختر التاريخ من التقويم**", ""]
    if error:
        lines += ["⚠️ تاريخ غير صحيح. استخدم التقويم أدناه.", ""]
    lines.append("اختر يوماً من التقويم:")
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RNA}:start"),
    ]])
    return "\n".join(lines), kb


def build_patient_count_prompt(session) -> tuple[str, InlineKeyboardMarkup]:
    date_str = session.created_at[:10] if session.created_at else "—"
    text = (
        f"{_DIVIDER}\n👥  **عدد المرضى**\n\n"
        f"📅 التاريخ: *{date_str}*\n{_THIN}\n\n"
        "كم عدد المرضى في هذه الدفعة؟"
    )
    rows = [
        [InlineKeyboardButton(str(i), callback_data=f"{RNA}:count_{i}") for i in range(1, 6)],
        [InlineKeyboardButton(str(i), callback_data=f"{RNA}:count_{i}") for i in range(6, 11)],
        [InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RNA}:start"),
         InlineKeyboardButton("❌ إلغاء", callback_data=f"{RN}:main")],
    ]
    return text, InlineKeyboardMarkup(rows)


def build_p_name_prompt(session) -> tuple[str, InlineKeyboardMarkup]:
    idx   = session.patient_index + 1
    total = session.patient_count
    text  = (
        f"{_DIVIDER}\n"
        f"👤  **مريض {idx} من {total}**\n\n"
        f"✏️ أرسل اسم المريض:"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{RN}:main"),
    ]])
    return text, kb


def build_p_visa_expiry_prompt(session) -> tuple[str, InlineKeyboardMarkup]:
    idx    = session.patient_index + 1
    total  = session.patient_count
    p_name = session.current_patient.get("name", "—")
    text   = (
        f"{_DIVIDER}\n"
        f"📅  **تاريخ انتهاء التأشيرة** — مريض {idx}/{total}\n\n"
        f"المريض: *{p_name}*\n{_THIN}\n\n"
        "اختر تاريخ انتهاء التأشيرة من التقويم:"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗓️ فتح التقويم",  callback_data=f"{RNA}:visa_expiry_cal")],
        [InlineKeyboardButton("⬅️ رجوع",          callback_data=f"{RNA}:back_p_name"),
         InlineKeyboardButton("❌ إلغاء",          callback_data=f"{RN}:main")],
    ])
    return text, kb


def build_p_passport_prompt(session) -> tuple[str, InlineKeyboardMarkup]:
    idx    = session.patient_index + 1
    total  = session.patient_count
    p_name = session.current_patient.get("name", "—")
    text   = (
        f"{_DIVIDER}\n"
        f"📎  **صورة الجواز** — مريض {idx}/{total}\n\n"
        f"المريض: *{p_name}*\n{_THIN}\n\n"
        "📸 أرسل صورة الجواز:"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RNA}:back_p_visa_expiry"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{RN}:main"),
    ]])
    return text, kb


def build_p_visa_prompt(session) -> tuple[str, InlineKeyboardMarkup]:
    idx    = session.patient_index + 1
    total  = session.patient_count
    p_name = session.current_patient.get("name", "—")
    text   = (
        f"{_DIVIDER}\n"
        f"📎  **صورة التأشيرة** — مريض {idx}/{total}\n\n"
        f"المريض: *{p_name}*\n{_THIN}\n\n"
        "📸 أرسل صورة التأشيرة:"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RNA}:back_p_passport"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{RN}:main"),
    ]])
    return text, kb


def build_p_has_companion_prompt(session) -> tuple[str, InlineKeyboardMarkup]:
    idx    = session.patient_index + 1
    total  = session.patient_count
    p_name = session.current_patient.get("name", "—")
    text   = (
        f"{_DIVIDER}\n"
        f"👥  **مرافق؟** — مريض {idx}/{total}\n\n"
        f"المريض: *{p_name}*\n{_THIN}\n\n"
        "هل يوجد مرافق لهذا المريض؟"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ نعم", callback_data=f"{RNA}:companion_yes"),
         InlineKeyboardButton("❌ لا",  callback_data=f"{RNA}:companion_no")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RNA}:back_p_visa"),
         InlineKeyboardButton("🚫 إلغاء", callback_data=f"{RN}:main")],
    ])
    return text, kb


def build_c_name_prompt(session) -> tuple[str, InlineKeyboardMarkup]:
    p_name  = session.current_patient.get("name", "—")
    c_count = len(session.current_patient.get("companions", []))
    text    = (
        f"{_DIVIDER}\n"
        f"👤  **مرافق {c_count + 1}**\n\n"
        f"المريض: *{p_name}*\n{_THIN}\n\n"
        "✏️ أرسل اسم المرافق:"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{RN}:main"),
    ]])
    return text, kb


def build_c_visa_expiry_prompt(session) -> tuple[str, InlineKeyboardMarkup]:
    p_name = session.current_patient.get("name", "—")
    c_name = session.current_companion.get("name", "—")
    text   = (
        f"{_DIVIDER}\n"
        f"📅  **انتهاء تأشيرة المرافق**\n\n"
        f"المريض: *{p_name}*\n"
        f"المرافق: *{c_name}*\n{_THIN}\n\n"
        "اختر تاريخ انتهاء التأشيرة:"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗓️ فتح التقويم",  callback_data=f"{RNA}:c_visa_expiry_cal")],
        [InlineKeyboardButton("⬅️ رجوع",          callback_data=f"{RNA}:back_c_name"),
         InlineKeyboardButton("❌ إلغاء",          callback_data=f"{RN}:main")],
    ])
    return text, kb


def build_c_passport_prompt(session) -> tuple[str, InlineKeyboardMarkup]:
    p_name = session.current_patient.get("name", "—")
    c_name = session.current_companion.get("name", "—")
    text   = (
        f"{_DIVIDER}\n"
        f"📎  **جواز المرافق**\n\n"
        f"المريض: *{p_name}*  •  المرافق: *{c_name}*\n{_THIN}\n\n"
        "📸 أرسل صورة الجواز:"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RNA}:back_c_visa_expiry"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{RN}:main"),
    ]])
    return text, kb


def build_c_visa_prompt(session) -> tuple[str, InlineKeyboardMarkup]:
    p_name = session.current_patient.get("name", "—")
    c_name = session.current_companion.get("name", "—")
    text   = (
        f"{_DIVIDER}\n"
        f"📎  **تأشيرة المرافق**\n\n"
        f"المريض: *{p_name}*  •  المرافق: *{c_name}*\n{_THIN}\n\n"
        "📸 أرسل صورة التأشيرة:"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RNA}:back_c_passport"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{RN}:main"),
    ]])
    return text, kb


def build_batch_notes_prompt(session) -> tuple[str, InlineKeyboardMarkup]:
    count = len(session.completed_patients)
    text  = (
        f"{_DIVIDER}\n"
        f"📝  **ملاحظات الدفعة**\n\n"
        f"✅ تم إدخال {count} مريض\n{_THIN}\n\n"
        "أرسل ملاحظات عامة للدفعة، أو اضغط **⏭️ تخطي**:"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭️ تخطي", callback_data=f"{RNA}:skip_batch_notes"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{RN}:main"),
    ]])
    return text, kb


def build_review(session) -> tuple[str, InlineKeyboardMarkup]:
    date_str = session.created_at[:10] if session.created_at else "—"
    notes    = session.batch_notes or "لا توجد"
    lines    = [
        f"{_DIVIDER}",
        "🪪  **مراجعة الدفعة**",
        "",
        f"📅 التاريخ: *{date_str}*",
        f"👥 عدد المرضى: *{len(session.completed_patients)}*",
        _THIN,
    ]
    for i, p in enumerate(session.completed_patients, 1):
        p_pass = "✅" if p.get("passport_file_id") else "⬜"
        p_visa = "✅" if p.get("visa_file_id")     else "⬜"
        comp   = "✅" if p.get("has_companion")    else "❌"
        exp    = format_expiry_date(p.get("visa_expiry", ""))
        lines += [
            "",
            f"*{i}.* {p.get('name', '—')}",
            f"تأشيرة: {exp}  •  مرافق: {comp}",
            f"📎 {p_pass} جواز   {p_visa} تأشيرة",
        ]
        for c in p.get("companions", []):
            c_pass = "✅" if c.get("passport_file_id") else "⬜"
            c_visa = "✅" if c.get("visa_file_id")     else "⬜"
            lines.append(f"↳ {c.get('name', '—')}  📎 {c_pass} جواز  {c_visa} تأشيرة")
    lines += [_THIN, f"📝 *الملاحظات:*  {notes}", "", "هل تريد نشر الدفعة؟"]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ نشر",   callback_data=f"{RNA}:confirm"),
         InlineKeyboardButton("❌ إلغاء", callback_data=f"{RNA}:cancel")],
        [InlineKeyboardButton("⬅️ رجوع للملاحظات", callback_data=f"{RNA}:back_to_batch_notes")],
    ])
    return "\n".join(lines), kb


# ── Terminal ──────────────────────────────────────────────────────────────────

def build_success(count: int) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"✅ *تم حفظ الدفعة بنجاح*\n\n"
        f"👥 عدد المرضى المُسجَّلين: *{count}*"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ دفعة جديدة", callback_data=f"{RNA}:start")],
        [InlineKeyboardButton("📁 الأرشيف",    callback_data=f"{RN}:archive")],
        [InlineKeyboardButton("🪪 الإقامات",   callback_data=f"{RN}:main")],
    ])
    return text, kb


def build_cancelled() -> tuple[str, InlineKeyboardMarkup]:
    text = "❌ *تم إلغاء العملية.*\n\nيمكنك البدء من جديد في أي وقت."
    kb   = InlineKeyboardMarkup([[InlineKeyboardButton("🪪 الإقامات", callback_data=f"{RN}:main")]])
    return text, kb


def build_error(message: str = "") -> tuple[str, InlineKeyboardMarkup]:
    text = f"❌ *خطأ*\n\n{message or 'حدث خطأ غير متوقع.'}"
    kb   = InlineKeyboardMarkup([[InlineKeyboardButton("🪪 الإقامات", callback_data=f"{RN}:main")]])
    return text, kb
