# modules/residency/renewal/views.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from modules.residency.views import (
    format_expiry_date, format_days_remaining, _DIVIDER, _THIN, _NONE,
)

RN  = "rn"
RNR = "rnr"


# ── Step: expiry date ─────────────────────────────────────────────────────────

def build_renewal_expiry_prompt(session) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER,
        "🪪  **تجديد الإقامة**",
        "",
        f"المريض: *{session.profile_name}*",
        _THIN,
        "",
        "اختر تاريخ انتهاء الإقامة الجديدة من التقويم:",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{RNR}:cancel"),
    ]])
    return "\n".join(lines), kb


# ── Step: residency number (main patient) ────────────────────────────────────

def build_renewal_residency_number_prompt(session) -> tuple[str, InlineKeyboardMarkup]:
    exp = format_expiry_date(session.new_expiry_date) if session.new_expiry_date else _NONE
    lines = [
        _DIVIDER,
        "🪪  **رقم الإقامة الجديدة**",
        "",
        f"المريض: *{session.profile_name}*",
        f"تاريخ الانتهاء: *{exp}*",
        _THIN,
        "",
        "✏️ أرسل رقم الإقامة الجديدة، أو اضغط **⏭️ تخطي**:",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭️ تخطي", callback_data=f"{RNR}:skip_residency_number"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{RNR}:cancel"),
    ]])
    return "\n".join(lines), kb


# ── Step: companion residency number ─────────────────────────────────────────

def build_renewal_c_residency_number_prompt(session) -> tuple[str, InlineKeyboardMarkup]:
    c     = session.current_companion
    idx   = session.companion_index + 1
    total = len(session.companions)
    c_name = c["name"] if c else "—"
    lines = [
        _DIVIDER,
        f"🪪  **رقم إقامة المرافق {idx}/{total}**",
        "",
        f"المريض: *{session.profile_name}*",
        f"المرافق: *{c_name}*",
        _THIN,
        "",
        "✏️ أرسل رقم الإقامة الجديدة، أو اضغط **⏭️ تخطي**:",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭️ تخطي", callback_data=f"{RNR}:skip_c_residency_number"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{RNR}:cancel"),
    ]])
    return "\n".join(lines), kb


# ── Step: document upload ─────────────────────────────────────────────────────

def build_renewal_document_prompt(session) -> tuple[str, InlineKeyboardMarkup]:
    exp = format_expiry_date(session.new_expiry_date) if session.new_expiry_date else _NONE
    lines = [
        _DIVIDER,
        "📎  **وثيقة الإقامة الجديدة**",
        "",
        f"المريض: *{session.profile_name}*",
        f"تاريخ الانتهاء الجديد: *{exp}*",
        _THIN,
        "",
        "أرسل صورة وثيقة الإقامة الجديدة، ثم اضغط **✅ انتهيت**.",
        "أو اضغط **⏭️ تخطي** إذا لم تكن متوفرة الآن.",
    ]
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ انتهيت", callback_data=f"{RNR}:doc_done"),
            InlineKeyboardButton("⏭️ تخطي",  callback_data=f"{RNR}:skip_doc"),
        ],
        [InlineKeyboardButton("❌ إلغاء",    callback_data=f"{RNR}:cancel")],
    ])
    return "\n".join(lines), kb


# ── Step: companions question ─────────────────────────────────────────────────

def build_renewal_companions_prompt(session) -> tuple[str, InlineKeyboardMarkup]:
    comp_count = len(session.companions)
    lines = [
        _DIVIDER,
        "👥  **تجديد إقامات المرافقين**",
        "",
        f"المريض: *{session.profile_name}*",
        _THIN,
    ]
    if comp_count == 0:
        lines += ["", "لا يوجد مرافقون مسجلون."]
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ متابعة", callback_data=f"{RNR}:no_companions"),
            InlineKeyboardButton("❌ إلغاء",  callback_data=f"{RNR}:cancel"),
        ]])
    else:
        lines += [
            "",
            f"يوجد {comp_count} مرافق. هل تريد تحديث إقاماتهم الآن؟",
        ]
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ نعم، تحديث الآن",   callback_data=f"{RNR}:companions_yes"),
                InlineKeyboardButton("⏭️ تخطي مؤقتاً",       callback_data=f"{RNR}:companions_skip"),
            ],
            [InlineKeyboardButton("❌ إلغاء", callback_data=f"{RNR}:cancel")],
        ])
    return "\n".join(lines), kb


# ── Step: companion expiry ────────────────────────────────────────────────────

def build_renewal_c_expiry_prompt(session) -> tuple[str, InlineKeyboardMarkup]:
    c    = session.current_companion
    idx  = session.companion_index + 1
    total = len(session.companions)
    lines = [
        _DIVIDER,
        f"📅  **انتهاء إقامة المرافق {idx}/{total}**",
        "",
        f"المريض: *{session.profile_name}*",
        f"المرافق: *{c['name']}*",
        _THIN,
        "",
        "اختر تاريخ انتهاء الإقامة الجديدة من التقويم:",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭️ تخطي هذا المرافق", callback_data=f"{RNR}:skip_c"),
        InlineKeyboardButton("❌ إلغاء",             callback_data=f"{RNR}:cancel"),
    ]])
    return "\n".join(lines), kb


