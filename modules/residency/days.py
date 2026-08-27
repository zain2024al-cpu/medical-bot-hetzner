# modules/residency/days.py
# حساب «الأيام» المعروضة بجانب كل حالة إقامة — مصدر واحد تستدعيه كل
# الشاشات (قوائم الحالات، تفاصيل الطلب، وأي شاشة تُضاف لاحقاً).
#
# ⚠️ الرقم ليس واحداً لكل الحالات، لأن السؤال يختلف:
#   • حالة لها تاريخ انتهاء (نشطة / معلّق انتهاء / تمديد مُصدَر) ⇒ السؤال
#     "كم بقي؟" — فيُعرَض المتبقّي، أو التأخّر إن مضى التاريخ.
#   • حالة انتظار (معلّق من الوصول / تم التقديم / الحالات السابقة) ⇒
#     السؤال "منذ متى وهي واقفة؟" — فتُعرَض مدة البقاء في الحالة.
# عرض "المتبقّي" لحالة بلا تاريخ انتهاء يعطي "—" بلا فائدة، وعرض "منذ"
# لإقامة توشك على الانتهاء يُخفي الخطر. لذلك يُختار الرقم حسب الحالة.

import logging
from datetime import date, datetime

from modules.residency.constants import (
    STATUS_ACTIVE, STATUS_EXPIRY_PENDING, STATUS_ISSUED,
)

logger = logging.getLogger(__name__)

# الحالات التي يُقاس فيها القرب من انتهاء الإقامة
_EXPIRY_DRIVEN = {STATUS_ACTIVE, STATUS_EXPIRY_PENDING, STATUS_ISSUED}

# التقويم في هذه الوحدة يكتب ISO دائماً (`f"{y:04d}-{mo:02d}-{d:02d}"`)،
# لكن `%d/%m/%Y` مقبولة أيضاً تحسّباً لأي بيانات قديمة أو مصدر آخر.
_FORMATS = ("%Y-%m-%d", "%d/%m/%Y")


def parse_date(value) -> date | None:
    """نصّ تاريخ ⇒ `date`، أو None إن كان فارغاً/غير صالح."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in _FORMATS:
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def _plural(n: int) -> str:
    """صيغة عربية سليمة للعدد: يوم / يومان / أيام."""
    if n == 1:
        return "يوم"
    if n == 2:
        return "يومان"
    if 3 <= n <= 10:
        return "أيام"
    return "يوماً"


def days_until(value, *, today: date | None = None) -> int | None:
    """عدد الأيام حتى التاريخ (سالب إن مضى)، أو None إن تعذّر."""
    d = parse_date(value)
    if d is None:
        return None
    return (d - (today or date.today())).days


def days_since(value, *, today: date | None = None) -> int | None:
    """عدد الأيام منذ التاريخ (0 إن كان اليوم)، أو None إن تعذّر."""
    d = parse_date(value)
    if d is None:
        return None
    return max(0, ((today or date.today()) - d).days)


def badge(person, since=None, *, today: date | None = None) -> str:
    """الشارة القصيرة المعروضة بجانب الاسم — "" إن لا رقم متاحاً.

    person — أي كائن فيه `status` و`expiry_date`.
    since  — تاريخ دخول الحالة الحالية (من سجلّ التحوّلات)؛ اختياري.
    """
    try:
        status = getattr(person, "status", "") or ""

        if status in _EXPIRY_DRIVEN:
            left = days_until(getattr(person, "expiry_date", ""), today=today)
            if left is not None:
                if left > 0:
                    return f"متبقٍّ {left} {_plural(left)}"
                if left == 0:
                    return "⚠️ ينتهي اليوم"
                over = abs(left)
                return f"⛔ متأخّر {over} {_plural(over)}"
            # بلا تاريخ انتهاء ⇒ يسقط لمدة البقاء بدل عرض "—" بلا معنى

        waited = days_since(since, today=today)
        if waited is not None:
            return "منذ اليوم" if waited == 0 else f"منذ {waited} {_plural(waited)}"
        return ""
    except Exception:
        # شارة عرض فقط — لا يجوز أن تُسقِط الشاشة
        logger.debug("[residency.days] تعذّر حساب الشارة", exc_info=True)
        return ""


def family_badge(family, since_map: dict | None = None,
                 *, today: date | None = None) -> str:
    """شارة العائلة في القوائم — **أشدّ أفرادها إلحاحاً**.

    ⚠️ عرض شارة الجذر وحده يُخفي مرافقاً إقامته تنتهي قبله؛ والعائلة تُفتَح
    بضغطة واحدة فالأولوية يجب أن تُقاس على أسوأ فرد فيها.
    """
    since_map = since_map or {}
    people = [family.root] + list(getattr(family, "companions", []) or [])

    worst_person, worst_key = None, None
    for p in people:
        if (getattr(p, "status", "") in _EXPIRY_DRIVEN
                and days_until(getattr(p, "expiry_date", ""), today=today) is not None):
            key = days_until(p.expiry_date, today=today)     # الأصغر = الأعجل
        else:
            waited = days_since(since_map.get(p.id), today=today)
            # الانتظار يأتي بعد كل ما له تاريخ انتهاء، والأطول انتظاراً أولاً
            key = 10_000 - (waited if waited is not None else 0)
        if worst_key is None or key < worst_key:
            worst_person, worst_key = p, key

    if worst_person is None:
        return ""
    return badge(worst_person, since_map.get(worst_person.id), today=today)
