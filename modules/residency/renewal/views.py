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


# ⚠️ لا شاشة مخصَّصة لرفع وثيقة المريض/المرافق هنا — `shared.uploads.collector`
# يبني شاشته الخاصة عند `uploads.open(..., title=...)` (في flow.py)، فأي
# دالة عرض هنا لن تُستدعى أبداً. كانتا موجودتين قبل هذا التبسيط بلا أي
# مستدعٍ فعلي (كود ميت موروث)، فأُزيلتا معه.

# ── Step: هل تم تجديد إقامة هذا المرافق؟ (سؤال لكل مرافق على حِدة) ───────────

def build_renewal_c_ready_prompt(session) -> tuple[str, InlineKeyboardMarkup]:
    c     = session.current_companion
    idx   = session.companion_index + 1
    total = len(session.companions)
    c_name = c["name"] if c else "—"
    lines = [
        _DIVIDER,
        f"👤  **مرافق {idx}/{total}**",
        "",
        f"المريض: *{session.profile_name}*",
        f"المرافق: *{c_name}*",
        _THIN,
        "",
        f"هل تم تجديد إقامة *{c_name}*؟",
    ]
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ نعم",           callback_data=f"{RNR}:c_ready_yes"),
            InlineKeyboardButton("❌ لم تجهز بعد",   callback_data=f"{RNR}:c_ready_no"),
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
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{RNR}:cancel"),
    ]])
    return "\n".join(lines), kb


# ── Review ────────────────────────────────────────────────────────────────────

def build_renewal_review(session) -> tuple[str, InlineKeyboardMarkup]:
    exp = format_expiry_date(session.new_expiry_date) if session.new_expiry_date else _NONE
    doc = "✅ تم الرفع" if session.document_file_id else "لا توجد"

    lines = [
        "🪪 *مراجعة تجديد الإقامة*",
        "",
        f"👤 *المريض:*  {session.profile_name}",
        f"📅 *تاريخ الانتهاء الجديد:*  {exp}",
        f"📎 *وثيقة الإقامة:*  {doc}",
    ]

    if session.completed_companions:
        lines.append(f"👥 *المرافقون ({len(session.completed_companions)}):*")
        for c in session.completed_companions:
            if c.get("skipped"):
                lines.append(f"  ❌ {c['name']} — لم تجهز بعد")
            else:
                c_exp = format_expiry_date(c.get("new_expiry", "")) or _NONE
                c_doc = "✅" if c.get("file_id") else "⬜"
                lines.append(f"  ✅ {c['name']}  •  {c_exp}  {c_doc}")
    elif session.companions:
        lines.append("👥 *المرافقون:*  لم تُجهَّز بعد")
    else:
        lines.append("👥 *المرافقون:*  لا يوجد")

    lines += [
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
