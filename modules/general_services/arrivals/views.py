# modules/general_services/arrivals/views.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from modules.general_services.arrivals.session import ArrivalSession
from modules.general_services.views import (
    format_arabic_datetime, format_arabic_date,
    _DIVIDER, _THIN, _NONE,
)
from modules.general_services.constants import HOSPITAL_MAP, STAFF_MAP

GS  = "gs"
GSA = "gsa"


# ── Menu ──────────────────────────────────────────────────────────────────────

def build_arrivals_menu() -> tuple[str, InlineKeyboardMarkup]:
    text = f"{_DIVIDER}\n🛬  **الوصول**\n\nاختر الإجراء:"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ تسجيل دفعة وصول جديدة", callback_data=f"{GSA}:start")],
        [InlineKeyboardButton("⬅️ رجوع",                  callback_data=f"{GS}:main")],
    ])
    return text, kb


# ── Step 1: التاريخ ───────────────────────────────────────────────────────────

def build_date_prompt() -> tuple[str, InlineKeyboardMarkup]:
    from datetime import datetime
    today_str = format_arabic_date(datetime.utcnow())
    lines = [
        _DIVIDER,
        "📅  **اختر تاريخ الوصول**",
        "",
        f"التاريخ الحالي: *{today_str}*",
        _THIN,
        "",
        "اختر طريقة تحديد التاريخ:",
    ]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ اليوم",             callback_data=f"{GSA}:date_today")],
        [InlineKeyboardButton("📆 اختيار من التقويم", callback_data=f"{GSA}:date_calendar")],
        [InlineKeyboardButton("⬅️ رجوع",              callback_data=f"{GS}:arrivals")],
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
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:start"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
    ]])
    return "\n".join(lines), kb


# ── Step 2: المستشفى ──────────────────────────────────────────────────────────

def build_hospital_prompt() -> tuple[str, InlineKeyboardMarkup]:
    lines = [_DIVIDER, "🏥  **اختر الجهة الموصلة**", "", "اختر الجهة الموصلة:"]
    rows = [
        [InlineKeyboardButton(label, callback_data=f"{GSA}:hospital_{hid}")]
        for hid, label in HOSPITAL_MAP.items()
    ]
    rows.append([
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:start"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
    ])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


# ── Step 3: المختص ────────────────────────────────────────────────────────────

def build_specialist_prompt() -> tuple[str, InlineKeyboardMarkup]:
    lines = [_DIVIDER, "👨‍⚕️  **اختر المختص المسؤول**", "", "اختر المختص:"]
    rows = [
        [InlineKeyboardButton(label, callback_data=f"{GSA}:specialist_{sid}")]
        for sid, label in STAFF_MAP.items()
    ]
    rows.append([
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_to_hospital"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
    ])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


# ── Step 4: عدد المرضى ────────────────────────────────────────────────────────

def build_patient_count_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER,
        "👥  **عدد المرضى في الدفعة**",
        "",
        f"الجهة الموصلة: {session.hospital_label}",
        f"المختص: {session.specialist_label}",
        _THIN,
        "",
        "اختر عدد المرضى في الدفعة:",
    ]
    # Numbers 1–20 in rows of 5
    rows = [
        [InlineKeyboardButton(str(n), callback_data=f"{GSA}:count_{n}") for n in range(1,  6)],
        [InlineKeyboardButton(str(n), callback_data=f"{GSA}:count_{n}") for n in range(6,  11)],
        [InlineKeyboardButton(str(n), callback_data=f"{GSA}:count_{n}") for n in range(11, 16)],
        [InlineKeyboardButton(str(n), callback_data=f"{GSA}:count_{n}") for n in range(16, 21)],
        [
            InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_to_specialist"),
            InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
        ],
    ]
    return "\n".join(lines), InlineKeyboardMarkup(rows)


# ── Patient loop steps ─────────────────────────────────────────────────────────

def build_p_name_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx   = session.patient_index + 1
    total = session.patient_count
    lines = [
        _DIVIDER,
        f"👤  **المريض {idx} من {total}**",
        "",
        f"الجهة الموصلة: {session.hospital_label}",
        _THIN,
        "",
        f"✏️ اكتب اسم المريض {idx}:",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
    ]])
    return "\n".join(lines), kb


