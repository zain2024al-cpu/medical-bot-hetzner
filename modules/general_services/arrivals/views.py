# modules/general_services/arrivals/views.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from modules.general_services.arrivals.session import ArrivalSession
from modules.general_services.views import (
    format_arabic_datetime, format_arabic_date,
    _DIVIDER, _THIN, _NONE,
)
from modules.general_services.constants import STAFF_MAP

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


# ── Step 2: المختص ────────────────────────────────────────────────────────────
# ✅ خطوة "🏥 المستشفى/الجهة الموصلة" على مستوى الدفعة أُزيلت نهائياً — "الجهة
# الموصلة" أصبحت حقلاً خاصاً بكل فرد (انظر build_p_escort_entity_prompt أدناه).

def build_specialist_prompt() -> tuple[str, InlineKeyboardMarkup]:
    lines = [_DIVIDER, "👨‍⚕️  **اختر المختص المسؤول**", "", "اختر المختص:"]
    rows = [
        [InlineKeyboardButton(label, callback_data=f"{GSA}:specialist_{sid}")]
        for sid, label in STAFF_MAP.items()
    ]
    rows.append([
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_to_batch_notes"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
    ])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


# ── Step 3: عدد المرضى ────────────────────────────────────────────────────────

def build_patient_count_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER,
        "👥  **عدد المرضى في الدفعة**",
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
            InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:start"),
            InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
        ],
    ]
    return "\n".join(lines), InlineKeyboardMarkup(rows)


# ── Patient loop steps ─────────────────────────────────────────────────────────
# ✅ لا يوجد بعد الآن أي شاشة "اكتب اسم المريض" — الاسم يُختار إلزامياً من
# patient_selector مباشرة (راجع _show_p_name في flow.py). كل الشاشات التالية
# تُعرض بعد الاختيار مباشرة.

def build_p_arrival_date_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx  = session.patient_index + 1
    name = session.current_patient.get("name", "—")
    lines = [
        _DIVIDER,
        f"📅  **المريض {idx} — تاريخ الوصول**",
        "",
        f"المريض: {name}",
        _THIN,
        "",
        "اختر تاريخ وصول هذا المريض، أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📆 اختيار من التقويم", callback_data=f"{GSA}:p_arrival_date_cal")],
        [
            InlineKeyboardButton("⏭️ تخطي", callback_data=f"{GSA}:skip_p_arrival_date"),
            InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_p_name"),
        ],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals")],
    ])
    return "\n".join(lines), kb


def build_p_passport_expiry_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx  = session.patient_index + 1
    name = session.current_patient.get("name", "—")
    lines = [
        _DIVIDER,
        f"🛂  **المريض {idx} — تاريخ انتهاء الجواز**",
        "",
        f"المريض: {name}",
        _THIN,
        "",
        "اختر تاريخ انتهاء الجواز، أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📆 اختيار من التقويم", callback_data=f"{GSA}:p_passport_expiry_cal")],
        [
            InlineKeyboardButton("⏭️ تخطي", callback_data=f"{GSA}:skip_p_passport_expiry"),
            InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_p_arrival_date"),
        ],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals")],
    ])
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
            InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_p_passport_expiry"),
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


def build_p_entry_stamp_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx  = session.patient_index + 1
    name = session.current_patient.get("name", "—")
    lines = [
        _DIVIDER,
        f"📮  **المريض {idx} — ختم الدخول**",
        "",
        f"المريض: {name}",
        _THIN,
        "",
        "أرسل صورة ختم الدخول، أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭️ تخطي", callback_data=f"{GSA}:skip_p_entry_stamp"),
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_p_visa"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
    ]])
    return "\n".join(lines), kb


def build_p_tickets_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx  = session.patient_index + 1
    name = session.current_patient.get("name", "—")
    lines = [
        _DIVIDER,
        f"🎫  **المريض {idx} — التذاكر**",
        "",
        f"المريض: {name}",
        _THIN,
        "",
        "أرسل صورة التذاكر، أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭️ تخطي", callback_data=f"{GSA}:skip_p_tickets"),
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_p_entry_stamp"),
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
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_p_tickets"),
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
        "اختر تاريخ انتهاء الإقامة:",
    ]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📆 اختيار من التقويم", callback_data=f"{GSA}:p_residence_expiry_cal")],
        [
            InlineKeyboardButton("⏭️ تخطي", callback_data=f"{GSA}:skip_p_residence_expiry"),
            InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_p_residence"),
        ],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals")],
    ])
    return "\n".join(lines), kb


def build_p_indiv_notes_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx  = session.patient_index + 1
    name = session.current_patient.get("name", "—")
    lines = [
        _DIVIDER,
        f"📝  **المريض {idx} — ملاحظات**",
        "",
        f"المريض: {name}",
        _THIN,
        "",
        "✏️ أضف ملاحظات خاصة بهذا المريض، أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭️ تخطي", callback_data=f"{GSA}:skip_p_indiv_notes"),
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_p_residence_expiry"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
    ]])
    return "\n".join(lines), kb


