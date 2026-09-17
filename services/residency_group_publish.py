# services/residency_group_publish.py
# 🪪 نشر الإقامة الجديدة في مجموعة الإقامات فور توثيقها.
#
# ينشر **الملف نفسه** (بطاقة/مستند الإقامة) بوصف منظَّم يعرّفه: الاسم
# والصفة (مريض أو مرافق ومَن يرافق) وتاريخا الانتهاء والتنبيه. الملف بلا
# وصف ورقةٌ مجهولة في مجموعة فيها عشرات الملفات.
#
# ⚠️ **النشر لا يُفشِل التوثيق أبداً**: التوثيق تمّ وحُفِظ في القاعدة قبل
# أن يُستدعى هذا. فشل الشبكة أو خطأ في صلاحيات المجموعة يُسجَّل ويُبلَّغ
# به، ولا يُلغي عملاً صحيحاً تمّ فعلاً.

from __future__ import annotations

import logging
from datetime import date

logger = logging.getLogger(__name__)

_AR_DAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس",
            "الجمعة", "السبت", "الأحد"]

# ⚠️ محارف Markdown في قيمة من القاعدة تُفشِل **الرسالة كلها** لا سطرها:
# تليجرام يرفض النصّ بـ`can't parse entities`، فيضيع النشر كلّه بسبب اسمٍ
# فيه شرطة سفلية. تُنزَع من كل قيمة تأتي من القاعدة، والعناوين الثابتة في
# الشيفرة تحتفظ بتنسيقها.
_MD_UNSAFE = "*_`[]"


def _safe(text) -> str:
    t = str(text or "").strip()
    for ch in _MD_UNSAFE:
        t = t.replace(ch, "")
    return t


def _fmt_date(iso: str) -> str:
    """التاريخ مع اسم يومه — «2027-02-13» وحده لا يُقرأ بسرعة."""
    s = (iso or "").strip()
    if not s:
        return "—"
    try:
        d = date.fromisoformat(s)
    except ValueError:
        return _safe(s)
    return f"{s}  ({_AR_DAYS[d.weekday()]})"


def _remaining(iso: str) -> str:
    try:
        d = date.fromisoformat((iso or "").strip())
    except ValueError:
        return ""
    n = (d - date.today()).days
    if n < 0:
        return f"  ⚠️ منتهية منذ {abs(n)} يوماً"
    if n == 0:
        return "  ⚠️ تنتهي اليوم"
    return f"  ({n} يوماً)"


def build_caption(person, parent_name: str | None) -> str:
    """وصف الملف المنشور. يُبنى من كائن الشخص بعد تأكيد الإصدار."""
    is_companion = getattr(person, "parent_id", None) is not None
    if is_companion:
        role = "مرافق"
        if parent_name:
            role += f" — مع المريض {_safe(parent_name)}"
    else:
        role = "مريض"

    lines = [
        "🪪 *إقامة جديدة — تم التوثيق*",
        "━━━━━━━━━━━━━━━━━━━━",
        f"👤 *الاسم:* {_safe(person.name)}",
        f"🔖 *الصفة:* {role}",
        "",
        f"📅 *تاريخ الانتهاء:* {_fmt_date(person.expiry_date)}"
        f"{_remaining(person.expiry_date)}",
        f"🔔 *تاريخ التنبيه:* {_fmt_date(person.reminder_date)}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🗓 تاريخ النشر: {date.today().isoformat()}",
    ]
    return "\n".join(lines)


def _group_id():
    from config.settings import RESIDENCY_GROUP_ID
    gid = RESIDENCY_GROUP_ID
    if not gid:
        return None
    try:
        return int(gid)
    except (ValueError, TypeError):
        return gid


async def publish_issuance(bot, person_id: int) -> bool:
    """ينشر ملف الإقامة في مجموعة الإقامات. يُرجِع هل نُشر فعلاً."""
    gid = _group_id()
    if gid is None:
        logger.warning("[residency.publish] RESIDENCY_GROUP_ID غير مضبوط — أُلغي النشر")
        return False

    from modules.residency import repository as rn_repo

    person = rn_repo.get_person(person_id)
    if not person:
        logger.error(f"[residency.publish] لا شخص بالمعرّف {person_id}")
        return False

    file_id = (person.residency_file_id or "").strip()
    if not file_id:
        logger.error(f"[residency.publish] لا ملف إقامة للشخص {person_id}")
        return False

    parent_name = None
    if getattr(person, "parent_id", None):
        parent = rn_repo.get_person(person.parent_id)
        parent_name = getattr(parent, "name", None) if parent else None

    caption = build_caption(person, parent_name)

    # ⚠️ `file_id` في تليجرام **مرتبط بنوعه**: مُعرِّف صورة يُرفَض من
    # `sendDocument` والعكس. والملف يُرفَع صورةً أو مستنداً ولا نخزّن
    # النوع — فتُجرَّب الطريقتان بدل افتراض واحدة.
    from telegram.constants import ParseMode

    for sender, label in ((bot.send_document, "document"), (bot.send_photo, "photo")):
        try:
            await sender(chat_id=gid, **{label: file_id},
                         caption=caption, parse_mode=ParseMode.MARKDOWN)
            logger.info(f"[residency.publish] نُشرت إقامة {person.name} "
                        f"(person_id={person_id}) في {gid}")
            return True
        except Exception as exc:
            last = exc
    logger.error(f"[residency.publish] تعذّر نشر إقامة person_id={person_id}: {last}")
    return False
