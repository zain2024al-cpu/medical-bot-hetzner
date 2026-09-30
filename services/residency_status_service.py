# services/residency_status_service.py
# الانتقال التلقائي اليومي: ACTIVE → EXPIRY_PENDING عند وصول تاريخ
# التنبيه اليدوي لكل شخص.

import logging
from datetime import date

logger = logging.getLogger(__name__)

# ⚠️ تنبيه المجموعة (send_residency_expiry_alert) يُستدعى **فقط** من
# مهمّتَي app.py (الجدولة اليومية ٩:٠٠ وتعويض الإقلاع) — لا من
# `_reevaluate_after_activation`/`_reevaluate_after_date_change` في
# modules/residency/models.py (إعادة تقييم فورية عند إدخال المستخدم
# مباشرة). لو نبّهت هذه أيضاً، كل إدخال تاريخ تنبيه ماضٍ بالخطأ أثناء
# تسجيل حالة كان سيُطلِق رسالة فورية في مجموعة الإقامة — ضوضاء لا يريدها
# أحد لعملية إدخال بيانات عادية. البقاء على التمييز: الفحص نفسه (كتابة
# قاعدة بيانات) مشترك ومُعاد استخدامه دائماً؛ الإشعار حصريّ للمسار اليومي.
_MAX_CHARS = 3500
_DIV = "━━━━━━━━━━━━━━━━━━━━"
_MD_UNSAFE = "*_`[]"


def _safe(text) -> str:
    t = str(text or "").strip()
    for ch in _MD_UNSAFE:
        t = t.replace(ch, "")
    return t


def run_daily_expiry_check() -> list[dict]:
    """يُستدعى من app.py عبر job_queue، ومن إعادة التقييم الفورية في
    modules/residency/models.py. يُرجِع **من انتقل فعلياً** إلى
    EXPIRY_PENDING (قائمة قواميس خفيفة لا كائنات ORM — تبقى صالحة بعد
    إغلاق الجلسة، وتُمرَّر عبر asyncio.to_thread من app.py بأمان).

    ⚠️ **الشرط كان `reminder_date` وحده**، فبقيت في «الحالات النشطة» حالات
    انتهت إقاماتها فعلاً وتعرض «⛔ متأخّر ٢٢ يوماً» — لأن الشارة تقيس
    `expiry_date` بينما النقل يقرأ `reminder_date`. حقلان مختلفان يقودان
    شاشةً واحدة. أُثبِتت ثلاث فجوات عملياً:
      • تنبيه فارغ  + انتهاء ماضٍ ⇒ لا تنتقل أبداً.
      • تنبيه NULL  + انتهاء ماضٍ ⇒ لا تنتقل (`NULL != ''` يساوي NULL في
        SQL فيسقط الصفّ من الفلتر صامتاً).
      • تنبيه مستقبلي + انتهاء ماضٍ ⇒ لا تنتقل (إدخال غير متّسق).

    القاعدة الآن: ينتقل من **حلّ تنبيهه أو انتهت إقامته** — فإقامة منتهية
    هي «معلّق انتهاء» بحكم التعريف مهما كان التنبيه.
    """
    from sqlalchemy import or_, and_
    from db.session import get_db
    from db.models import ResidencyPerson, ResidencyStatusLog
    from modules.residency.constants import STATUS_ACTIVE, STATUS_EXPIRY_PENDING

    today_iso = date.today().isoformat()
    moved: list[dict] = []

    def _due(col):
        return and_(col.isnot(None), col != "", col <= today_iso)

    with get_db() as db:
        due = (
            db.query(ResidencyPerson)
            .filter(
                ResidencyPerson.status == STATUS_ACTIVE,
                # ✈️ المجمَّد لا يُحرَّك: من سافر لا تُتابَع إقامته، وتحريكه
                # يُعيده لقوائم العمل من الباب الخلفي رغم تجميده.
                ResidencyPerson.frozen_at.is_(None),
                or_(_due(ResidencyPerson.reminder_date),
                    _due(ResidencyPerson.expiry_date)),
            )
            .all()
        )
        for person in due:
            old = person.status
            person.status = STATUS_EXPIRY_PENDING
            db.add(ResidencyStatusLog(
                person_id=person.id, old_status=old, new_status=STATUS_EXPIRY_PENDING,
                performed_by=None,
            ))
            # ✅ قاموس خفيف لا كائن ORM — يُلتقَط الآن والجلسة مفتوحة، يبقى
            # صالحاً بعد إغلاقها (يعبر asyncio.to_thread لاحقاً بأمان).
            moved.append({
                "name": person.name,
                "is_companion": person.parent_id is not None,
                "reminder_date": person.reminder_date or "",
                "expiry_date": person.expiry_date or "",
            })

    logger.info(f"[residency.status] expiry check: {len(moved)} person(s) → EXPIRY_PENDING")
    return moved


