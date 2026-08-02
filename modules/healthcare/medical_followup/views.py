# modules/healthcare/medical_followup/views.py
# Pure view builders for the medical follow-up operational flow — official 11-step spec.
# No I/O, no context, no DB — data in, (text, keyboard) out.
#
# Steps: التاريخ → المريض → القسم الطبي → نوع الإجراء → الشكوى الرئيسية
#        → العلامات الحيوية (×4) → الأدوية والمستلزمات → الصور
#        → الملاحظات → اسم الصحي → مراجعة → نشر

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from modules.healthcare.medical_followup.constants import STAFF_LIST  # noqa: F401  (re-exported for callers)
from modules.healthcare.medical_followup.session import MedicalFollowupSession
from modules.healthcare.views import format_arabic_datetime, format_arabic_date, format_image_count

# ── Callback prefixes ─────────────────────────────────────────────────────────
HC   = "hc"     # healthcare navigation (shared across module)
HCFU = "hcfu"   # medical follow-up flow

_DIVIDER = "━━━━━━━━━━━━━━━━━━━━"
_THIN    = "─────────────────────"


# ── Step 1: اختيار التاريخ ────────────────────────────────────────────────────

def build_date_prompt() -> tuple[str, InlineKeyboardMarkup]:
    """Date selection screen — first visible step of every followup entry."""
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
        [InlineKeyboardButton("✅ اختيار تاريخ اليوم", callback_data=f"{HCFU}:date_today")],
        [InlineKeyboardButton("📆 اختيار من التقويم",  callback_data=f"{HCFU}:date_calendar")],
        [InlineKeyboardButton("⬅️ رجوع",               callback_data=f"{HC}:main")],
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
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{HCFU}:start"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{HC}:main"),
    ]])
    return "\n".join(lines), kb


# ── Followup submenu ──────────────────────────────────────────────────────────

def build_followup_menu() -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"{_DIVIDER}\n"
        f"📋  **المتابعة الطبية والإجراءات العلاجية**\n\n"
        "اختر العملية:"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ تسجيل إجراء طبي جديد", callback_data=f"{HCFU}:start")],
        [InlineKeyboardButton("⬅️ رجوع",                 callback_data=f"{HC}:main")],
    ])
    return text, kb


# ── Step 3b: "أخرى" free-text department prompt ───────────────────────────────

def build_dept_other_prompt(session: MedicalFollowupSession) -> tuple[str, InlineKeyboardMarkup]:
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
        InlineKeyboardButton("🔙 رجوع", callback_data=f"{HCFU}:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{HCFU}:cancel"),
    ]])
    return "\n".join(lines), kb


# ── Step 5b: "أخرى" free-text complaint prompt ───────────────────────────────

def build_complaint_other_prompt(session: MedicalFollowupSession) -> tuple[str, InlineKeyboardMarkup]:
    """Direct free-text prompt — shown when 'أخرى' was selected in complaint multiselect."""
    known = [lbl for lbl in session.complaint_labels if lbl != "أخرى"]
    known_text = "، ".join(known) if known else "—"
    lines = [
        _DIVIDER,
        "😷  **إضافة شكوى جديدة**",
        "",
        f"المريض: {session.patient_name}",
        f"الشكاوى المحددة: {known_text}",
        _THIN,
        "",
        "أرسل اسم الشكوى لإضافتها:",
        "_(سيُحفظ ويظهر تلقائياً في المرات القادمة)_",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 رجوع", callback_data=f"{HCFU}:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{HCFU}:cancel"),
    ]])
    return "\n".join(lines), kb


# ── Step 6a: العلامات الحيوية — درجة الحرارة ──────────────────────────────────

def build_vitals_temp_prompt(session: MedicalFollowupSession) -> tuple[str, InlineKeyboardMarkup]:
    """Vitals step 1/4 — Temperature. Required, no skip."""
    lines = [
        _DIVIDER,
        "🌡️  **العلامات الحيوية (1/4) — درجة الحرارة**",
        "",
        f"المريض: {session.patient_name}",
        _THIN,
        "",
        "أرسل درجة الحرارة (مثال: 37.2 °C):",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 رجوع", callback_data=f"{HCFU}:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{HCFU}:cancel"),
    ]])
    return "\n".join(lines), kb


# ── Step 6b: ضغط الدم ────────────────────────────────────────────────────────