def build_p_visa_expiry_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx  = session.patient_index + 1
    name = session.current_patient.get("name", "—")
    lines = [
        _DIVIDER,
        f"📋  **المريض {idx} — تاريخ انتهاء التأشيرة**",
        "",
        f"المريض: {name}",
        _THIN,
        "",
        "اختر تاريخ انتهاء التأشيرة:",
    ]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📆 اختيار من التقويم", callback_data=f"{GSA}:visa_expiry_cal")],
        [
            InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_p_name"),
            InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
        ],
    ])
    return "\n".join(lines), kb


def build_p_has_companion_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx  = session.patient_index + 1
    name = session.current_patient.get("name", "—")
    lines = [
        _DIVIDER,
        f"🤝  **المريض {idx} — هل يوجد مرافق؟**",
        "",
        f"المريض: {name}",
        _THIN,
        "",
        "هل يوجد مرافق مع هذا المريض؟",
    ]
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ نعم، يوجد مرافق", callback_data=f"{GSA}:companion_yes"),
            InlineKeyboardButton("❌ لا يوجد",          callback_data=f"{GSA}:companion_no"),
        ],
        [
            InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_p_visa_expiry"),
            InlineKeyboardButton("🚫 إلغاء", callback_data=f"{GS}:arrivals"),
        ],
    ])
    return "\n".join(lines), kb


def build_p_passport_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx  = session.patient_index + 1
    name = session.current_patient.get("name", "—")
    lines = [
        _DIVIDER,
        f"🛂  **المريض {idx} — جواز السفر**",
        "",
        f"المريض: {name}",
        _THIN,
        "",
        "أرسل صورة جواز السفر.",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_p_companion"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
    ]])
    return "\n".join(lines), kb


def build_p_visa_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx  = session.patient_index + 1
    name = session.current_patient.get("name", "—")
    lines = [
        _DIVIDER,
        f"📄  **المريض {idx} — التأشيرة**",
        "",
        f"المريض: {name}",
        _THIN,
        "",
        "أرسل صورة التأشيرة.",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_p_passport"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
    ]])
    return "\n".join(lines), kb


def build_p_residence_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx  = session.patient_index + 1
    name = session.current_patient.get("name", "—")
    lines = [
        _DIVIDER,
        f"🏠  **المريض {idx} — الإقامة**",
        "",
        f"المريض: {name}",
        _THIN,
        "",
        "أرسل صورة الإقامة، أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭️ تخطي", callback_data=f"{GSA}:skip_p_residence"),
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_p_visa"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
    ]])
    return "\n".join(lines), kb


def build_p_residence_expiry_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx  = session.patient_index + 1
    name = session.current_patient.get("name", "—")
    lines = [
        _DIVIDER,
        f"📋  **المريض {idx} — تاريخ انتهاء الإقامة**",
        "",
        f"المريض: {name}",
        _THIN,
        "",
        "✏️ ردّ على هذه الرسالة بتاريخ انتهاء الإقامة  (مثال: 22/05/2026)،",
        "أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭️ تخطي", callback_data=f"{GSA}:skip_p_residence_expiry"),
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_p_residence"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
    ]])
    return "\n".join(lines), kb


def build_batch_notes_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER,
        "📝  **ملاحظات عامة للدفعة**",
        "",
        f"الجهة الموصلة: {session.hospital_label}",
        f"عدد المرضى: {session.patient_count}",
        _THIN,
        "",
        "✏️ أضف ملاحظات عامة لهذه الدفعة، أو اضغط **⏭️ تخطي**.",
    ]
    if session.batch_notes:
        lines.append(f"\nالملاحظات الحالية: _{session.batch_notes}_")
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭️ تخطي", callback_data=f"{GSA}:skip_batch_notes"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
    ]])
    return "\n".join(lines), kb


# ── Companion loop steps ──────────────────────────────────────────────────────

