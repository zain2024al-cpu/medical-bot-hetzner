# modules/healthcare/supplies/views.py
# Pure view builders for the medical supplies dispensing flow.
# Workflow (mirrors medications):
#   1. التاريخ | 2. المريض | 3. القسم | 4. عدد الأصناف
#   5. الصور | 6. جهة الصرف | 7. ملاحظات | 8. اسم الصحي | 9. مراجعة | 10. نشر

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from modules.healthcare.supplies.constants import STAFF_LIST  # noqa: F401
from modules.healthcare.supplies.session import SuppliesSession
from modules.healthcare.views import format_arabic_datetime, format_image_count

HC    = "hc"
HCSUP = "hcsup"

_DIVIDER = "━━━━━━━━━━━━━━━━━━━━"
_THIN    = "─────────────────────"


# ── Step 1: اختيار التاريخ ────────────────────────────────────────────────────

def build_date_prompt() -> tuple[str, InlineKeyboardMarkup]:
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
        [InlineKeyboardButton("✅ اختيار تاريخ اليوم", callback_data=f"{HCSUP}:date_today")],
        [InlineKeyboardButton("📆 اختيار من التقويم",  callback_data=f"{HCSUP}:date_calendar")],
        [InlineKeyboardButton("⬅️ رجوع",               callback_data=f"{HC}:supplies")],
    ])
    return "\n".join(lines), kb


def build_date_calendar_prompt(*, error: bool = False) -> tuple[str, InlineKeyboardMarkup]:
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
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{HCSUP}:start"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{HC}:supplies"),
    ]])
    return "\n".join(lines), kb


# ── Submenu ───────────────────────────────────────────────────────────────────

def build_supplies_menu() -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"{_DIVIDER}\n"
        f"🏥  **المستلزمات الطبية**\n\n"
        "اختر العملية:"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ تسجيل صرف مستلزمات جديد", callback_data=f"{HCSUP}:start")],
        [InlineKeyboardButton("⬅️ رجوع",                     callback_data=f"{HC}:main")],
    ])
    return text, kb


# ── Step 3b: "أخرى" free-text department prompt ───────────────────────────────

def build_dept_other_prompt(session: SuppliesSession) -> tuple[str, InlineKeyboardMarkup]:
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
        InlineKeyboardButton("🔙 رجوع", callback_data=f"{HCSUP}:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{HCSUP}:cancel"),
    ]])
    return "\n".join(lines), kb


# ── Step 4: عدد الأصناف ───────────────────────────────────────────────────────

def build_count_prompt(
    session: SuppliesSession, *, error: bool = False
) -> tuple[str, InlineKeyboardMarkup]:
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
        lines += ["⚠️ *الرجاء إدخال رقم صحيح وموجب.*  (مثال: 3)", ""]
    lines += ["أرسل عدد أصناف المستلزمات المصروفة (رقم موجب، مثال: 3)."]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 رجوع", callback_data=f"{HCSUP}:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{HCSUP}:cancel"),
    ]])
    return "\n".join(lines), kb


# ── Step 6: جهة الصرف ────────────────────────────────────────────────────────

def build_dispense_source_prompt(session: SuppliesSession) -> tuple[str, InlineKeyboardMarkup]:
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
        "اختر جهة صرف المستلزمات:",
    ]
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏪 الصيدلية", callback_data=f"{HCSUP}:disp_pharmacy"),
            InlineKeyboardButton("📦 المخزن",   callback_data=f"{HCSUP}:disp_warehouse"),
        ],
        [
            InlineKeyboardButton("🔙 رجوع", callback_data=f"{HCSUP}:back"),
            InlineKeyboardButton("❌ إلغاء", callback_data=f"{HCSUP}:cancel"),
        ],
    ])
    return "\n".join(lines), kb


# ── Step 7: ملاحظات ───────────────────────────────────────────────────────────

