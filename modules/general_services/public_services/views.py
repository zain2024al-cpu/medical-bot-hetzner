# modules/general_services/public_services/views.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from modules.general_services.public_services.session import PublicServiceSession
from modules.general_services.views import (
    format_arabic_datetime, format_arabic_date, format_image_count,
    _DIVIDER, _THIN, _NONE,
)
from modules.general_services.constants import STAFF_MAP

GS  = "gs"
GSP = "gsp"


# ── Menu ──────────────────────────────────────────────────────────────────────

def build_public_services_menu() -> tuple[str, InlineKeyboardMarkup]:
    text = f"{_DIVIDER}\n🧾  **الخدمات العامة**\n\nاختر الإجراء:"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ تسجيل خدمة جديدة", callback_data=f"{GSP}:start")],
        [InlineKeyboardButton("⬅️ رجوع",              callback_data=f"{GS}:main")],
    ])
    return text, kb


# ── Step 1: التاريخ ───────────────────────────────────────────────────────────

def build_date_prompt() -> tuple[str, InlineKeyboardMarkup]:
    from datetime import datetime
    today_str = format_arabic_date(datetime.utcnow())
    lines = [
        _DIVIDER,
        "📅  **اختر تاريخ الخدمة**",
        "",
        f"التاريخ الحالي: *{today_str}*",
        _THIN,
        "",
        "اختر طريقة تحديد التاريخ:",
    ]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ اليوم",             callback_data=f"{GSP}:date_today")],
        [InlineKeyboardButton("📆 اختيار من التقويم", callback_data=f"{GSP}:date_calendar")],
        [InlineKeyboardButton("⬅️ رجوع",              callback_data=f"{GS}:public_services")],
    ])
    return "\n".join(lines), kb


def build_date_calendar_prompt(*, error: bool = False) -> tuple[str, InlineKeyboardMarkup]:
    lines = [_DIVIDER, "📆  **إدخال التاريخ يدوياً**", ""]
    if error:
        lines += ["⚠️ *صيغة التاريخ غير صحيحة.* يرجى المحاولة مجدداً.", ""]
    lines += [
        "أرسل التاريخ بإحدى الصيغ التالية:",
        "*يوم/شهر/سنة*  (مثال: 22/05/2026)",
        "أو:  22-05-2026",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSP}:start"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:public_services"),
    ]])
    return "\n".join(lines), kb


# ── Step 2: المريض (patient_selector) ────────────────────────────────────────

def build_patient_prompt() -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER,
        "👤  **اختر المريض**",
        "",
        "ابحث عن المريض أو اختره من القائمة:",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSP}:start"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:public_services"),
    ]])
    return "\n".join(lines), kb


# ── Step 3: نوع الخدمة (free text) ───────────────────────────────────────────

def build_service_type_prompt(session: PublicServiceSession) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER,
        "🧾  **نوع الخدمة**",
        "",
        f"المريض: {session.patient_name or _NONE}",
        _THIN,
        "",
        "✏️ اكتب نوع الخدمة:",
        "",
        "_أمثلة: حجز فندق، استقبال مطار، استخراج شريحة، نقل مريض، مراجعة سفارة_",
    ]
    current = session.service_type_labels[0] if session.service_type_labels else ""
    if current:
        lines.append(f"\nالخدمة الحالية: *{current}*")
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSP}:back_to_patient"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:public_services"),
    ]])
    return "\n".join(lines), kb


# ── Step 4: عدد الأصناف / البنود ─────────────────────────────────────────────

def build_count_prompt(session: PublicServiceSession) -> tuple[str, InlineKeyboardMarkup]:
    svc = "، ".join(session.service_type_labels) or _NONE
    lines = [
        _DIVIDER,
        "🔢  **عدد البنود**",
        "",
        f"المريض: {session.patient_name or _NONE}",
        f"الخدمات: {svc}",
        _THIN,
        "",
        "أرسل عدد البنود / الأصناف (رقم):",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSP}:back_to_service_type"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:public_services"),
    ]])
    return "\n".join(lines), kb


# ── Step 5: الصور ─────────────────────────────────────────────────────────────

def build_images_prompt(session: PublicServiceSession) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER,
        "📷  **صور الخدمة**",
        "",
        f"المريض: {session.patient_name or _NONE}",
        _THIN,
        "",
        "أرسل صور وثائق / إيصالات الخدمة، ثم اضغط **✅ انتهيت**.",
    ]
    count = session.image_count
    if count:
        lines.insert(-1, f"📎 تم استلام {format_image_count(count)} حتى الآن.")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ انتهيت من الصور", callback_data=f"{GSP}:images_done")],
        [
            InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSP}:back_to_count"),
            InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:public_services"),
        ],
    ])
    return "\n".join(lines), kb


