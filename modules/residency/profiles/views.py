# modules/residency/profiles/views.py
# All view builders for the profiles sub-module:
# main menu, archive list, profile detail, add-patient steps.

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from modules.residency.constants import PROFILES_PAGE_SIZE
from modules.residency.views import (
    format_status, format_status_icon, format_expiry_date,
    format_days_remaining, format_expiry_warning_inline, doc_icon,
    effective_status,
    _DIVIDER, _THIN, _NONE,
)

RN  = "rn"
RNA = "rna"


# ── Main menu ─────────────────────────────────────────────────────────────────

def build_residency_main_menu() -> tuple[str, InlineKeyboardMarkup]:
    text = f"{_DIVIDER}\n🪪  **الإقامات**\n\nاختر القسم:"
    # ✅ زرّ واحد لا أكثر: كل شيء صار عبر «📁 أرشيف المرضى» (قرار المستخدم
    # صراحةً). أُزيل «➕ إضافة مريض جديد» سابقاً (مصدر الأسماء الوحيد هو
    # الواصلون)، وأُزيل الآن «📤 الرفع والمتابعة» — متابعة تقديم الأوراق
    # وإضافة المرافقين ورفع فورم C/الصورة صارت كلها أزراراً مباشرة على ملف
    # كل مريض (يُفتح من الأرشيف)، وشاشتا «⏰ المتابعة» و«⏳ المرافقون
    # المعلقون» انتقلتا لتكونا زرّين في شاشة الأرشيف نفسها.
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📁 أرشيف المرضى", callback_data=f"{RN}:archive")],
    ])
    return text, kb


# ── Archive list ──────────────────────────────────────────────────────────────

def build_archive_list(
    profiles, *, page: int, total: int,
    expiring_count: int = 0, pending_count: int = 0,
) -> tuple[str, InlineKeyboardMarkup]:
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
        # ✅ الأيام المتبقية تظهر **دائماً** هنا. كانت تُبنى من
        # `format_expiry_warning_inline` التي تُرجع فراغاً إذا تبقّى أكثر من
        # 30 يوماً — فبدت الحالات الجديدة (كأنها) بلا أيام متبقية إطلاقاً،
        # وهي في الحقيقة سليمة وبعيدة عن الانتهاء.
        for p in profiles:
            icon = format_status_icon(effective_status(p.status, p.expiry_date))
            comp = f"  +{p.companion_count} مرافق" if p.companion_count else ""
            days = format_days_remaining(p.expiry_date)
            lines += [
                "",
                f"{icon} *{p.name}*{comp}",
                f"     ⏳ {days}",
            ]

    rows: list[list[InlineKeyboardButton]] = []

    # Search button at the top
    rows.append([InlineKeyboardButton("🔍 بحث", callback_data=f"{RNA}:search")])

    # Patient buttons (one per row)
    for p in profiles:
        icon = format_status_icon(effective_status(p.status, p.expiry_date))
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

    # ✅ تصدير الأرشيف كاملاً (كل الصفحات لا الصفحة الحالية فقط) — ملف Excel
    # فيه المرضى ومرافقوهم وتواريخ انتهاء الإقامة والجواز، ملوَّن حسب القرب
    # من الانتهاء ومع فلتر تلقائي.
    rows.append([
        InlineKeyboardButton("📊 Excel", callback_data=f"{RNA}:export_ask_xlsx"),
        InlineKeyboardButton("📄 PDF",   callback_data=f"{RNA}:export_ask_pdf"),
    ])

    # ✅ منقولان هنا من شاشة «📤 الرفع والمتابعة» المحذوفة — قرار المستخدم:
    # كل شيء عبر الأرشيف. الهدفان (`rn:followup` / `rn:pending`) لم يتغيّرا،
    # فقط موضع الزرّين.
    rows.append([
        InlineKeyboardButton(f"⏰ المتابعة ({expiring_count})",       callback_data=f"{RN}:followup"),
        InlineKeyboardButton(f"⏳ المرافقون المعلقون ({pending_count})", callback_data=f"{RN}:pending"),
    ])

    rows.append([
        # ⚠️ لا زرّ «➕ إضافة جديد» هنا — أُزيل عمداً مع زرّ القائمة الرئيسية
        # (نفس السبب: مصدر الأسماء الوحيد هو الواصلون).
        InlineKeyboardButton("⬅️ رجوع",       callback_data=f"{RN}:main"),
    ])

    return "\n".join(lines), InlineKeyboardMarkup(rows)


