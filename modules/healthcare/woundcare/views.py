# modules/healthcare/woundcare/views.py
# Pure view builders for the woundcare operational flow — official 11-step spec.
# No I/O, no context, no DB — data in, (text, keyboard) out.
#
# Steps: التاريخ → المريض → القسم الطبي → اسم العملية → مرحلة المجارحة
#        → وصف الحالة → المستلزمات → الصور → الملاحظات → اسم الصحي
#        → مراجعة → نشر

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from modules.healthcare.woundcare.constants import STAFF_LIST  # noqa: F401  (re-exported for callers)
from modules.healthcare.woundcare.session import WoundcareAddSession
from modules.healthcare.views import format_arabic_datetime, format_image_count

# ── Callback prefixes ─────────────────────────────────────────────────────────
HC  = "hc"    # healthcare navigation (shared across module)
WCA = "wca"   # woundcare flow

_DIVIDER = "━━━━━━━━━━━━━━━━━━━━"
_THIN    = "─────────────────────"


# ── Step 1: اختيار التاريخ ────────────────────────────────────────────────────

def build_date_prompt() -> tuple[str, InlineKeyboardMarkup]:
    """Date selection screen — first visible step of every woundcare entry."""
    from datetime import datetime
    from modules.healthcare.views import format_arabic_date
    today_str = format_arabic_date(datetime.utcnow())
    lines = [
        _DIVIDER,
        "📅  **اختر التاريخ**",
        "",
        f"التاريخ الحالي: *{today_str}*",
        _THIN,
        "",
        "اختر طريقة تحديد تاريخ التقرير:",
    ]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ اختيار تاريخ اليوم", callback_data=f"{WCA}:date_today")],
        [InlineKeyboardButton("📆 اختيار من التقويم",  callback_data=f"{WCA}:date_calendar")],
        [InlineKeyboardButton("⬅️ رجوع",               callback_data=f"{HC}:woundcare")],
    ])
    return "\n".join(lines), kb


def build_date_calendar_prompt(*, error: bool = False) -> tuple[str, InlineKeyboardMarkup]:
    """Free-text date entry — shown when user chooses manual date entry."""
    lines = [
        _DIVIDER,
        "📆  **إدخال التاريخ يدوياً**",
        "",
    ]
    if error:
        lines += ["⚠️ *صيغة التاريخ غير صحيحة.* يرجى المحاولة مجدداً.", ""]
    lines += [
        "أرسل التاريخ بإحدى الصيغ التالية:",
        "*يوم/شهر/سنة*  (مثال: 22/05/2026)",
        "أو:  22-05-2026",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{WCA}:start"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{HC}:woundcare"),
    ]])
    return "\n".join(lines), kb


# ── Woundcare submenu ─────────────────────────────────────────────────────────

def build_woundcare_menu() -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"{_DIVIDER}\n"
        f"🩺  **المجارحة والعناية بالجرح**\n\n"
        "اختر العملية:"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ تسجيل حالة جرح جديدة", callback_data=f"{WCA}:start")],
        [InlineKeyboardButton("⬅️ رجوع",                  callback_data=f"{HC}:main")],
    ])
    return text, kb


# ── Step 3b: "أخرى" free-text department prompt ───────────────────────────────

def build_dept_other_prompt(session: WoundcareAddSession) -> tuple[str, InlineKeyboardMarkup]:
    """Direct free-text prompt — shown when 'أخرى' was selected in department multiselect."""
    known = [lbl for lbl in session.medical_department_labels if lbl != "أخرى"]
    known_text = "، ".join(known) if known else "—"
    lines = [
        _DIVIDER,
        "🏥  **إضافة قسم طبي جديد**",
        "",
        f"المريض: {session.patient_name}",
        f"🏥 القسم الطبي: {known_text}",
        _THIN,
        "",
        "أرسل اسم القسم الطبي لإضافته:",
        "_(سيُحفظ ويظهر تلقائياً في المرات القادمة)_",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 رجوع", callback_data=f"{WCA}:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{WCA}:cancel"),
    ]])
    return "\n".join(lines), kb


# ── Step 4: اسم العملية ───────────────────────────────────────────────────────

def build_operation_name_prompt(session: WoundcareAddSession) -> tuple[str, InlineKeyboardMarkup]:
    """Free-text prompt for اسم العملية — required, no skip."""
    depts = "، ".join(session.medical_department_labels) if session.medical_department_labels else "—"
    lines = [
        _DIVIDER,
        "✍️  **اسم العملية**",
        "",
        f"المريض: {session.patient_name}",
        f"القسم: {depts}",
        _THIN,
        "",
        "أرسل اسم العملية أو الإجراء الذي تم تنفيذه.",
        "(مثال: شق وتصريف، تنظيف جرح وتضميد…)",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 رجوع", callback_data=f"{WCA}:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{WCA}:cancel"),
    ]])
    return "\n".join(lines), kb


