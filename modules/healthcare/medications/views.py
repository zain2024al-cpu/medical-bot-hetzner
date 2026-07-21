# modules/healthcare/medications/views.py
# Pure view builders for the medication dispensing flow.
# Official 10-step workflow:
#   1. التاريخ (auto) | 2. المريض | 3. القسم | 4. عدد الأصناف
#   5. الصور | 6. جهة الصرف | 7. ملاحظات | 8. اسم الصحي (fixed) | 9. مراجعة | 10. نشر

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from modules.healthcare.medications.constants import STAFF_LIST  # noqa: F401  (re-exported for callers)
from modules.healthcare.medications.session import MedicationSession
from modules.healthcare.views import format_arabic_date, format_arabic_datetime, format_image_count

HC    = "hc"
HCMED = "hcmed"

_DIVIDER = "━━━━━━━━━━━━━━━━━━━━"
_THIN    = "─────────────────────"


# ── Step 1: اختيار التاريخ ────────────────────────────────────────────────────

def build_date_prompt() -> tuple[str, InlineKeyboardMarkup]:
    """Date selection screen — first visible step of every medications entry."""
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
        [InlineKeyboardButton("✅ اختيار تاريخ اليوم", callback_data=f"{HCMED}:date_today")],
        [InlineKeyboardButton("📆 اختيار من التقويم",  callback_data=f"{HCMED}:date_calendar")],
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
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{HCMED}:start"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{HC}:main"),
    ]])
    return "\n".join(lines), kb


# ── Submenu ───────────────────────────────────────────────────────────────────

def build_medications_menu() -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"{_DIVIDER}\n"
        f"💊  **صرف الأدوية**\n\n"
        "اختر العملية:"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ تسجيل صرف دواء جديد", callback_data=f"{HCMED}:start")],
        [InlineKeyboardButton("⬅️ رجوع",                callback_data=f"{HC}:main")],
    ])
    return text, kb


# ── Step 3b: "أخرى" free-text department prompt ───────────────────────────────

def build_dept_other_prompt(session: MedicationSession) -> tuple[str, InlineKeyboardMarkup]:
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
        InlineKeyboardButton("🔙 رجوع", callback_data=f"{HCMED}:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{HCMED}:cancel"),
    ]])
    return "\n".join(lines), kb


# ── Step 4: عدد الأصناف ───────────────────────────────────────────────────────

def build_count_prompt(
    session: MedicationSession, *, error: bool = False
) -> tuple[str, InlineKeyboardMarkup]:
    """Free-text input for عدد الأصناف (رقم أو وصف). Set error=True to show validation message."""
    depts = "، ".join(session.medical_department_labels) if session.medical_department_labels else "—"
    lines = [
        _DIVIDER,
        "🔢  **عدد الأصناف**",
        "",
        f"المريض: {session.patient_name}",
        f"القسم: {depts}",
        _THIN,
        "",
    ]
    if error:
        lines += ["⚠️ *الرجاء إرسال نص غير فارغ.*", ""]
    lines += [
        "أرسل عدد أصناف الأدوية المصروفة، أو وضّح كل صنف كما تريد.",
        "_(مثال: 3  —  أو: بنادول 5، شاش 3، محلول ملحي 2)_",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 رجوع", callback_data=f"{HCMED}:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{HCMED}:cancel"),
    ]])
    return "\n".join(lines), kb


# ── Step 6: جهة الصرف ────────────────────────────────────────────────────────

def build_dispense_source_prompt(session: MedicationSession) -> tuple[str, InlineKeyboardMarkup]:
    """Two-button selector: الصيدلية or المخزن. Required — no skip."""
    depts = "، ".join(session.medical_department_labels) if session.medical_department_labels else "—"
    lines = [
        _DIVIDER,
        "🏪  **جهة الصرف**",
        "",
        f"المريض: {session.patient_name}",
        f"القسم: {depts}",
        f"عدد الأصناف: {session.item_count}",
        _THIN,
        "",
        "اختر جهة صرف الدواء:",
    ]
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏪 الصيدلية", callback_data=f"{HCMED}:disp_pharmacy"),
            InlineKeyboardButton("📦 المخزن",   callback_data=f"{HCMED}:disp_warehouse"),
        ],
        [
            InlineKeyboardButton("🔙 رجوع", callback_data=f"{HCMED}:back"),
            InlineKeyboardButton("❌ إلغاء", callback_data=f"{HCMED}:cancel"),
        ],
    ])
    return "\n".join(lines), kb


# ── Step 7: ملاحظات ───────────────────────────────────────────────────────────

def build_notes_prompt(session: MedicationSession) -> tuple[str, InlineKeyboardMarkup]:
    depts = "، ".join(session.medical_department_labels) if session.medical_department_labels else "—"
    lines = [
        _DIVIDER,
        "📝  **الملاحظات السريرية**",
        "",
        f"المريض: {session.patient_name}",
        f"القسم: {depts}",
        f"عدد الأصناف: {session.item_count}",
        f"جهة الصرف: {session.dispense_source or '—'}",
        f"الصور: {format_image_count(session.image_count)}",
        _THIN,
        "",
        "أضف ملاحظات (جرعة، تعليمات خاصة…)، أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏭️ تخطي",  callback_data=f"{HCMED}:skip_notes"),
            InlineKeyboardButton("🔙 رجوع",   callback_data=f"{HCMED}:back"),
            InlineKeyboardButton("❌ إلغاء",  callback_data=f"{HCMED}:cancel"),
        ],
    ])
    return "\n".join(lines), kb