# ── تصدير الأرشيف — خياران قبل الإنشاء (طلب المستخدم صراحةً) ───────────────────

_EXPORT_FMT_LABEL = {"pdf": "📄 PDF", "xlsx": "📊 Excel"}


def build_export_passport_prompt(fmt: str) -> tuple[str, InlineKeyboardMarkup]:
    """السؤال الأول: تضمين عمود انتهاء الجواز، أم الإقامات فقط."""
    text = (
        f"{_DIVIDER}\n{_EXPORT_FMT_LABEL.get(fmt, fmt)}  **تصدير الأرشيف**\n\n"
        "هل يتضمّن الملف تاريخ انتهاء الجواز؟"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 مع تاريخ الجواز",        callback_data=f"{RNA}:export_dst_{fmt}_y")],
        [InlineKeyboardButton("🪪 الإقامات فقط (بلا جواز)", callback_data=f"{RNA}:export_dst_{fmt}_n")],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"{RN}:archive")],
    ])
    return text, kb


def build_export_destination_prompt(fmt: str, include_passport: bool) -> tuple[str, InlineKeyboardMarkup]:
    """السؤال الثاني: نشر في المجموعة، أم للمستخدم فقط بلا نشر."""
    pas = "y" if include_passport else "n"
    text = (
        f"{_DIVIDER}\n{_EXPORT_FMT_LABEL.get(fmt, fmt)}  **تصدير الأرشيف**\n\n"
        "قبل الإنشاء — أين يُرسَل الملف؟"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 نشر في المجموعة",       callback_data=f"{RNA}:export_go_{fmt}_{pas}_group")],
        [InlineKeyboardButton("👤 لي فقط (بلا نشر)",       callback_data=f"{RNA}:export_go_{fmt}_{pas}_user")],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"{RN}:archive")],
    ])
    return text, kb


# ── Profile detail ────────────────────────────────────────────────────────────

