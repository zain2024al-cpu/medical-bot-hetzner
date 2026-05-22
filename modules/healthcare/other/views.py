# modules/healthcare/other/views.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from modules.healthcare.other.session import OtherHealthcareSession
from modules.healthcare.views import format_arabic_datetime, format_image_count

HC    = "hc"
HCOTH = "hcoth"

_DIVIDER = "━━━━━━━━━━━━━━━━━━━━"
_THIN    = "─────────────────────"


# ── Step 1: اختيار التاريخ ────────────────────────────────────────────────────

def build_date_prompt() -> tuple[str, InlineKeyboardMarkup]:
    """Date selection screen — first visible step of every other-hc entry."""
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
        [InlineKeyboardButton("✅ اختيار تاريخ اليوم", callback_data=f"{HCOTH}:date_today")],
        [InlineKeyboardButton("📆 اختيار من التقويم",  callback_data=f"{HCOTH}:date_calendar")],
        [InlineKeyboardButton("⬅️ رجوع",               callback_data=f"{HC}:other")],
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
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{HCOTH}:start"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{HC}:other"),
    ]])
    return "\n".join(lines), kb


def build_other_menu() -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"{_DIVIDER}\n"
        f"📝  **الإجراءات الصحية الأخرى**\n\n"
        "اختر الإجراء:"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ تسجيل إجراء صحي جديد", callback_data=f"{HCOTH}:start")],
        [InlineKeyboardButton("⬅️ رجوع",                  callback_data=f"{HC}:main")],
    ])
    return text, kb


def build_notes_prompt(session: OtherHealthcareSession) -> tuple[str, InlineKeyboardMarkup]:
    ops = ", ".join(session.operation_labels) or "—"
    lines = [
        _DIVIDER,
        "📝  **الملاحظات السريرية**",
        "",
        f"المريض: {session.patient_name}",
        f"الإجراءات: {ops}",
        f"الصور: {format_image_count(session.image_count)}",
        _THIN,
        "",
        "أرسل ملاحظاتك، أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏭️ تخطي",  callback_data=f"{HCOTH}:skip_notes"),
            InlineKeyboardButton("🔙 رجوع",   callback_data=f"{HCOTH}:back"),
            InlineKeyboardButton("❌ إلغاء",  callback_data=f"{HCOTH}:cancel"),
        ],
    ])
    return "\n".join(lines), kb


def build_specialist_prompt(session: OtherHealthcareSession) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER,
        "👨‍⚕️  **اسم المختص الصحي**",
        "",
        f"المريض: {session.patient_name}",
        _THIN,
        "",
        "أرسل اسم المختص الصحي، أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏭️ تخطي",         callback_data=f"{HCOTH}:skip_specialist"),
            InlineKeyboardButton("🔙 رجوع",          callback_data=f"{HCOTH}:back"),
            InlineKeyboardButton("❌ إلغاء",         callback_data=f"{HCOTH}:cancel"),
        ],
        [InlineKeyboardButton("↩️ تعديل الملاحظات", callback_data=f"{HCOTH}:edit_notes")],
    ])
    return "\n".join(lines), kb


def build_review(session: OtherHealthcareSession) -> tuple[str, InlineKeyboardMarkup]:
    date_str  = format_arabic_datetime(session.created_at)
    ops_list  = "\n".join(f"  • {lbl}" for lbl in session.operation_labels) or "  —"

    lines = [
        "📝 *مراجعة الإجراء الصحي*",
        "",
        f"📅 *التاريخ:*  {date_str}",
        f"👤 *المريض:*  {session.patient_name}",
        "",
        f"📝 *الإجراءات:*",
        ops_list,
    ]
    if session.image_count:
        lines += ["", f"📎 *الصور:*  {format_image_count(session.image_count)}"]
    if session.notes:
        lines += ["", f"📝 *الملاحظات:*", session.notes]
    if session.specialist_name:
        lines += ["", f"👨‍⚕️ *المختص الصحي:*  {session.specialist_name}"]
    lines += ["", "هل تريد نشر هذا التقرير؟"]

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 نشر التقرير",     callback_data=f"{HCOTH}:confirm"),
            InlineKeyboardButton("❌ إلغاء",            callback_data=f"{HCOTH}:cancel"),
        ],
        [
            InlineKeyboardButton("✏️ تعديل الملاحظات", callback_data=f"{HCOTH}:edit_notes"),
            InlineKeyboardButton("👨‍⚕️ تعديل المختص",  callback_data=f"{HCOTH}:edit_specialist"),
        ],
    ])
    return "\n".join(lines), kb


def build_success(record_id: int, patient_name: str, image_count: int) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"✅ *تم حفظ ونشر الإجراء الصحي بنجاح*\n\n"
        f"رقم التقرير: `#{record_id}`\n"
        f"المريض: {patient_name}\n"
        f"الصور المرفوعة: {image_count}\n\n"
        f"📤 تم إرسال التقرير للمسؤولين والمجموعة الصحية."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إجراء جديد",        callback_data=f"{HCOTH}:start")],
        [InlineKeyboardButton("🏥 القائمة الرئيسية",  callback_data=f"{HC}:main")],
    ])
    return text, kb


def build_cancelled() -> tuple[str, InlineKeyboardMarkup]:
    text = "❌ *تم إلغاء العملية.*\n\nيمكنك البدء من جديد في أي وقت."
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏥 القائمة الرئيسية", callback_data=f"{HC}:main")]])
    return text, kb


def build_error(message: str = "") -> tuple[str, InlineKeyboardMarkup]:
    text = f"❌ *خطأ*\n\n{message or 'حدث خطأ غير متوقع.'}"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏥 القائمة الرئيسية", callback_data=f"{HC}:main")]])
    return text, kb