# ── Step 7: اسم الصحي — fixed single-select, REQUIRED ────────────────────────

def build_specialist_prompt(session: MedicationSession) -> tuple[str, InlineKeyboardMarkup]:
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
        "اختر اسم الصحي المسؤول عن الصرف:",
    ]
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("د. فضل",    callback_data=f"{HCMED}:sp_fadl"),
            InlineKeyboardButton("د. سرور",   callback_data=f"{HCMED}:sp_sarour"),
        ],
        [
            InlineKeyboardButton("د. زكريا",  callback_data=f"{HCMED}:sp_zakariya"),
            InlineKeyboardButton("د. مبروك",  callback_data=f"{HCMED}:sp_mabrook"),
        ],
        [
            InlineKeyboardButton("🔙 رجوع", callback_data=f"{HCMED}:back"),
            InlineKeyboardButton("❌ إلغاء", callback_data=f"{HCMED}:cancel"),
        ],
    ])
    return "\n".join(lines), kb


# ── Step 8: مراجعة نهائية ─────────────────────────────────────────────────────

_NONE = "➖ غير مضاف"


def build_review(session: MedicationSession) -> tuple[str, InlineKeyboardMarkup]:
    """
    Official review layout:
    التاريخ · المريض · الأقسام · عدد الأصناف · الصور · الملاحظات · اسم الصحي
    """
    date_str  = format_arabic_date(session.created_at)
    dept_text = "، ".join(session.medical_department_labels) or "—"
    imgs      = format_image_count(session.image_count)
    notes     = session.notes or "لا توجد ملاحظات"

    lines = [
        "💊 *مراجعة صرف الدواء*",
        "",
        f"📅 {date_str}",
        f"👤 {session.patient_name}  •  🏥 {dept_text}",
        f"🔢 الأصناف: {session.item_count or '—'}  •  🏪 {session.dispense_source or '—'}",
        f"📎 {imgs}",
        f"📝 {notes}",
        f"👨‍⚕️ {session.specialist_name or '—'}",
        "",
        "هل تريد نشر هذا التقرير؟",
    ]

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 نشر التقرير",       callback_data=f"{HCMED}:confirm"),
            InlineKeyboardButton("❌ إلغاء",              callback_data=f"{HCMED}:cancel"),
        ],
        [InlineKeyboardButton("✏️ القسم الطبي",          callback_data=f"{HCMED}:edit_dept"),
         InlineKeyboardButton("✏️ عدد الأصناف",          callback_data=f"{HCMED}:edit_count")],
        [InlineKeyboardButton("✏️ الصور",                 callback_data=f"{HCMED}:edit_images"),
         InlineKeyboardButton("✏️ جهة الصرف",            callback_data=f"{HCMED}:edit_source")],
        [InlineKeyboardButton("✏️ الملاحظات",             callback_data=f"{HCMED}:edit_notes"),
         InlineKeyboardButton("✏️ المختص الصحي",         callback_data=f"{HCMED}:edit_specialist")],
    ])
    return "\n".join(lines), kb


# ── Success screen ────────────────────────────────────────────────────────────

def build_success(
    record_id: int, patient_name: str, image_count: int
) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"✅ *تم حفظ ونشر تقرير الدواء بنجاح*\n\n"
        f"رقم التقرير: `#{record_id}`\n"
        f"المريض: {patient_name}\n"
        f"الصور المرفوعة: {format_image_count(image_count)}\n\n"
        f"📤 تم إرسال التقرير للمسؤولين والمجموعة الصحية."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ صرف دواء جديد",    callback_data=f"{HCMED}:start")],
        [InlineKeyboardButton("🏥 القائمة الرئيسية", callback_data=f"{HC}:main")],
    ])
    return text, kb


# ── Cancellation screen ───────────────────────────────────────────────────────

def build_cancelled() -> tuple[str, InlineKeyboardMarkup]:
    text = "❌ *تم إلغاء العملية.*\n\nيمكنك البدء من جديد في أي وقت."
    kb   = InlineKeyboardMarkup([[InlineKeyboardButton("🏥 القائمة الرئيسية", callback_data=f"{HC}:main")]])
    return text, kb


# ── Error screen ──────────────────────────────────────────────────────────────

def build_error(message: str = "") -> tuple[str, InlineKeyboardMarkup]:
    text = f"❌ *خطأ*\n\n{message or 'حدث خطأ غير متوقع.'}"
    kb   = InlineKeyboardMarkup([[InlineKeyboardButton("🏥 القائمة الرئيسية", callback_data=f"{HC}:main")]])
    return text, kb
