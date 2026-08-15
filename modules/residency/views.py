# modules/residency/views.py
# بناء الشاشات — المرحلة الأولى فقط (ملفات معلّقة بانتظار الصورة + تاريخ تنبيه).

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from modules.residency.constants import RN
from modules.residency.repository import ProfileRow

_DIVIDER = "━━━━━━━━━━━━━━━━━━━━"
_THIN = "─────────────────────"


def build_pending_list(profiles: list[ProfileRow]) -> tuple[str, InlineKeyboardMarkup]:
    lines = [_DIVIDER, "🪪  **الملفات المعلّقة**", ""]
    rows: list[list[InlineKeyboardButton]] = []

    if not profiles:
        lines.append("✅ لا توجد ملفات معلّقة حالياً.")
    else:
        lines.append(f"يوجد {len(profiles)} ملفاً — اضغط على اسم لفتحه:")
        lines.append(_THIN)
        for p in profiles:
            photo_mark = "✅" if p.photo_file_id else "⬜"
            remind_mark = f"📅 {p.reminder_date}" if p.reminder_date else "📅 —"
            lines.append(f"👤 {p.name}   صورة {photo_mark}   {remind_mark}")
            rows.append([InlineKeyboardButton(
                f"📂 {p.name[:25]}", callback_data=f"{RN}:view_{p.id}",
            )])

    return "\n".join(lines), InlineKeyboardMarkup(rows)


def build_profile_detail(profile: ProfileRow, *, is_admin: bool) -> tuple[str, InlineKeyboardMarkup]:
    photo_mark = "✅ مرفوعة" if profile.photo_file_id else "⬜ غير مرفوعة"
    remind_text = profile.reminder_date if profile.reminder_date else "➖ غير محدَّد"

    lines = [
        _DIVIDER,
        "🪪  **ملف المريض**",
        "",
        f"👤 *{profile.name}*",
        _THIN,
        f"📷 *الصورة الشخصية:*  {photo_mark}",
        f"📅 *تاريخ التنبيه:*  {remind_text}",
    ]
    if profile.companions:
        lines.append(_THIN)
        lines.append(f"👥 *المرافقون ({len(profile.companions)}):*")
        for name in profile.companions:
            lines.append(f"  • {name}")
    lines.append(_THIN)

    rows = [
        [InlineKeyboardButton("📷 رفع الصورة الشخصية", callback_data=f"{RN}:photo_{profile.id}")],
        [InlineKeyboardButton("📅 تاريخ التنبيه", callback_data=f"{RN}:remind_{profile.id}")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(
            "✅ تم تقديم طلب الإقامة لهذا المريض والمرافقين",
            callback_data=f"{RN}:submit_{profile.id}",
        )])
    rows.append([InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:list")])

    return "\n".join(lines), InlineKeyboardMarkup(rows)


def build_photo_prompt(profile: ProfileRow) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"{_DIVIDER}\n📷  **رفع الصورة الشخصية**\n\n"
        f"المريض: {profile.name}\n\n"
        f"أرسل الصورة الآن."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ رجوع", callback_data=f"{RN}:view_{profile.id}")],
    ])
    return text, kb
