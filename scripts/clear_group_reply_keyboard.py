#!/usr/bin/env python3
"""
يمسح "لوحة أزرار البوت" (ReplyKeyboardMarkup) العالقة داخل مجموعات المتابعة.

── المشكلة التي يحلّها ────────────────────────────────────────────────────────
لوحة الأزرار السفلية في تيليجرام ليست جزءاً من الرسالة — بمجرد إرسالها مرة
واحدة لمحادثة ما، تبقى ظاهرة لأعضائها **إلى الأبد** حتى تُمسَح صراحةً بـ
ReplyKeyboardRemove. لا يكفي أن يتوقّف البوت عن إرسالها، ولا حذف الرسالة
التي جاءت معها.

قبل إضافة bot/group_guard.py كان البوت يردّ داخل المجموعات، وأي ردّ يحمل
لوحة القائمة كان يثبّتها هناك. الحارس (group -100) أوقف الردّ نهائياً، لكنه
لا يمسح ما ثُبِّت سابقاً — فتظل الأزرار ظاهرة، وضغطها يُرسل نصّها كرسالة
عادية للمجموعة (يتجاهلها الحارس) فتبدو "لا تعمل". هذا السكربت يمسحها.

⚠️ لماذا سكربت لمرة واحدة لا إصلاح في الكود: لا يوجد مسار في الكود الحالي
يُرسل ReplyKeyboardMarkup لمجموعة (تحقّقنا: بثّ التقارير يُرفق
InlineKeyboardMarkup فقط)، فالعطب بيانات متبقّية لا خلل جارٍ.

── التشغيل ────────────────────────────────────────────────────────────────────
    venv/bin/python scripts/clear_group_reply_keyboard.py            # فحص فقط
    venv/bin/python scripts/clear_group_reply_keyboard.py --apply    # التنفيذ

يرسل رسالة قصيرة تحمل ReplyKeyboardRemove ثم يحذفها، فلا يبقى أثر في
المجموعة. مسح اللوحة يسري لحظة استلام الرسالة ولا يتراجع بحذفها.
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Bot, ReplyKeyboardRemove
from telegram.error import TelegramError

# أسماء متغيّرات البيئة لكل مجموعات المنصّة
_GROUP_ENV_KEYS = [
    "REPORTS_GROUP_ID",
    "MEDICAL_REPORTS_GROUP_ID",
    "CHENNAI_REPORTS_GROUP_ID",
    "NOTIFICATIONS_GROUP_ID",
    "HEALTHCARE_GROUP_ID",
    "GENERAL_SERVICES_GROUP_ID",
    "RESIDENCY_GROUP_ID",
]


def _collect_groups() -> list[tuple[str, str]]:
    from config import settings

    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for key in _GROUP_ENV_KEYS:
        raw = str(getattr(settings, key, "") or "").strip()
        if not raw or raw in seen:
            continue
        seen.add(raw)
        found.append((key, raw))
    return found


async def _clear(bot: Bot, name: str, chat_id: str, apply: bool) -> bool:
    try:
        chat = await bot.get_chat(chat_id)
    except TelegramError as exc:
        print(f"  ⚠️  {name} ({chat_id}): تعذّر الوصول للمجموعة — {exc}")
        return False

    title = chat.title or chat_id
    if not apply:
        print(f"  • {name} ({chat_id}) — {title}   [فحص فقط، لم يُنفَّذ شيء]")
        return True

    try:
        msg = await bot.send_message(
            chat_id=chat_id,
            text="​",  # مسافة صفرية — أقصر رسالة ممكنة
            reply_markup=ReplyKeyboardRemove(),
        )
    except TelegramError as exc:
        print(f"  ❌ {name} ({chat_id}) — {title}: فشل الإرسال — {exc}")
        return False

    print(f"  ✅ {name} ({chat_id}) — {title}: تم مسح اللوحة")

    try:
        await bot.delete_message(chat_id=chat_id, message_id=msg.message_id)
        print("     ↳ وحُذفت رسالة المسح، فلا أثر لها في المجموعة")
    except TelegramError:
        print("     ↳ (تعذّر حذف رسالة المسح — احذفها يدوياً، المسح نفسه تمّ)")
    return True


async def main() -> int:
    apply = "--apply" in sys.argv

    from config import settings

    token = str(getattr(settings, "BOT_TOKEN", "") or "").strip()
    if not token:
        print("❌ BOT_TOKEN غير مضبوط — لا يمكن المتابعة.")
        return 1

    groups = _collect_groups()
    if not groups:
        print("⚠️ لا توجد أي مجموعة مضبوطة في الإعدادات — لا شيء لعمله.")
        return 0

    print(f"\n🔎 المجموعات المضبوطة: {len(groups)}")
    if not apply:
        print("   (وضع الفحص — أضف --apply للتنفيذ الفعلي)\n")
    else:
        print("   (وضع التنفيذ)\n")

    bot = Bot(token=token)
    ok = 0
    for name, chat_id in groups:
        if await _clear(bot, name, chat_id, apply):
            ok += 1

    print(f"\n📊 النتيجة: {ok}/{len(groups)} مجموعة.")
    if not apply:
        print("لم يُنفَّذ أي تغيير. أعد التشغيل مع --apply للمسح الفعلي.")
    else:
        print("افتح المجموعة على هاتفك — يجب أن تكون لوحة الأزرار اختفت.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