# ── Step: companion document ──────────────────────────────────────────────────

def build_renewal_c_document_prompt(session) -> tuple[str, InlineKeyboardMarkup]:
    c    = session.current_companion
    idx  = session.companion_index + 1
    total = len(session.companions)
    exp  = format_expiry_date(session.companions[session.companion_index - 1].get("_new_expiry", "")) \
           if session.companion_index > 0 else _NONE
    lines = [
        _DIVIDER,
        f"📎  **وثيقة المرافق {idx}/{total}**",
        "",
        f"المريض: *{session.profile_name}*",
        f"المرافق: *{c['name']}*",
        _THIN,
        "",
        "أرسل صورة وثيقة إقامة المرافق الجديدة، ثم اضغط **✅ انتهيت**.",
    ]
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ انتهيت", callback_data=f"{RNR}:c_doc_done"),
            InlineKeyboardButton("⏭️ تخطي",  callback_data=f"{RNR}:skip_c_doc"),
        ],
        [InlineKeyboardButton("❌ إلغاء",    callback_data=f"{RNR}:cancel")],
    ])
    return "\n".join(lines), kb


# ── Step: notes ───────────────────────────────────────────────────────────────

def build_renewal_notes_prompt(session) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER,
        "📝  **ملاحظات التجديد**",
        "",
        f"المريض: *{session.profile_name}*",
        _THIN,
        "",
        "أرسل ملاحظاتك، أو اضغط **⏭️ تخطي**:",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭️ تخطي", callback_data=f"{RNR}:skip_notes"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{RNR}:cancel"),
    ]])
    return "\n".join(lines), kb


# ── Review ────────────────────────────────────────────────────────────────────

def build_renewal_review(session) -> tuple[str, InlineKeyboardMarkup]:
    exp     = format_expiry_date(session.new_expiry_date) if session.new_expiry_date else _NONE
    res_num = session.new_residency_number or _NONE
    doc     = "✅ تم الرفع" if session.document_file_id else "لا توجد"
    notes   = session.notes or "لا توجد ملاحظات"

    lines = [
        "🪪 *مراجعة تجديد الإقامة*",
        "",
        f"👤 *المريض:*  {session.profile_name}",
        f"🪪 *رقم الإقامة الجديد:*  {res_num}",
        f"📅 *تاريخ الانتهاء الجديد:*  {exp}",
        f"📎 *وثيقة الإقامة:*  {doc}",
    ]

    if session.completed_companions:
        lines.append(f"👥 *المرافقون ({len(session.completed_companions)}):*")
        for c in session.completed_companions:
            if c.get("skipped"):
                lines.append(f"  ⏭️ {c['name']} — تخطي مؤقت")
            else:
                c_exp = format_expiry_date(c.get("new_expiry", "")) or _NONE
                c_doc = "✅" if c.get("file_id") else "⬜"
                c_num = c.get("residency_number") or "—"
                lines.append(f"  ✅ {c['name']}  🪪 {c_num}  •  {c_exp}  {c_doc}")
    elif session.companions:
        lines.append("👥 *المرافقون:*  تخطي مؤقت")
    else:
        lines.append("👥 *المرافقون:*  لا يوجد")

    lines += [
        f"📝 *الملاحظات:*  {notes}",
        "",
        "هل تريد حفظ هذا التجديد؟",
    ]

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ حفظ التجديد", callback_data=f"{RNR}:confirm"),
            InlineKeyboardButton("❌ إلغاء",        callback_data=f"{RNR}:cancel"),
        ],
    ])
    return "\n".join(lines), kb


# ── Terminal ──────────────────────────────────────────────────────────────────

def build_renewal_success(profile_id: int, profile_name: str, is_dependent: bool) -> tuple[str, InlineKeyboardMarkup]:
    if is_dependent:
        status_line = "⏳ *الحالة:* مرافقون معلقون — تم الإصدار جزئياً"
    else:
        status_line = "✅ *الحالة:* تم الإصدار بالكامل"
    text = (
        f"🪪 *تم حفظ التجديد بنجاح*\n\n"
        f"👤 {profile_name}\n"
        f"{status_line}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📁 عرض الملف",    callback_data=f"rna:view_{profile_id}")],
        [InlineKeyboardButton("⏰ المتابعة",      callback_data=f"{RN}:followup")],
        [InlineKeyboardButton("🪪 الإقامات",     callback_data=f"{RN}:main")],
    ])
    return text, kb


def build_renewal_cancelled() -> tuple[str, InlineKeyboardMarkup]:
    text = "❌ *تم إلغاء التجديد.*"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🪪 الإقامات", callback_data=f"{RN}:main")]])
    return text, kb