def build_profile_detail(profile, companions, missing_items=()) -> tuple[str, InlineKeyboardMarkup]:
    comp_count   = len(companions)
    # ✅ الحالة الزمنية تُشتقّ من التاريخ — العمود المخزَّن يبقى "active" أبداً
    _status      = effective_status(profile.status, profile.expiry_date)
    status_icon  = format_status_icon(_status)
    status_label = format_status(_status)

    # ✅ «رقم الإقامة» أُزيل من هذه الشاشة بطلب المستخدم — الحقل ما زال في
    # قاعدة البيانات وفي مسار التجديد، لكنه لا يُعرض هنا لأنه غير مطلوب.
    lines = [
        _DIVIDER,
        "🪪  **ملف المريض**",
        "",
        f"👤 *{profile.name}*",
        "",
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
            _c_status = effective_status(c.status, c.expiry_date)
            c_icon  = format_status_icon(_c_status)
            c_label = format_status(_c_status)
            c_exp   = format_expiry_date(c.expiry_date)
            c_days  = format_days_remaining(c.expiry_date)
            lines += [
                "",
                f"  *{i}.* 👤 *{c.name}*",
                f"  📅 تاريخ الانتهاء:  {c_exp}",
                f"  ⏳ الأيام المتبقية:  {c_days}",
                f"  📊 الحالة:  {c_icon} {c_label}",
            ]

    lines.append(_THIN)

    # ── Documents ─────────────────────────────────────────────────────────────
    # ✅ نصّ صريح بدل المربعات: المربع الأبيض وحده لا يميّز «غير مرفوع» عن
    # «لا ينطبق»، وكانت الوثائق الأربع مكدَّسة في سطر واحد يصعب قراءته.
    def _doc(file_id) -> str:
        return "✅ يوجد" if file_id else "⬜ لا يوجد"

    lines += [
        "📎 *الوثائق:*",
        f"  جواز السفر:  {_doc(profile.passport_file_id)}",
        f"  التأشيرة:  {_doc(profile.visa_file_id)}",
        f"  الإقامة:  {_doc(profile.latest_residency_file_id)}",
        f"  فورم C:  {_doc(getattr(profile, 'form_c_file_id', ''))}",
        f"  الصورة الشخصية:  {_doc(getattr(profile, 'photo_file_id', ''))}",
    ]

    lines.append(_THIN)

    # ── الطلبات الناقصة ────────────────────────────────────────────────────────
    if missing_items:
        lines.append(f"📋 *طلبات ناقصة بانتظار الرفع ({len(missing_items)}):*")
        for m in missing_items:
            lines.append(f"  • {m.description}")
        lines.append(_THIN)

    rows: list[list[InlineKeyboardButton]] = []

    # ✅ «هل ملفه معلق بسبب طلب إضافي» — يظهر فقط حين تكون هذه هي الحالة
    # فعلاً (مرافق لم يُستكمَل رغم صدور إقامة المريض)، بدل شاشة منفصلة
    # لعرض كل الحالات المعلَّقة دفعة واحدة.
    if _status == "dependent_pending":
        rows.append([
            InlineKeyboardButton("📋 استكمال المرافقين المعلَّقين", callback_data=f"rnf:complete_{profile.id}"),
        ])

    # ✅ تسجيل طلب ناقص متاح دائماً (طلب جديد يُكتشَف في أي وقت، لا فقط عند
    # التقديم) — نفس الآلية التي تُفعَّل تلقائياً عند الإجابة بـ«لا» على
    # «هل اكتملت الأوراق؟» عند الضغط على زر التقديم أعلاه.
    missing_row = [InlineKeyboardButton("📝 تسجيل طلب ناقص", callback_data=f"{RNA}:missing_new_{profile.id}")]
    if len(missing_items) == 1:
        missing_row.append(InlineKeyboardButton(
            "📎 رفع الطلب المعلَّق", callback_data=f"{RNA}:missing_resolve_{missing_items[0].id}"))
    elif len(missing_items) > 1:
        missing_row.append(InlineKeyboardButton(
            f"📎 رفع طلب معلَّق ({len(missing_items)})", callback_data=f"{RNA}:missing_pick_{profile.id}"))
    rows.append(missing_row)

    rows.append([
        InlineKeyboardButton("🪪 تجديد الإقامة", callback_data=f"rnr:start_{profile.id}"),
        InlineKeyboardButton("➕ إضافة مرافق",   callback_data=f"{RNA}:add_comp_{profile.id}"),
    ])

    # ✅ زر موحَّد واحد بدل زرَّي فورم C/الصورة المنفصلين سابقاً — يفتح قائمة
    # تشمل الاثنين بالإضافة لجواز/فيزا/تذكرة (لم يكن لها أي مسار رفع من
    # قبل — تُستخدَم لتصحيح ما تم تخطّيه بالخطأ أثناء الواصلين). الإقامة
    # نفسها مستبعَدة عمداً وتبقى حصراً على مسار «🪪 تجديد الإقامة» الكامل
    # فلا يصير للحقل الواحد مصدران.
    rows.append([
        InlineKeyboardButton("🗂️ رفع وثيقة", callback_data=f"rnu:docmenu_{profile.id}"),
    ])

    # ✅ يظهر فقط بعد اكتمال الصورة الشخصية وفورم C معاً، وطالما لم يُؤرشَف
    # الملف بعد — اعتماد يدوي صريح (بطلب المستخدم: لا نقل تلقائي بمجرد
    # اكتمال الرفع). بعد أي تجديد لاحق (rnr:) يعود status إلى "issued"
    # فيظهر الزر من جديد ليُعتمَد مجدداً.
    if profile.photo_file_id and profile.form_c_file_id and profile.status != "archived":
        rows.append([
            InlineKeyboardButton(
                "✅ اعتماد ونقل إلى الأرشيف", callback_data=f"{RNA}:archive_confirm_{profile.id}",
            ),
        ])

    rows.append([
        InlineKeyboardButton("📄 ملف PDF", callback_data=f"{RNA}:pdf_{profile.id}"),
    ])
    rows.append([
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:archive"),
    ])
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

# ── إضافة مرافق لملف موجود ────────────────────────────────────────────────────

def build_add_companion_name_prompt(profile_name: str, profile_id: int) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"{_DIVIDER}\n➕  **إضافة مرافق**\n\n"
        f"المريض: *{profile_name}*\n{_THIN}\n\n"
        "✏️ اكتب اسم المرافق:"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{RNA}:view_{profile_id}"),
    ]])
    return text, kb


