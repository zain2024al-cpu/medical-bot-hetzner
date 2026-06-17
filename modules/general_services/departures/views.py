# modules/general_services/departures/views.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from modules.general_services.departures.session import DepartureSession
from modules.general_services.views import (
    format_arabic_datetime, format_arabic_date, format_image_count,
    _DIVIDER, _THIN, _NONE,
)
from modules.general_services.constants import HOSPITAL_MAP, STAFF_MAP

GS  = "gs"
GSD = "gsd"


# ── Menu ──────────────────────────────────────────────────────────────────────

def build_departures_menu() -> tuple[str, InlineKeyboardMarkup]:
    text = f"{_DIVIDER}\n🛫  **المغادرة**\n\nاختر الإجراء:"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ تسجيل مغادرة جديدة", callback_data=f"{GSD}:start")],
        [InlineKeyboardButton("⬅️ رجوع",               callback_data=f"{GS}:main")],
    ])
    return text, kb


# ── Step 1: التاريخ ───────────────────────────────────────────────────────────

def build_date_prompt() -> tuple[str, InlineKeyboardMarkup]:
    from datetime import datetime
    today_str = format_arabic_date(datetime.utcnow())
    lines = [
        _DIVIDER,
        "📅  **اختر تاريخ المغادرة**",
        "",
        f"التاريخ الحالي: *{today_str}*",
        _THIN,
        "",
        "اختر طريقة تحديد التاريخ:",
    ]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ اليوم",             callback_data=f"{GSD}:date_today")],
        [InlineKeyboardButton("📆 اختيار من التقويم", callback_data=f"{GSD}:date_calendar")],
        [InlineKeyboardButton("⬅️ رجوع",              callback_data=f"{GS}:departures")],
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
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSD}:start"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:departures"),
    ]])
    return "\n".join(lines), kb


# ── Step 2: اختيار الواصلين ───────────────────────────────────────────────────

def build_no_arrivals_prompt() -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER,
        "🛬  **لا يوجد واصلون نشطون**",
        "",
        "لا توجد دفعات وصول بحالة *نشطة* في الأرشيف.",
        _THIN,
        "",
        "يجب تسجيل وصول أولاً قبل تسجيل المغادرة.",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSD}:start"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:departures"),
    ]])
    return "\n".join(lines), kb


# ── Step 3: الصور ─────────────────────────────────────────────────────────────

def build_images_prompt(session: DepartureSession) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER,
        "📷  **صور المغادرة**",
        "",
        f"المغادرون: {session.patients_text or _NONE}",
        _THIN,
        "",
        "أرسل صور المغادرة (اختياري)، ثم اضغط **✅ انتهيت**.",
        "أو اضغط **⏭️ تخطي** إذا لم تكن هناك صور.",
    ]
    count = session.image_count
    if count:
        lines.insert(-1, f"📎 تم استلام {format_image_count(count)} حتى الآن.")
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ انتهيت من الصور", callback_data=f"{GSD}:images_done"),
            InlineKeyboardButton("⏭️ تخطي",             callback_data=f"{GSD}:skip_images"),
        ],
        [
            InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSD}:back_to_patients"),
            InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:departures"),
        ],
    ])
    return "\n".join(lines), kb


# ── Step 4: المستشفى ──────────────────────────────────────────────────────────

def build_hospital_prompt() -> tuple[str, InlineKeyboardMarkup]:
    lines = [_DIVIDER, "🏥  **اختر الجهة الموصلة**", "", "اختر الجهة الموصلة:"]
    rows = [
        [InlineKeyboardButton(label, callback_data=f"{GSD}:hospital_{hid}")]
        for hid, label in HOSPITAL_MAP.items()
    ]
    rows.append([
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSD}:back_to_images"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:departures"),
    ])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


# ── Step 5: الملاحظات ─────────────────────────────────────────────────────────

def build_notes_prompt(session: DepartureSession) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER,
        "📝  **ملاحظات**",
        "",
        f"الجهة الموصلة: {session.hospital_label}",
        _THIN,
        "",
        "أرسل ملاحظاتك، أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭️ تخطي", callback_data=f"{GSD}:skip_notes"),
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSD}:back_to_hospital"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:departures"),
    ]])
    return "\n".join(lines), kb


# ── Step 6: المختص ────────────────────────────────────────────────────────────

def build_specialist_prompt(session: DepartureSession) -> tuple[str, InlineKeyboardMarkup]:
    lines = [_DIVIDER, "👨‍⚕️  **اختر المختص المسؤول**", "", "اختر المختص:"]
    rows = [
        [InlineKeyboardButton(label, callback_data=f"{GSD}:specialist_{sid}")]
        for sid, label in STAFF_MAP.items()
    ]
    rows.append([
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSD}:back_to_notes"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:departures"),
    ])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


# ── Review ────────────────────────────────────────────────────────────────────

def build_review(session: DepartureSession) -> tuple[str, InlineKeyboardMarkup]:
    date_str = format_arabic_datetime(session.created_at)
    imgs     = format_image_count(session.image_count)
    notes    = session.notes or "لا توجد ملاحظات"
    lines = [
        "🛫 *مراجعة تقرير المغادرة*",
        _DIVIDER,
        f"📅 *التاريخ:*  {date_str}",
        f"👥 *المغادرون:*  {session.patients_text or _NONE}",
        f"🏥 *الجهة الموصلة:*  {session.hospital_label or _NONE}",
        f"👨‍⚕️ *المسؤول:*  {session.specialist_label or _NONE}",
        f"📎 *الوثائق:*  {imgs}",
        _THIN,
        f"📝 *الملاحظات:*  {notes}",
        "",
        "هل تريد نشر هذا التقرير؟",
    ]
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 نشر التقرير", callback_data=f"{GSD}:confirm"),
            InlineKeyboardButton("❌ إلغاء",        callback_data=f"{GSD}:cancel"),
        ],
        [
            InlineKeyboardButton("✏️ المغادرون",  callback_data=f"{GSD}:edit_patients"),
            InlineKeyboardButton("✏️ الصور",       callback_data=f"{GSD}:edit_images"),
        ],
        [
            InlineKeyboardButton("✏️ الجهة الموصلة", callback_data=f"{GSD}:edit_hospital"),
            InlineKeyboardButton("✏️ الملاحظات",  callback_data=f"{GSD}:edit_notes"),
        ],
        [
            InlineKeyboardButton("✏️ المختص",     callback_data=f"{GSD}:edit_specialist"),
        ],
    ])
    return "\n".join(lines), kb


# ── Terminal screens ──────────────────────────────────────────────────────────

def build_success(record_id: int, hospital_label: str) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"✅ *تم حفظ ونشر تقرير المغادرة بنجاح*\n\n"
        f"رقم التقرير: `#{record_id}`\n"
        f"الجهة الموصلة: {hospital_label}\n\n"
        f"📤 تم إرسال التقرير للمسؤولين."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ مغادرة جديدة",    callback_data=f"{GSD}:start")],
        [InlineKeyboardButton("🔧 الخدمات العامة",  callback_data=f"{GS}:main")],
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
