# modules/residency/models.py
# عمليات الكتابة على res_profiles/res_companions — المرحلة الأولى فقط
# (ملف معلّق بانتظار الصورة الشخصية + تاريخ تنبيه يدوي).

import logging

logger = logging.getLogger(__name__)


def create_profiles_from_arrival(patients: list[dict], created_by: int | None = None) -> int:
    """
    ينشئ ResidencyProfile + ResidencyCompanion لكل مريض في دفعة وصول
    مؤكَّدة — نقطة الإنشاء الوحيدة لملفات الإقامة الآن (عند تأكيد
    "🛬 الوصول" فقط، لا قبله). `patients` بنفس شكل
    `ArrivalSession.completed_patients` (كل عنصر: name + companions).

    Fire-and-forget من arrivals/flow.py — فشلها لا يوقف نشر دفعة الوصول.
    """
    from db.session import get_db
    from db.models import ResidencyProfile, ResidencyCompanion

    count = 0
    with get_db() as db:
        for p in patients:
            name = p.get("name", "").strip()
            if not name:
                continue
            profile = ResidencyProfile(name=name, created_by=created_by)
            db.add(profile)
            db.flush()
            for c in p.get("companions", []):
                cname = (c.get("name") or "").strip()
                if cname:
                    db.add(ResidencyCompanion(profile_id=profile.id, name=cname))
            count += 1

    logger.info(f"[residency] create_profiles_from_arrival: {count} profile(s) created")
    return count


def set_reminder_date(profile_id: int, date_iso: str) -> bool:
    """يضبط تاريخ التنبيه اليدوي ويُفعِّل التذكير اليومي بدءاً منه."""
    from db.session import get_db
    from db.models import ResidencyProfile

    with get_db() as db:
        profile = db.query(ResidencyProfile).filter_by(id=profile_id).first()
        if not profile:
            return False
        profile.reminder_date = date_iso
        profile.reminder_active = True
    logger.info(f"[residency] reminder_date set  profile_id={profile_id}  date={date_iso}")
    return True


def mark_submitted(profile_id: int, performed_by: int | None = None) -> bool:
    """✅ تم تقديم طلب الإقامة — يوقف التذكير ويُخفي الملف من المعلّقة."""
    from db.session import get_db
    from db.models import ResidencyProfile

    with get_db() as db:
        profile = db.query(ResidencyProfile).filter_by(id=profile_id).first()
        if not profile:
            return False
        profile.submitted = True
        profile.reminder_active = False
    logger.info(f"[residency] marked submitted  profile_id={profile_id}  by={performed_by}")
    return True


def save_photo(profile_id: int, file_id: str) -> bool:
    from db.session import get_db
    from db.models import ResidencyProfile

    with get_db() as db:
        profile = db.query(ResidencyProfile).filter_by(id=profile_id).first()
        if not profile:
            return False
        profile.photo_file_id = file_id
    logger.info(f"[residency] photo saved  profile_id={profile_id}")
    return True


def delete_stub_profile_by_name(name: str) -> int:
    """
    ✅ تُستدعى من services/patients_service.py::delete_patient() — تحذف
    أي ملف إقامة يتيم بلا صورة بعد (لم يُستكمَل بعد) مطابق للاسم عند
    حذف المريض المرتبط به. ملفات لها صورة مرفوعة بالفعل (تقدّم حقيقي)
    لا تُمَسّ إطلاقاً مهما كان.
    """
    from db.session import get_db
    from db.models import ResidencyProfile, ResidencyCompanion

    deleted = 0
    with get_db() as db:
        stale = (
            db.query(ResidencyProfile)
            .filter_by(name=name, submitted=False)
            .filter(
                (ResidencyProfile.photo_file_id == "") | (ResidencyProfile.photo_file_id.is_(None))
            )
            .all()
        )
        for profile in stale:
            db.query(ResidencyCompanion).filter_by(profile_id=profile.id).delete()
            db.delete(profile)
            deleted += 1
            logger.info(f"[residency] deleted orphaned pending profile #{profile.id} for: {name}")

    return deleted
