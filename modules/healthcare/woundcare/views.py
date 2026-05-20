# modules/healthcare/woundcare/views.py
# Pure view builders for the woundcare add-record flow.
# No I/O, no context, no DB — data in, (text, keyboard) out.

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from modules.healthcare.woundcare.session import WoundcareAddSession

# ── Callback prefixes ─────────────────────────────────────────────────────────
HC  = "hc"    # healthcare navigation
WCA = "wca"   # woundcare add flow

_DIVIDER = "━━━━━━━━━━━━━━━━━━━━"
_THIN    = "─────────────────────"


# ── Healthcare main menu ──────────────────────────────────────────────────────

def build_healthcare_menu() -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"{_DIVIDER}\n"
        f"🏥  **الرعاية الصحية**\n\n"
        "اختر القسم:"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🩹 رعاية الجروح", callback_data=f"{HC}:woundcare")],
    ])
    return text, kb


# ── Woundcare submenu ─────────────────────────────────────────────────────────

def build_woundcare_menu() -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"{_DIVIDER}\n"
        f"🩹  **رعاية الجروح**\n\n"
        "اختر العملية:"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة تقرير جرح", callback_data=f"{WCA}:start")],
        [InlineKeyboardButton("⬅️ رجوع",            callback_data=f"{HC}:main")],
    ])
    return text, kb


# ── Notes prompt ──────────────────────────────────────────────────────────────

def build_notes_prompt(session: WoundcareAddSession) -> tuple[str, InlineKeyboardMarkup]:
    """
    Shown after images are collected. User may type notes or skip.
    """
    lines = [
        _DIVIDER,
        "📝  **إضافة ملاحظات**",
        "",
        f"المريض: {session.patient_name}",
        f"نوع الجرح: {', '.join(session.wound_type_labels)}",
        f"الصور: {session.image_count} صورة",
        _THIN,
        "",
        "أرسل ملاحظاتك حول الجرح.",
        "يمكنك وصف الحالة أو العلاج المقدم.",
        "",
        "أو اضغط **⏭️ تخطي** إذا لم يكن هناك ملاحظات.",
    ]
    text = "\n".join(lines)
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏭️ تخطي",  callback_data=f"{WCA}:skip_notes"),
            InlineKeyboardButton("❌ إلغاء", callback_data=f"{WCA}:cancel"),
        ],
    ])
    return text, kb


# ── Review screen ─────────────────────────────────────────────────────────────

def build_review(session: WoundcareAddSession) -> tuple[str, InlineKeyboardMarkup]:
    """
    Full review summary before final save.
    """
    wound_list = "\n".join(f"  • {lbl}" for lbl in session.wound_type_labels) or "  —"
    notes_section = (
        f"\n📝 *الملاحظات:*\n{session.notes}"
        if session.notes else ""
    )
    lines = [
        _DIVIDER,
        "🩹  **مراجعة تقرير الجرح**",
        _THIN,
        "",
        f"👤 *المريض:*  {session.patient_name}",
        "",
        f"🩹 *نوع الجرح:*",
        wound_list,
        "",
        f"📎 *الصور:*  {session.image_count} {'صورة' if session.image_count != 1 else 'صورة واحدة'} مرفوعة",
        notes_section,
        "",
        _THIN,
        "هل تريد حفظ هذا التقرير؟",
    ]
    text = "\n".join(lines)
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ تأكيد الحفظ", callback_data=f"{WCA}:confirm"),
            InlineKeyboardButton("❌ إلغاء",        callback_data=f"{WCA}:cancel"),
        ],
        [InlineKeyboardButton("✏️ تعديل الملاحظات", callback_data=f"{WCA}:edit_notes")],
    ])
    return text, kb


# ── Success screen ────────────────────────────────────────────────────────────

def build_success(record_id: int, patient_name: str, image_count: int) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"✅ *تم حفظ تقرير الجرح بنجاح*\n\n"
        f"رقم التقرير: #{record_id}\n"
        f"المريض: {patient_name}\n"
        f"الصور المرفوعة: {image_count}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ تقرير جديد",  callback_data=f"{WCA}:start")],
        [InlineKeyboardButton("🏥 القائمة الرئيسية", callback_data=f"{HC}:main")],
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
