# modules/residency/uploads/views.py
# شاشات نتيجة رفع فورم C والصورة الشخصية — تُفتحان من زرّين في ملف المريض
# نفسه (`build_profile_detail`)، لا من شاشة قائمة منفصلة.
#
# ⚠️ شاشة الوحدة القديمة («📤 الرفع والمتابعة» بمنتقياتها) حُذفت بالكامل —
# قرار المستخدم: كل شيء عبر «📁 أرشيف المرضى» ← ملف المريض مباشرة. فورم C
# والصورة الشخصية صارا زرّين على ملف المريض نفسه
# (`modules/residency/profiles/views.py`).

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from modules.residency.views import _DIVIDER

RN  = "rn"
RNU = "rnu"
RNA = "rna"

# ✅ الأنواع التي لم يكن لها أي مسار رفع/تصحيح داخل بوت الإقامات إطلاقاً
# قبل هذه الميزة — لكل واحد منها عمود مطابق بالاسم على ResidencyProfile
# وResidencyCompanion (passport_file_id/visa_file_id/tickets_file_id).
# الإقامة نفسها مستبعَدة عمداً: تبقى حصراً على مسار «🪪 تجديد الإقامة»
# الكامل حتى لا يصير للحقل مصدران (قرار المستخدم صراحةً).
DOCUMENT_TYPES: dict[str, tuple[str, str]] = {
    "passport": ("📔", "جواز سفر"),
    "visa":     ("🛂", "فيزا"),
    "tickets":  ("🎫", "تذكرة سفر"),
}


def build_photo_saved(name: str, profile_id: int, *, resized: bool = True) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER,
        "✅  **تم رفع الصورة الشخصية**",
        "",
        f"👤 {name}",
        "",
        ("📐 ضُبطت على مقاس 4×6." if resized else
         "⚠️ حُفظت بمقاسها الأصلي — تعذّر ضبطها على 4×6، حاول رفعها مجدداً."),
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("👁 عرض الملف", callback_data=f"{RNA}:view_{profile_id}"),
    ]])
    return "\n".join(lines), kb


def build_photo_target_picker(profile_name: str, profile_id: int, companions) -> tuple[str, InlineKeyboardMarkup]:
    """
    اختيار لمن الصورة الشخصية — المريض أو أحد مرافقيه — يظهر فقط إذا
    كان للملف مرافقون، وإلا تُرفَع للمريض مباشرة بلا سؤال (لا داعي
    لتخيير المستخدم بين خيار واحد فقط).
    """
    text = (
        f"{_DIVIDER}\n🖼️  **الصورة الشخصية**\n\n"
        "لمن الصورة؟"
    )
    rows = [[InlineKeyboardButton(f"👤 {profile_name} (المريض)", callback_data=f"{RNU}:photosel_{profile_id}_p")]]
    for c in companions:
        rows.append([InlineKeyboardButton(f"👤 {c.name}", callback_data=f"{RNU}:photosel_{profile_id}_{c.id}")])
    rows.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"{RNA}:view_{profile_id}")])
    return text, InlineKeyboardMarkup(rows)


def build_document_type_menu(profile_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """
    القائمة الموحَّدة «🗂️ رفع وثيقة» — تحلّ محل زرَّي «📄 فورم C» و«🖼️ صورة
    شخصية» المنفصلين سابقاً على ملف المريض، وتضيف إليهما جواز/فيزا/تذكرة
    التي لم يكن لها أي مسار رفع من قبل (تُستخدَم عند تخطّي أحدها بالخطأ
    أثناء الواصلين). الصورة وفورم C يُوجَّهان لمعالِجيهما الأصليين
    بلا أي تغيير — فقط جواز/فيزا/تذكرة مسار جديد.
    """
    text = f"{_DIVIDER}\n🗂️  **رفع وثيقة**\n\nاختر نوع الوثيقة:"
    rows = [
        [InlineKeyboardButton("🖼️ صورة شخصية", callback_data=f"{RNU}:photo_{profile_id}")],
        [InlineKeyboardButton("📄 فورم C",       callback_data=f"{RNU}:formc_{profile_id}")],
    ]
    for doc_type, (icon, label) in DOCUMENT_TYPES.items():
        rows.append([InlineKeyboardButton(f"{icon} {label}", callback_data=f"{RNU}:doc_{doc_type}_{profile_id}")])
    rows.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"{RNA}:view_{profile_id}")])
    return text, InlineKeyboardMarkup(rows)


def build_document_target_picker(doc_type: str, profile_name: str, profile_id: int, companions) -> tuple[str, InlineKeyboardMarkup]:
    """نسخة عامة من build_photo_target_picker — لجواز/فيزا/تذكرة."""
    icon, label = DOCUMENT_TYPES[doc_type]
    text = f"{_DIVIDER}\n{icon}  **{label}**\n\nلمن الوثيقة؟"
    rows = [[InlineKeyboardButton(f"👤 {profile_name} (المريض)", callback_data=f"{RNU}:docsel_{doc_type}_{profile_id}_p")]]
    for c in companions:
        rows.append([InlineKeyboardButton(f"👤 {c.name}", callback_data=f"{RNU}:docsel_{doc_type}_{profile_id}_{c.id}")])
    rows.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"{RNA}:view_{profile_id}")])
    return text, InlineKeyboardMarkup(rows)


def build_document_saved(doc_type: str, name: str, profile_id: int) -> tuple[str, InlineKeyboardMarkup]:
    icon, label = DOCUMENT_TYPES[doc_type]
    lines = [
        _DIVIDER,
        f"✅  **تم رفع {label}**",
        "",
        f"👤 {name}",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("👁 عرض الملف", callback_data=f"{RNA}:view_{profile_id}"),
    ]])
    return "\n".join(lines), kb


def build_form_c_saved(name: str, profile_id: int) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER,
        "✅  **تم رفع فورم C**",
        "",
        f"👤 {name}",
        "",
        "الاستمارة محفوظة على ملف العائلة، وتُرسَل ضمن «📄 ملف PDF».",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("👁 عرض الملف", callback_data=f"{RNA}:view_{profile_id}"),
    ]])
    return "\n".join(lines), kb