# ── Step 5: مرحلة المجارحة ────────────────────────────────────────────────────

def build_phase_prompt(session: WoundcareAddSession) -> tuple[str, InlineKeyboardMarkup]:
    """Single-select: 4 phase options."""
    lines = [
        _DIVIDER,
        "🩹  **مرحلة المجارحة**",
        "",
        f"المريض: {session.patient_name}",
        f"العملية: {session.operation_name}",
        _THIN,
        "",
        "اختر مرحلة المجارحة:",
    ]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("قبل العملية",               callback_data=f"{WCA}:phase_pre_op")],
        [InlineKeyboardButton("الأولى بعد العملية",        callback_data=f"{WCA}:phase_post_1")],
        [InlineKeyboardButton("بعد العملية الأخيرة",       callback_data=f"{WCA}:phase_post_last")],
        [InlineKeyboardButton("مجارحة دورية / جرح مزمن",  callback_data=f"{WCA}:phase_chronic")],
        [
            InlineKeyboardButton("🔙 رجوع", callback_data=f"{WCA}:back"),
            InlineKeyboardButton("❌ إلغاء", callback_data=f"{WCA}:cancel"),
        ],
    ])
    return "\n".join(lines), kb


# ── Step 6b: "أخرى" free-text condition prompt ────────────────────────────────

def build_description_other_prompt(session: WoundcareAddSession) -> tuple[str, InlineKeyboardMarkup]:
    """Free-text prompt — shown when 'أخرى' was selected in condition multiselect."""
    known = [lbl for lbl in session.condition_labels if lbl != "أخرى"]
    known_text = "، ".join(known) if known else "—"
    lines = [
        _DIVIDER,
        "📝  **وصف حالة الجرح — تفاصيل إضافية**",
        "",
        f"المريض: {session.patient_name}",
        f"الحالة المحددة: {known_text}",
        _THIN,
        "",
        "أرسل وصفاً إضافياً لحالة الجرح:",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 رجوع", callback_data=f"{WCA}:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{WCA}:cancel"),
    ]])
    return "\n".join(lines), kb


# ── Step 7b: "أخرى" free-text supplies prompt ─────────────────────────────────

def build_supplies_other_prompt(session: WoundcareAddSession) -> tuple[str, InlineKeyboardMarkup]:
    """Direct free-text prompt — shown when 'أخرى' was selected in supplies multiselect."""
    known = [lbl for lbl in session.supply_labels if lbl != "أخرى"]
    known_text = "، ".join(known) if known else "—"
    lines = [
        _DIVIDER,
        "🧰  **إضافة مستلزم طبي جديد**",
        "",
        f"المريض: {session.patient_name}",
        f"المستلزمات المحددة: {known_text}",
        _THIN,
        "",
        "أرسل اسم المستلزم الطبي لإضافته:",
        "_(سيُحفظ ويظهر تلقائياً في المرات القادمة)_",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 رجوع", callback_data=f"{WCA}:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{WCA}:cancel"),
    ]])
    return "\n".join(lines), kb


# ── Step 9: الملاحظات ─────────────────────────────────────────────────────────

def build_notes_prompt(session: WoundcareAddSession) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER,
        "📝  **الملاحظات السريرية**",
        "",
        f"المريض: {session.patient_name}",
        f"العملية: {session.operation_name}",
        f"المرحلة: {session.phase_label}",
        f"الصور: {format_image_count(session.image_count)}",
        _THIN,
        "",
        "أضف ملاحظاتك السريرية، أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏭️ تخطي",  callback_data=f"{WCA}:skip_notes"),
            InlineKeyboardButton("🔙 رجوع",   callback_data=f"{WCA}:back"),
            InlineKeyboardButton("❌ إلغاء",  callback_data=f"{WCA}:cancel"),
        ],
    ])
    return "\n".join(lines), kb


# ── Step 10: اسم الصحي — fixed single-select, REQUIRED ──────────────────────

def build_specialist_prompt(session: WoundcareAddSession) -> tuple[str, InlineKeyboardMarkup]:
    """
    Fixed 3-name selector — no free-text, no skip.
    Staff: د. فضل · د. سرور · د. زكريا
    """
    lines = [
        _DIVIDER,
        "👨‍⚕️  **اسم الصحي**",
        "",
        f"المريض: {session.patient_name}",
        _THIN,
        "",
        "اختر اسم الصحي المسؤول عن الإجراء:",
    ]
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("د. فضل",   callback_data=f"{WCA}:sp_fadl"),
            InlineKeyboardButton("د. سرور",  callback_data=f"{WCA}:sp_sarour"),
            InlineKeyboardButton("د. زكريا", callback_data=f"{WCA}:sp_zakariya"),
        ],
        [
            InlineKeyboardButton("🔙 رجوع", callback_data=f"{WCA}:back"),
            InlineKeyboardButton("❌ إلغاء", callback_data=f"{WCA}:cancel"),
        ],
    ])
    return "\n".join(lines), kb