def build_c_name_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx  = session.patient_index + 1
    name = session.current_patient.get("name", "—")
    lines = [
        _DIVIDER,
        f"🤝  **مرافق المريض {idx} — الاسم**",
        "",
        f"المريض: {name}",
        _THIN,
        "",
        "✏️ اكتب اسم المرافق:",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_p_companion"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
    ]])
    return "\n".join(lines), kb


def build_c_visa_expiry_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx  = session.patient_index + 1
    name = session.current_companion.get("name", "—")
    lines = [
        _DIVIDER,
        f"📋  **مرافق المريض {idx} — تاريخ انتهاء التأشيرة**",
        "",
        f"المرافق: {name}",
        _THIN,
        "",
        "اختر تاريخ انتهاء التأشيرة:",
    ]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📆 اختيار من التقويم", callback_data=f"{GSA}:c_visa_expiry_cal")],
        [
            InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_c_name"),
            InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
        ],
    ])
    return "\n".join(lines), kb


def build_c_passport_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx = session.patient_index + 1
    lines = [
        _DIVIDER,
        f"🛂  **مرافق المريض {idx} — جواز السفر**",
        "",
        "أرسل صورة جواز سفر المرافق.",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_c_visa_expiry"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
    ]])
    return "\n".join(lines), kb


def build_c_visa_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx = session.patient_index + 1
    lines = [
        _DIVIDER,
        f"📄  **مرافق المريض {idx} — التأشيرة**",
        "",
        "أرسل صورة تأشيرة المرافق.",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_c_passport"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
    ]])
    return "\n".join(lines), kb


# ── Review ────────────────────────────────────────────────────────────────────

def build_review(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    date_str = format_arabic_date(session.created_at)
    count    = len(session.completed_patients)
    lines = [
        "🛬 *مراجعة دفعة الوصول*",
        "",
        f"📅 {date_str}",
        f"🏥 {session.hospital_label or _NONE}  •  👨‍⚕️ {session.specialist_label or _NONE}",
        f"👥 *عدد المرضى:*  {count}",
    ]
    for i, p in enumerate(session.completed_patients):
        pname    = p.get("name", "—")
        vis_exp  = p.get("visa_expiry") or "—"
        comp_icon = "✅" if p.get("has_companion") else "❌"
        p_pass = "✅" if p.get("passport_file_id")  else "⬜"
        p_visa = "✅" if p.get("visa_file_id")       else "⬜"
        p_res  = "✅" if p.get("residence_file_id")  else "⬜"
        lines += [
            "",
            f"*{i + 1}.* {pname}",
            f"تأشيرة: {vis_exp}  •  مرافق: {comp_icon}",
            f"📎 {p_pass} جواز  {p_visa} تأشيرة  {p_res} إقامة",
        ]
        for c in p.get("companions", []):
            c_pass = "✅" if c.get("passport_file_id") else "⬜"
            c_visa = "✅" if c.get("visa_file_id")     else "⬜"
            lines.append(f"↳ {c.get('name', '—')}  📎 {c_pass} جواز  {c_visa} تأشيرة")

    lines += [
        "",
        f"📝 *الملاحظات:*  {session.batch_notes or 'لا توجد ملاحظات'}",
        "",
        "هل تريد نشر هذا التقرير؟",
    ]
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 نشر التقرير",   callback_data=f"{GSA}:confirm"),
            InlineKeyboardButton("❌ إلغاء",          callback_data=f"{GSA}:cancel"),
        ],
        [
            InlineKeyboardButton("✏️ تعديل الملاحظات", callback_data=f"{GSA}:back_to_batch_notes"),
        ],
    ])
    return "\n".join(lines), kb


# ── Terminal screens ──────────────────────────────────────────────────────────

def build_success(batch_id: int, hospital_label: str, patient_count: int) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"✅ *تم حفظ ونشر دفعة الوصول بنجاح*\n\n"
        f"رقم الدفعة: `#{batch_id}`\n"
        f"الجهة الموصلة: {hospital_label}\n"
        f"عدد المرضى: {patient_count}\n\n"
        f"📤 تم إرسال التقرير للمسؤولين."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ دفعة جديدة",     callback_data=f"{GSA}:start")],
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