def build_notes_prompt(session: SuppliesSession) -> tuple[str, InlineKeyboardMarkup]:
    depts = "، ".join(session.medical_department_labels) if session.medical_department_labels else "—"
    lines = [
        _DIVIDER,
        "📝  **الملاحظات**",
        "",
        f"المريض: {session.patient_name}",
        f"القسم: {depts}",
        f"عدد الأصناف: {session.item_count}",
        f"جهة الصرف: {session.dispense_source or '—'}",
        f"الصور: {format_image_count(session.image_count)}",
        _THIN,
        "",
        "أضف ملاحظات (كميات، تعليمات خاصة…)، أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏭️ تخطي",  callback_data=f"{HCSUP}:skip_notes"),
            InlineKeyboardButton("🔙 رجوع",   callback_data=f"{HCSUP}:back"),
            InlineKeyboardButton("❌ إلغاء",  callback_data=f"{HCSUP}:cancel"),
        ],
    ])
    return "\n".join(lines), kb


# ── Step 8: اسم الصحي ────────────────────────────────────────────────────────

def build_specialist_prompt(session: SuppliesSession) -> tuple[str, InlineKeyboardMarkup]:
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
            InlineKeyboardButton("د. فضل",    callback_data=f"{HCSUP}:sp_fadl"),
            InlineKeyboardButton("د. سرور",   callback_data=f"{HCSUP}:sp_sarour"),
            InlineKeyboardButton("د. زكريا",  callback_data=f"{HCSUP}:sp_zakariya"),
        ],
        [
            InlineKeyboardButton("🔙 رجوع", callback_data=f"{HCSUP}:back"),
            InlineKeyboardButton("❌ إلغاء", callback_data=f"{HCSUP}:cancel"),
        ],
    ])
    return "\n".join(lines), kb


# ── Step 9: مراجعة نهائية ─────────────────────────────────────────────────────

_NONE = "➖ غير مضاف"


def build_review(session: SuppliesSession) -> tuple[str, InlineKeyboardMarkup]:
    date_str  = format_arabic_datetime(session.created_at)
    dept_text = "، ".join(session.medical_department_labels) or _NONE

    lines = [
        "🏥 *مراجعة صرف المستلزمات الطبية*",
        "",
        f"📅 *التاريخ:*  {date_str}",
        f"👤 *المريض:*  {session.patient_name}",
        "",
        f"🏥 *القسم الطبي:*  {dept_text}",
        "",
        f"🔢 *عدد الأصناف:*  {session.item_count or _NONE}",
        f"🏪 *جهة الصرف:*   {session.dispense_source or _NONE}",
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
            InlineKeyboardButton("📢 نشر التقرير",       callback_data=f"{HCSUP}:confirm"),
            InlineKeyboardButton("❌ إلغاء",              callback_data=f"{HCSUP}:cancel"),
        ],
        [InlineKeyboardButton("✏️ القسم الطبي",          callback_data=f"{HCSUP}:edit_dept"),
         InlineKeyboardButton("✏️ عدد الأصناف",          callback_data=f"{HCSUP}:edit_count")],
        [InlineKeyboardButton("✏️ الصور",                 callback_data=f"{HCSUP}:edit_images"),
         InlineKeyboardButton("✏️ جهة الصرف",            callback_data=f"{HCSUP}:edit_source")],
        [InlineKeyboardButton("✏️ الملاحظات",             callback_data=f"{HCSUP}:edit_notes"),
         InlineKeyboardButton("✏️ المختص الصحي",         callback_data=f"{HCSUP}:edit_specialist")],
    ])
    return "\n".join(lines), kb


# ── Success screen ────────────────────────────────────────────────────────────

def build_success(
    record_id: int, patient_name: str, image_count: int
) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"✅ *تم حفظ ونشر تقرير المستلزمات الطبية بنجاح*\n\n"
        f"رقم التقرير: `#{record_id}`\n"
        f"المريض: {patient_name}\n"
        f"الصور المرفوعة: {format_image_count(image_count)}\n\n"
        f"📤 تم إرسال التقرير للمسؤولين والمجموعة الصحية."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ صرف مستلزمات جديد",  callback_data=f"{HCSUP}:start")],
        [InlineKeyboardButton("🏥 القائمة الرئيسية",    callback_data=f"{HC}:main")],
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