def build_vitals_bp_prompt(session: MedicalFollowupSession) -> tuple[str, InlineKeyboardMarkup]:
    """Vitals step 2/4 — Blood Pressure. Required, no skip."""
    lines = [
        _DIVIDER,
        "❤️  **العلامات الحيوية (2/4) — ضغط الدم**",
        "",
        f"المريض: {session.patient_name}",
        f"الحرارة: {session.vitals_temp}",
        _THIN,
        "",
        "أرسل ضغط الدم (مثال: 120/80 mmHg):",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 رجوع", callback_data=f"{HCFU}:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{HCFU}:cancel"),
    ]])
    return "\n".join(lines), kb


# ── Step 6c: النبض ────────────────────────────────────────────────────────────

def build_vitals_pulse_prompt(session: MedicalFollowupSession) -> tuple[str, InlineKeyboardMarkup]:
    """Vitals step 3/4 — Pulse. Required, no skip."""
    lines = [
        _DIVIDER,
        "💓  **العلامات الحيوية (3/4) — النبض**",
        "",
        f"المريض: {session.patient_name}",
        f"الحرارة: {session.vitals_temp}",
        f"ضغط الدم: {session.vitals_bp}",
        _THIN,
        "",
        "أرسل معدل النبض (مثال: 80 bpm):",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 رجوع", callback_data=f"{HCFU}:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{HCFU}:cancel"),
    ]])
    return "\n".join(lines), kb


# ── Step 6d: تشبع الأكسجين ────────────────────────────────────────────────────

def build_vitals_spo2_prompt(session: MedicalFollowupSession) -> tuple[str, InlineKeyboardMarkup]:
    """Vitals step 4/4 — SpO2. Required, no skip."""
    lines = [
        _DIVIDER,
        "🫁  **العلامات الحيوية (4/4) — تشبع الأكسجين**",
        "",
        f"المريض: {session.patient_name}",
        f"الحرارة: {session.vitals_temp}",
        f"ضغط الدم: {session.vitals_bp}",
        f"النبض: {session.vitals_pulse}",
        _THIN,
        "",
        "أرسل نسبة تشبع الأكسجين (مثال: 98%):",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 رجوع", callback_data=f"{HCFU}:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{HCFU}:cancel"),
    ]])
    return "\n".join(lines), kb


# ── Step 7b: "أخرى" free-text meds/supply prompt ─────────────────────────────

def build_meds_supply_other_prompt(session: MedicalFollowupSession) -> tuple[str, InlineKeyboardMarkup]:
    """Direct free-text prompt — shown when 'أخرى' was selected in meds/supply multiselect."""
    known = [lbl for lbl in session.meds_supply_labels if lbl != "Other (Specify)"]
    known_text = "، ".join(known) if known else "—"
    lines = [
        _DIVIDER,
        "💊  **إضافة دواء أو مستلزم جديد**",
        "",
        f"المريض: {session.patient_name}",
        f"المحدد: {known_text}",
        _THIN,
        "",
        "أرسل اسم الدواء أو المستلزم لإضافته:",
        "_(سيُحفظ ويظهر تلقائياً في المرات القادمة)_",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 رجوع", callback_data=f"{HCFU}:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{HCFU}:cancel"),
    ]])
    return "\n".join(lines), kb


# ── Step 9: الملاحظات ─────────────────────────────────────────────────────────

def build_notes_prompt(session: MedicalFollowupSession) -> tuple[str, InlineKeyboardMarkup]:
    depts = "، ".join(session.medical_department_labels) if session.medical_department_labels else "—"
    procs = "، ".join(session.procedure_type_labels)     if session.procedure_type_labels     else "—"
    lines = [
        _DIVIDER,
        "📝  **الملاحظات السريرية**",
        "",
        f"المريض: {session.patient_name}",
        f"القسم: {depts}",
        f"الإجراء: {procs}",
        f"الصور: {format_image_count(session.image_count)}",
        _THIN,
        "",
        "أضف ملاحظاتك السريرية، أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏭️ تخطي",  callback_data=f"{HCFU}:skip_notes"),
            InlineKeyboardButton("🔙 رجوع",   callback_data=f"{HCFU}:back"),
            InlineKeyboardButton("❌ إلغاء",  callback_data=f"{HCFU}:cancel"),
        ],
    ])
    return "\n".join(lines), kb


# ── Step 10: اسم الصحي — fixed single-select, REQUIRED ──────────────────────

