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
        "",
        "الصورة محفوظة على ملف المريض، وتُرسَل مع «📎 إرسال الوثائق».",
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
        "الاستمارة محفوظة على ملف العائلة، وتُرسَل مع «📎 إرسال الوثائق».",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("👁 عرض الملف", callback_data=f"{RNA}:view_{profile_id}"),
    ]])
    return "\n".join(lines), kb