def build_add_companion_visa_expiry_prompt(name: str, profile_id: int) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"{_DIVIDER}\n➕  **إضافة مرافق — {name}**\n\n"
        "اختر تاريخ انتهاء التأشيرة، أو اضغط **⏭️ تخطي**."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📆 اختيار من التقويم", callback_data=f"{RNA}:add_comp_cal_{profile_id}")],
        [InlineKeyboardButton("⏭️ تخطي",              callback_data=f"{RNA}:add_comp_skipexp_{profile_id}")],
        [InlineKeyboardButton("❌ إلغاء",              callback_data=f"{RNA}:view_{profile_id}")],
    ])
    return text, kb


def build_add_companion_saved(name: str, profile_id: int) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"{_DIVIDER}\n✅  **تمت إضافة المرافق**\n\n"
        f"👤 {name}\n\n"
        "أُضيف إلى ملف المريض."
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("👁 عرض الملف", callback_data=f"{RNA}:view_{profile_id}"),
    ]])
    return text, kb


# ── الطلبات الناقصة (تسجيل جديد / رفع لإغلاق طلب) ─────────────────────────────

def build_missing_item_prompt(profile_name: str, profile_id: int) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"{_DIVIDER}\n📝  **تسجيل طلب ناقص**\n\n"
        f"المريض: *{profile_name}*\n{_THIN}\n\n"
        "✏️ اكتب ما هو الطلب/المستند الناقص:"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{RNA}:view_{profile_id}"),
    ]])
    return text, kb


def build_missing_item_saved(profile_name: str, description: str, profile_id: int) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"{_DIVIDER}\n✅  **تم تسجيل الطلب**\n\n"
        f"👤 {profile_name}\n"
        f"📝 {description}\n\n"
        "نُشر للمجموعة للمتابعة، وسيُذكَّر به يومياً حتى يُرفَع."
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("👁 عرض الملف", callback_data=f"{RNA}:view_{profile_id}"),
    ]])
    return text, kb


def build_missing_items_pick(profile_name: str, profile_id: int, items) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER, "📎  **اختر الطلب المُراد رفعه**", "",
        f"المريض: *{profile_name}*", _THIN, "",
    ]
    rows: list[list[InlineKeyboardButton]] = []
    for m in items:
        lines.append(f"• {m.description}")
        rows.append([InlineKeyboardButton(
            f"📎 {m.description[:30]}", callback_data=f"{RNA}:missing_resolve_{m.id}")])
    rows.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"{RNA}:view_{profile_id}")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


def build_missing_item_resolved(profile_name: str, description: str, profile_id: int) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"{_DIVIDER}\n✅  **تم رفع الطلب**\n\n"
        f"👤 {profile_name}\n"
        f"📝 {description}\n\n"
        "جاري انتظار الإقامة."
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("👁 عرض الملف", callback_data=f"{RNA}:view_{profile_id}"),
    ]])
    return text, kb


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
        icon    = format_status_icon(effective_status(p.status, p.expiry_date))
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