def build_specialist_prompt(session: MedicalFollowupSession) -> tuple[str, InlineKeyboardMarkup]:
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
            InlineKeyboardButton("د. فضل",   callback_data=f"{HCFU}:sp_fadl"),
            InlineKeyboardButton("د. سرور",  callback_data=f"{HCFU}:sp_sarour"),
        ],
        [
            InlineKeyboardButton("د. زكريا", callback_data=f"{HCFU}:sp_zakariya"),
            InlineKeyboardButton("د. مبروك", callback_data=f"{HCFU}:sp_mabrook"),
        ],
        [
            InlineKeyboardButton("🔙 رجوع", callback_data=f"{HCFU}:back"),
            InlineKeyboardButton("❌ إلغاء", callback_data=f"{HCFU}:cancel"),
        ],
    ])
    return "\n".join(lines), kb


# ── Step 11a: مراجعة نهائية — Interactive Editor ──────────────────────────────

def build_review(session: MedicalFollowupSession) -> tuple[str, InlineKeyboardMarkup]:
    date_str    = format_arabic_date(session.created_at)
    dept_text   = "، ".join(session.medical_department_labels) or "—"
    proc_text   = "، ".join(session.procedure_type_labels)     or "—"
    cmp_text    = "، ".join(session.complaint_labels)          or "—"
    supply_text = "، ".join(session.meds_supply_labels)        or "—"
    imgs        = format_image_count(session.image_count)
    notes       = session.notes or "لا توجد ملاحظات"

    vitals_parts = []
    if session.vitals_temp:  vitals_parts.append(f"🌡️ {session.vitals_temp}")
    if session.vitals_bp:    vitals_parts.append(f"🩸 {session.vitals_bp}")
    if session.vitals_pulse: vitals_parts.append(f"💓 {session.vitals_pulse}")
    if session.vitals_spo2:  vitals_parts.append(f"🫁 {session.vitals_spo2}")
    vitals_txt = "  ".join(vitals_parts) or "—"

    lines = [
        "📋 *مراجعة تقرير المتابعة الطبية*",
        "",
        f"📅 {date_str}",
        f"👤 {session.patient_name}  •  🏥 {dept_text}",
        f"📋 {proc_text}  •  😷 {cmp_text}",
        f"❤️ {vitals_txt}",
        f"💊 المستلزمات: {supply_text}",
        f"📎 {imgs}",
        f"📝 {notes}",
        f"👨‍⚕️ {session.specialist_name or '—'}",
        "",
        "هل تريد نشر هذا التقرير؟",
    ]

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 نشر التقرير", callback_data=f"{HCFU}:confirm"),
            InlineKeyboardButton("❌ إلغاء",         callback_data=f"{HCFU}:cancel"),
        ],
        [
            InlineKeyboardButton("✏️ القسم الطبي",   callback_data=f"{HCFU}:edit_dept"),
            InlineKeyboardButton("✏️ نوع الإجراء",  callback_data=f"{HCFU}:edit_proc"),
        ],
        [
            InlineKeyboardButton("✏️ الشكوى / الأعراض",  callback_data=f"{HCFU}:edit_complaint"),
            InlineKeyboardButton("✏️ العلامات الحيوية",   callback_data=f"{HCFU}:edit_vitals"),
        ],
        [
            InlineKeyboardButton("✏️ الأدوية / المستلزمات", callback_data=f"{HCFU}:edit_meds"),
            InlineKeyboardButton("✏️ الصور",                  callback_data=f"{HCFU}:edit_images"),
        ],
        [
            InlineKeyboardButton("✏️ الملاحظات",      callback_data=f"{HCFU}:edit_notes"),
            InlineKeyboardButton("✏️ المختص الصحي",  callback_data=f"{HCFU}:edit_specialist"),
        ],
    ])
    return "\n".join(lines), kb


# ── Success screen ────────────────────────────────────────────────────────────

def build_success(
    record_id:    int,
    patient_name: str,
    image_count:  int,
) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"✅ *تم حفظ ونشر تقرير المتابعة الطبية بنجاح*\n\n"
        f"رقم التقرير: `#{record_id}`\n"
        f"المريض: {patient_name}\n"
        f"الصور المرفوعة: {format_image_count(image_count)}\n\n"
        f"📤 تم إرسال التقرير للمسؤولين والمجموعة الصحية."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إجراء جديد",        callback_data=f"{HCFU}:start")],
        [InlineKeyboardButton("🏥 القائمة الرئيسية",  callback_data=f"{HC}:main")],
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
