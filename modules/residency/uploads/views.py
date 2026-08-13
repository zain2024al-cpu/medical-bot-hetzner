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