def _person_reason(p: dict, today_iso: str) -> str:
    """أيّ تاريخ استحقّ — يقرّر السبب المعروض."""
    if p["reminder_date"] and p["reminder_date"] <= today_iso:
        return f"🔔 تاريخ التنبيه: {p['reminder_date']}"
    if p["expiry_date"] and p["expiry_date"] <= today_iso:
        return f"⏳ تاريخ انتهاء الإقامة: {p['expiry_date']}"
    return "مستحقّ"  # احتياط نظري — الفلتر لا يسمح بعنصر بلا سبب استحقاق


def _person_block(index: int, p: dict, today_iso: str) -> str:
    role = "🧑‍🤝‍🧑 مرافق" if p["is_companion"] else "👤 مريض"
    return f"{index}. {role}: {_safe(p['name'])}\n   {_person_reason(p, today_iso)}"


def build_expiry_alert_messages(people: list[dict]) -> list[str]:
    """رسالة أو أكثر لتنبيه مجموعة الإقامة — دالّة نقية بلا Telegram/DB،
    نفس نمط notification_service.py::build_reminder_messages (تقسيم بحدّ
    العنصر لا منتصفه، ≤3500 حرف هامش أمان تحت حدّ تليجرام ٤٠٩٦)."""
    if not people:
        return []

    today_iso = date.today().isoformat()
    header = [_DIV, "🔴 *حالات جديدة انتقلت إلى «معلّق انتهاء الإقامة»*"]
    blocks = [_person_block(i, p, today_iso) for i, p in enumerate(people, 1)]

    chunks: list[list[str]] = []
    cur: list[str] = []
    cur_len = 0
    for block in blocks:
        if cur and cur_len + len(block) > _MAX_CHARS:
            chunks.append(cur)
            cur, cur_len = [], 0
        cur.append(block)
        cur_len += len(block) + 2
    if cur:
        chunks.append(cur)

    out = []
    for ci, chunk in enumerate(chunks):
        lines = list(header)
        if len(chunks) > 1:
            lines.append(f"الجزء {ci + 1} من {len(chunks)}")
        lines.append(f"العدد: `{len(people)}`")
        lines.append("")
        lines.extend(chunk)
        out.append("\n".join(lines))
    return out


async def _send_expiry_text(bot, chat_id, text: str) -> bool:
    """Markdown ثم نصّ عادي عند الرفض — نفس احتياط notification_service.py."""
    from telegram.constants import ParseMode
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
        return True
    except Exception as first:
        try:
            await bot.send_message(chat_id=chat_id, text=text)
            logger.warning(f"⚠️ Markdown رُفض لتنبيه الإقامة ({first}) — وصل نصّاً عادياً")
            return True
        except Exception as second:
            logger.error(f"❌ Failed to send residency expiry alert: {first} / {second}")
            return False


async def send_residency_expiry_alert(application) -> int:
    """يُستدعى **فقط** من مهمّتَي app.py (الجدولة اليومية ٩:٠٠ + تعويض
    الإقلاع) — انظر التنبيه أعلى الملف. يُرجِع عدد من أُرسِل عنهم تنبيه
    (قد يكون صفراً، وحينها لا رسالة إطلاقاً — قناة مجموعة لا صندوق أدمن
    خاص يستحقّ رسالة طمأنة يومية)."""
    import asyncio
    from config.settings import RESIDENCY_ISSUANCE_GROUP_ID

    moved = await asyncio.to_thread(run_daily_expiry_check)
    if not moved:
        return 0

    if not RESIDENCY_ISSUANCE_GROUP_ID:
        logger.warning("⚠️ [residency.status] RESIDENCY_ISSUANCE_GROUP_ID فارغ — تعذّر إرسال تنبيه الإقامة")
        return 0

    messages = build_expiry_alert_messages(moved)
    bot = application.bot
    for msg in messages:
        await _send_expiry_text(bot, RESIDENCY_ISSUANCE_GROUP_ID, msg)

    logger.info(
        f"✅ [residency.status] expiry alert sent to group: "
        f"{len(moved)} person(s), {len(messages)} message(s)."
    )
    return len(moved)

