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

ولمجموعة غير مضبوطة في الإعدادات (أو للتأكد من واحدة بعينها):
    venv/bin/python scripts/clear_group_reply_keyboard.py --chat-id -1002190577845 --apply

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
        if not raw:
            continue
        # ⚠️ بعض المفاتيح تحمل أكثر من معرّف مفصولة بفواصل
        # (REPORTS_GROUP_ID مثلاً = "-100...388,-100...845")، فتمريرها كما هي
        # لتيليجرام يعامِلها كمعرّف واحد خاطئ. نفصلها هنا، ونحذف المكرّر —
        # فالمعرّف نفسه يتكرّر عادةً بين REPORTS_GROUP_ID وMEDICAL_REPORTS_GROUP_ID
        # ولا داعي لإرسال رسالة مسح مرتين لنفس المجموعة.
        for part in raw.split(","):
            cid = part.strip()
            if not cid or cid in seen:
                continue
            seen.add(cid)
            found.append((key, cid))
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
        # ⚠️ نصّ مرئي فعلي — تيليجرام يرفض الرسالة الفارغة أو المكوَّنة من
        # مسافة صفرية (U+200B) بـ"Text must be non-empty"، ولا يمكن إرسال
        # ReplyKeyboardRemove بلا رسالة تحملها.
        msg = await bot.send_message(
            chat_id=chat_id,
            text="🔄 تم تحديث لوحة الأزرار — لا تحذف هذه الرسالة.",
            reply_markup=ReplyKeyboardRemove(),
        )
    except TelegramError as exc:
        print(f"  ❌ {name} ({chat_id}) — {title}: فشل الإرسال — {exc}")
        return False

    print(f"  ✅ {name} ({chat_id}) — {title}: أُرسل أمر المسح  (msg_id={msg.message_id})")

    # ⚠️⚠️ لا تُحذَف رسالة المسح — وهذا سبب فشل المحاولة الأولى فعلياً:
    # عميل تيليجرام يستنتج لوحة الأزرار الحالية من **آخر رسالة قائمة** في
    # المحادثة. فحذف الرسالة الحاملة لـReplyKeyboardRemove يُسقط الأمر نفسه،
    # فيرجع العميل لآخر رسالة ثبّتت لوحة قبلها وتظهر الأزرار من جديد —
    # ولهذا أبلغ السكربت "4/4 ✅" بينما بقيت اللوحة ظاهرة على الهاتف:
    # الـAPI قَبِل الإرسال فعلاً، ثم أبطلَه الحذف الذي كنّا نُجريه بعده.
    # تبقى الرسالة في المجموعة عمداً — وهي الثمن الوحيد لمسح دائم.
    if "--delete-message" in sys.argv:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg.message_id)
            print("     ↳ ⚠️ حُذفت رسالة المسح بطلبك — قد تعود اللوحة للظهور")
        except TelegramError:
            print("     ↳ (تعذّر الحذف — وهذا أفضل)")
    return True


def _explicit_chat_id() -> str | None:
    if "--chat-id" not in sys.argv:
        return None
    i = sys.argv.index("--chat-id")
    if i + 1 >= len(sys.argv):
        return None
    return sys.argv[i + 1].strip()


async def main() -> int:
    apply = "--apply" in sys.argv

    from config import settings

    token = str(getattr(settings, "BOT_TOKEN", "") or "").strip()
    if not token:
        print("❌ BOT_TOKEN غير مضبوط — لا يمكن المتابعة.")
        return 1

    explicit = _explicit_chat_id()
    if explicit:
        groups = [("--chat-id", explicit)]
    else:
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
        return 0

    # ⚠️ لا تُطمئِن المستخدم إلا إذا نجح شيء فعلاً — الإصدار الأول كان يطبع
    # "اختفت اللوحة" حتى مع 0/4 فاشلة، وهو تقرير نجاح كاذب.
    if ok == 0:
        print("❌ لم تُمسَح أي لوحة — راجع أسباب الفشل أعلاه.")
        return 1
    if ok < len(groups):
        print(f"⚠️ نجح {ok} وفشل {len(groups) - ok} — راجع الأسباب أعلاه.")
    print(
        "\nافتح المجموعة على هاتفك — يجب أن تكون لوحة الأزرار اختفت."
        "\n⚠️ اترك رسالة «تم تحديث لوحة الأزرار» في المجموعة ولا تحذفها:"
        "\n   حذفها يُسقط أمر المسح فتعود الأزرار للظهور."
        "\n💡 إن بقيت الأزرار ظاهرة عندك: أغلق تيليجرام وافتحه (تخزين مؤقت"
        "\n   في العميل)، فالمسح نفسه تمّ على الخادم."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