def build_p_services_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx  = session.patient_index + 1
    name = session.current_patient.get("name", "—")
    lines = [
        _DIVIDER,
        f"🛎️  **المريض {idx} — الخدمات المقدَّمة أثناء الوصول**",
        "",
        f"المريض: {name}",
        _THIN,
        "",
        "✏️ اكتب الخدمات المقدَّمة له أثناء الوصول، أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭️ تخطي", callback_data=f"{GSA}:skip_p_services"),
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_p_indiv_notes"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
    ]])
    return "\n".join(lines), kb


def build_p_escort_entity_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx  = session.patient_index + 1
    name = session.current_patient.get("name", "—")
    lines = [
        _DIVIDER,
        f"🚐  **المريض {idx} — الجهة الموصلة**",
        "",
        f"المريض: {name}",
        _THIN,
        "",
        "✏️ اكتب الجهة الموصلة لهذا المريض، أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭️ تخطي", callback_data=f"{GSA}:skip_p_escort_entity"),
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_p_services"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
    ]])
    return "\n".join(lines), kb


def build_p_residence_address_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx  = session.patient_index + 1
    name = session.current_patient.get("name", "—")
    lines = [
        _DIVIDER,
        f"🏠  **المريض {idx} — عنوان السكن**",
        "",
        f"المريض: {name}",
        _THIN,
        "",
        "✏️ اكتب عنوان سكن المريض، أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭️ تخطي", callback_data=f"{GSA}:skip_p_residence_address"),
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_p_escort_entity"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
    ]])
    return "\n".join(lines), kb


def build_batch_notes_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER,
        "📝  **ملاحظات عامة للدفعة**",
        "",
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
# ✅ نفس القائمة الكاملة من الحقول التي يمر بها المريض تماماً (بلا خطوة
# "هل يوجد مرافق؟" التي تخص المريض فقط). لا شاشة "اكتب اسم المرافق" — الاسم
# يُختار إلزامياً من patient_selector مباشرة (راجع _show_c_name في flow.py).

def build_c_arrival_date_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx  = session.patient_index + 1
    name = session.current_companion.get("name", "—")
    lines = [
        _DIVIDER,
        f"📅  **مرافق المريض {idx} — تاريخ الوصول**",
        "",
        f"المرافق: {name}",
        _THIN,
        "",
        "اختر تاريخ وصول المرافق، أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📆 اختيار من التقويم", callback_data=f"{GSA}:c_arrival_date_cal")],
        [
            InlineKeyboardButton("⏭️ تخطي", callback_data=f"{GSA}:skip_c_arrival_date"),
            InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_c_name"),
        ],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals")],
    ])
    return "\n".join(lines), kb


def build_c_passport_expiry_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx  = session.patient_index + 1
    name = session.current_companion.get("name", "—")
    lines = [
        _DIVIDER,
        f"🛂  **مرافق المريض {idx} — تاريخ انتهاء الجواز**",
        "",
        f"المرافق: {name}",
        _THIN,
        "",
        "اختر تاريخ انتهاء الجواز، أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📆 اختيار من التقويم", callback_data=f"{GSA}:c_passport_expiry_cal")],
        [
            InlineKeyboardButton("⏭️ تخطي", callback_data=f"{GSA}:skip_c_passport_expiry"),
            InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_c_arrival_date"),
        ],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals")],
    ])
    return "\n".join(lines), kb


def build_c_visa_expiry_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx  = session.patient_index + 1
    name = session.current_companion.get("name", "—")
    lines = [
        _DIVIDER,
        f"📋  **مرافق المريض {idx} — تاريخ انتهاء الإقامة**",
        "",
        f"المرافق: {name}",
        _THIN,
        "",
        "اختر تاريخ انتهاء الإقامة:",
    ]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📆 اختيار من التقويم", callback_data=f"{GSA}:c_visa_expiry_cal")],
        [
            InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_c_passport_expiry"),
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


def build_c_entry_stamp_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx  = session.patient_index + 1
    name = session.current_companion.get("name", "—")
    lines = [
        _DIVIDER,
        f"📮  **مرافق المريض {idx} — ختم الدخول**",
        "",
        f"المرافق: {name}",
        _THIN,
        "",
        "أرسل صورة ختم الدخول، أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭️ تخطي", callback_data=f"{GSA}:skip_c_entry_stamp"),
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_c_visa"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
    ]])
    return "\n".join(lines), kb


def build_c_tickets_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx  = session.patient_index + 1
    name = session.current_companion.get("name", "—")
    lines = [
        _DIVIDER,
        f"🎫  **مرافق المريض {idx} — التذاكر**",
        "",
        f"المرافق: {name}",
        _THIN,
        "",
        "أرسل صورة التذاكر، أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭️ تخطي", callback_data=f"{GSA}:skip_c_tickets"),
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_c_entry_stamp"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
    ]])
    return "\n".join(lines), kb


def build_c_residence_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx  = session.patient_index + 1
    name = session.current_companion.get("name", "—")
    lines = [
        _DIVIDER,
        f"🏠  **مرافق المريض {idx} — الإقامة**",
        "",
        f"المرافق: {name}",
        _THIN,
        "",
        "أرسل صورة الإقامة، أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭️ تخطي", callback_data=f"{GSA}:skip_c_residence"),
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_c_tickets"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
    ]])
    return "\n".join(lines), kb


