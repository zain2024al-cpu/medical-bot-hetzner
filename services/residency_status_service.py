# services/residency_status_service.py
# الانتقال التلقائي اليومي: ACTIVE → EXPIRY_PENDING عند وصول تاريخ
# التنبيه اليدوي لكل شخص. كتابة فقط على قاعدة البيانات — بلا أي رسالة
# تلغرام (التنبيه يتحقق داخل البوت فقط عبر ظهور العدّاد/القائمة).

import logging
from datetime import date

logger = logging.getLogger(__name__)


def run_daily_expiry_check() -> int:
    """يُستدعى من app.py عبر job_queue.run_daily. يُرجع عدد الأشخاص
    الذين انتقلوا إلى EXPIRY_PENDING."""
    from db.session import get_db
    from db.models import ResidencyPerson, ResidencyStatusLog
    from modules.residency.constants import STATUS_ACTIVE, STATUS_EXPIRY_PENDING

    today_iso = date.today().isoformat()
    count = 0
    with get_db() as db:
        due = (
            db.query(ResidencyPerson)
            .filter(
                ResidencyPerson.status == STATUS_ACTIVE,
                ResidencyPerson.reminder_date != "",
                ResidencyPerson.reminder_date <= today_iso,
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

    logger.info(f"[residency.status] daily expiry check: {count} person(s) → EXPIRY_PENDING")
    return count