# ── Step 11a: مراجعة نهائية ───────────────────────────────────────────────────

_NONE = "➖ غير مضاف"


def build_review(session: WoundcareAddSession) -> tuple[str, InlineKeyboardMarkup]:
    """Full review summary before final save — all 11 workflow fields."""
    date_str    = format_arabic_datetime(session.created_at)
    dept_text   = "، ".join(session.medical_department_labels) or _NONE
    supply_list = "\n".join(f"  • {lbl}" for lbl in session.supply_labels) or _NONE

    # Build condition list — replace "أخرى" placeholder with the typed free-text
    _cond_labels = list(session.condition_labels)
    if session.condition_other:
        _cond_labels = [
            session.condition_other if lbl == "أخرى" else lbl
            for lbl in _cond_labels
        ]
    cond_list = "\n".join(f"  • {lbl}" for lbl in _cond_labels) or _NONE

    lines = [
        "🩺 *مراجعة تقرير المجارحة*",
        "",
        f"📅 *التاريخ:*  {date_str}",
        f"👤 *المريض:*  {session.patient_name}",
        "",
        f"🏥 *القسم الطبي:*  {dept_text}",
        "",
        f"✍️ *اسم العملية:*  {session.operation_name or _NONE}",
        f"🩹 *مرحلة المجارحة:*  {session.phase_label or _NONE}",
        "",
        "🩹 *وصف حالة الجرح:*",
        cond_list,
        "",
        "🧰 *المستلزمات الطبية المستخدمة:*",
        supply_list,
        "",
        f"📎 *الصور:*  {format_image_count(session.image_count) if session.image_count else _NONE}",
        "",
        f"📝 *الملاحظات:*  {session.notes if session.notes else _NONE}",
        "",
        f"👨‍⚕️ *المختص الصحي:*  {session.specialist_name or _NONE}",
        "",
        "هل تريد نشر هذا التقرير؟",
    ]

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 نشر التقرير",        callback_data=f"{WCA}:confirm"),
            InlineKeyboardButton("❌ إلغاء",               callback_data=f"{WCA}:cancel"),
        ],
        [InlineKeyboardButton("✏️ القسم الطبي",           callback_data=f"{WCA}:edit_dept"),
         InlineKeyboardButton("✏️ اسم العملية",           callback_data=f"{WCA}:edit_operation")],
        [InlineKeyboardButton("✏️ مرحلة المجارحة",        callback_data=f"{WCA}:edit_phase"),
         InlineKeyboardButton("✏️ وصف الحالة",            callback_data=f"{WCA}:edit_condition")],
        [InlineKeyboardButton("✏️ المستلزمات",             callback_data=f"{WCA}:edit_supplies"),
         InlineKeyboardButton("✏️ الصور",                  callback_data=f"{WCA}:edit_images")],
        [InlineKeyboardButton("✏️ الملاحظات",              callback_data=f"{WCA}:edit_notes"),
         InlineKeyboardButton("✏️ المختص الصحي",          callback_data=f"{WCA}:edit_specialist")],
    ])
    return "\n".join(lines), kb


# ── Success screen ────────────────────────────────────────────────────────────

def build_success(
    record_id:    int,
    patient_name: str,
    image_count:  int,
) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"✅ *تم حفظ ونشر تقرير المجارحة بنجاح*\n\n"
        f"رقم التقرير: `#{record_id}`\n"
        f"المريض: {patient_name}\n"
        f"الصور المرفوعة: {format_image_count(image_count)}\n\n"
        f"📤 تم إرسال التقرير للمسؤولين والمجموعة الصحية."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ حالة جرح جديدة",      callback_data=f"{WCA}:start")],
        [InlineKeyboardButton("🏥 القائمة الرئيسية",    callback_data=f"{HC}:main")],
    ])
    return text, kb


# ── Cancellation screen ───────────────────────────────────────────────────────

def build_cancelled() -> tuple[str, InlineKeyboardMarkup]:
    text = "❌ *تم إلغاء العملية.*\n\nيمكنك البدء من جديد في أي وقت."
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏥 القائمة الرئيسية", callback_data=f"{HC}:main")],
    ])
    return text, kb


# ── Error screen ──────────────────────────────────────────────────────────────

def build_error(message: str = "") -> tuple[str, InlineKeyboardMarkup]:
    body = message or "حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى."
    text = f"❌ *خطأ*\n\n{body}"
    kb   = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏥 القائمة الرئيسية", callback_data=f"{HC}:main")],
    ])
    return text, kb