# ── Step 6: الملاحظات ─────────────────────────────────────────────────────────

def build_notes_prompt(session: PublicServiceSession) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER,
        "📝  **ملاحظات**",
        "",
        f"المريض: {session.patient_name or _NONE}",
        _THIN,
        "",
        "أرسل ملاحظاتك، أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭️ تخطي", callback_data=f"{GSP}:skip_notes"),
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSP}:back_to_images"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:public_services"),
    ]])
    return "\n".join(lines), kb


# ── Step 7: المختص ────────────────────────────────────────────────────────────

def build_specialist_prompt(session: PublicServiceSession) -> tuple[str, InlineKeyboardMarkup]:
    lines = [_DIVIDER, "👨‍⚕️  **اختر المختص المسؤول**", "", "اختر المختص:"]
    rows = [
        [InlineKeyboardButton(label, callback_data=f"{GSP}:specialist_{sid}")]
        for sid, label in STAFF_MAP.items()
    ]
    rows.append([
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSP}:back_to_notes"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:public_services"),
    ])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


# ── Review ────────────────────────────────────────────────────────────────────

def build_review(session: PublicServiceSession) -> tuple[str, InlineKeyboardMarkup]:
    date_str  = format_arabic_datetime(session.created_at)
    svc       = session.service_type_labels[0] if session.service_type_labels else _NONE
    imgs      = format_image_count(session.image_count)
    notes     = session.notes or "لا توجد ملاحظات"
    lines = [
        "🧾 *مراجعة الخدمة العامة*",
        _DIVIDER,
        f"📅 *التاريخ:*  {date_str}",
        f"👤 *المريض:*  {session.patient_name or _NONE}",
        f"🧾 *نوع الخدمة:*  {svc}",
        f"🔢 *عدد البنود:*  {session.item_count or _NONE}",
        f"📎 *الوثائق:*  {imgs}",
        f"👨‍⚕️ *المختص:*  {session.specialist_label or _NONE}",
        _THIN,
        f"📝 *الملاحظات:*  {notes}",
        "",
        "هل تريد نشر هذا التقرير؟",
    ]
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 نشر التقرير", callback_data=f"{GSP}:confirm"),
            InlineKeyboardButton("❌ إلغاء",        callback_data=f"{GSP}:cancel"),
        ],
        [
            InlineKeyboardButton("✏️ المريض",     callback_data=f"{GSP}:edit_patient"),
            InlineKeyboardButton("✏️ الخدمات",    callback_data=f"{GSP}:edit_service_type"),
        ],
        [
            InlineKeyboardButton("✏️ البنود",     callback_data=f"{GSP}:edit_count"),
            InlineKeyboardButton("✏️ الصور",      callback_data=f"{GSP}:edit_images"),
        ],
        [
            InlineKeyboardButton("✏️ الملاحظات", callback_data=f"{GSP}:edit_notes"),
            InlineKeyboardButton("✏️ المختص",    callback_data=f"{GSP}:edit_specialist"),
        ],
    ])
    return "\n".join(lines), kb


# ── Terminal screens ──────────────────────────────────────────────────────────

def build_success(record_id: int, patient_name: str) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"✅ *تم حفظ ونشر تقرير الخدمة العامة بنجاح*\n\n"
        f"رقم التقرير: `#{record_id}`\n"
        f"المريض: {patient_name}\n\n"
        f"📤 تم إرسال التقرير للمسؤولين."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ خدمة جديدة",     callback_data=f"{GSP}:start")],
        [InlineKeyboardButton("🔧 الخدمات العامة", callback_data=f"{GS}:main")],
    ])
    return text, kb


def build_cancelled() -> tuple[str, InlineKeyboardMarkup]:
    text = "❌ *تم إلغاء العملية.*\n\nيمكنك البدء من جديد في أي وقت."
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔧 الخدمات العامة", callback_data=f"{GS}:main")]])
    return text, kb


def build_error(message: str = "") -> tuple[str, InlineKeyboardMarkup]:
    text = f"❌ *خطأ*\n\n{message or 'حدث خطأ غير متوقع.'}"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔧 الخدمات العامة", callback_data=f"{GS}:main")]])
    return text, kb
