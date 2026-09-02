# services/residency_status_service.py
# الانتقال التلقائي اليومي: ACTIVE → EXPIRY_PENDING عند وصول تاريخ
# التنبيه اليدوي لكل شخص. كتابة فقط على قاعدة البيانات — بلا أي رسالة
# تلغرام (التنبيه يتحقق داخل البوت فقط عبر ظهور العدّاد/القائمة).

import logging
from datetime import date

logger = logging.getLogger(__name__)

def run_daily_expiry_check() -> int:
    """يُستدعى من app.py عبر job_queue. يُرجِع عدد من انتقل إلى EXPIRY_PENDING.

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
    count = 0

    def _due(col):
        return and_(col.isnot(None), col != "", col <= today_iso)

    with get_db() as db:
        due = (
            db.query(ResidencyPerson)
            .filter(
                ResidencyPerson.status == STATUS_ACTIVE,
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
            count += 1

    logger.info(f"[residency.status] expiry check: {count} person(s) → EXPIRY_PENDING")
    return count