def build_c_indiv_notes_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx  = session.patient_index + 1
    name = session.current_companion.get("name", "—")
    lines = [
        _DIVIDER,
        f"📝  **مرافق المريض {idx} — ملاحظات**",
        "",
        f"المرافق: {name}",
        _THIN,
        "",
        "✏️ أضف ملاحظات خاصة بهذا المرافق، أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭️ تخطي", callback_data=f"{GSA}:skip_c_indiv_notes"),
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_c_residence"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
    ]])
    return "\n".join(lines), kb


def build_c_services_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx  = session.patient_index + 1
    name = session.current_companion.get("name", "—")
    lines = [
        _DIVIDER,
        f"🛎️  **مرافق المريض {idx} — الخدمات المقدَّمة أثناء الوصول**",
        "",
        f"المرافق: {name}",
        _THIN,
        "",
        "✏️ اكتب الخدمات المقدَّمة له أثناء الوصول، أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭️ تخطي", callback_data=f"{GSA}:skip_c_services"),
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_c_indiv_notes"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
    ]])
    return "\n".join(lines), kb


def build_c_escort_entity_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx  = session.patient_index + 1
    name = session.current_companion.get("name", "—")
    lines = [
        _DIVIDER,
        f"🚐  **مرافق المريض {idx} — الجهة الموصلة**",
        "",
        f"المرافق: {name}",
        _THIN,
        "",
        "✏️ اكتب الجهة الموصلة لهذا المرافق، أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭️ تخطي", callback_data=f"{GSA}:skip_c_escort_entity"),
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_c_services"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
    ]])
    return "\n".join(lines), kb


def build_c_residence_address_prompt(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    idx  = session.patient_index + 1
    name = session.current_companion.get("name", "—")
    lines = [
        _DIVIDER,
        f"🏠  **مرافق المريض {idx} — عنوان السكن**",
        "",
        f"المرافق: {name}",
        _THIN,
        "",
        "✏️ اكتب عنوان سكن المرافق، أو اضغط **⏭️ تخطي**.",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭️ تخطي", callback_data=f"{GSA}:skip_c_residence_address"),
        InlineKeyboardButton("⬅️ رجوع", callback_data=f"{GSA}:back_c_escort_entity"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{GS}:arrivals"),
    ]])
    return "\n".join(lines), kb


# ── Review ────────────────────────────────────────────────────────────────────

def _individual_detail_lines(entity: dict, *, is_companion: bool) -> list[str]:
    """سطور العرض المشتركة لمريض أو مرافق في شاشة المراجعة/التقرير المنشور."""
    vis_exp   = entity.get("visa_expiry") or entity.get("residence_expiry") or "—"
    p_pass    = "✅" if entity.get("passport_file_id")    else "⬜"
    p_visa    = "✅" if entity.get("visa_file_id")         else "⬜"
    p_stamp   = "✅" if entity.get("entry_stamp_file_id")  else "⬜"
    p_tickets = "✅" if entity.get("tickets_file_id")      else "⬜"
    escort    = entity.get("escort_entity") or "—"
    lines = [
        f"   📋 تأشيرة: {vis_exp}",
        f"   📎 جواز {p_pass}   تأشيرة {p_visa}   ختم {p_stamp}   تذاكر {p_tickets}",
        f"   🚐 الجهة الموصلة: {escort}",
    ]
    return lines


def build_review(session: ArrivalSession) -> tuple[str, InlineKeyboardMarkup]:
    date_str = format_arabic_datetime(session.created_at)
    count    = len(session.completed_patients)
    lines = [
        "🛬 *مراجعة دفعة الوصول*",
        _DIVIDER,
        f"📅 *التاريخ:*  {date_str}",
        f"👨‍⚕️ *المسؤول:*  {session.specialist_label or _NONE}",
        f"👥 *عدد المرضى:*  {count}",
        _THIN,
        "*قائمة المرضى:*",
    ]
    for i, p in enumerate(session.completed_patients):
        pname     = p.get("name", "—")
        comp_icon = "✅" if p.get("has_companion") else "❌"
        lines += [
            "",
            f"*{i + 1}.* {pname}",
            f"   🤝 مرافق: {comp_icon}",
        ] + _individual_detail_lines(p, is_companion=False)
        for c in p.get("companions", []):
            lines += [f"   ↳ *{c.get('name', '—')}*"] + [
                f"      {ln.strip()}" for ln in _individual_detail_lines(c, is_companion=True)
            ]

    lines += [
        "",
        _THIN,
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
        [
            InlineKeyboardButton("✏️ تعديل المختص",     callback_data=f"{GSA}:back_to_specialist"),
        ],
    ])
    return "\n".join(lines), kb


# ── Terminal screens ──────────────────────────────────────────────────────────

def build_success(batch_id: int, patient_count: int) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"✅ *تم حفظ ونشر دفعة الوصول بنجاح*\n\n"
        f"رقم الدفعة: `#{batch_id}`\n"
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
