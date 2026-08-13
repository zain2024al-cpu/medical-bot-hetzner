# modules/residency/uploads/repository.py
# منطق ملحق بملف مريض واحد: تقدّم مرحلة الأوراق، حفظ فورم C،
# حفظ الصورة الشخصية.
#
# ⚠️ لا حالات مكتوبة يدوياً هنا: كل الانتقالات تُقرأ من `PAPERS_ADVANCE` في
# modules/residency/constants.py. فلا يوجد جدول انتقالات ثانٍ يمكن أن
# ينحرف عن الشاشة.
#
# ⚠️ `get_papers_entries` وَ`get_hub_counts` (شاشتا القائمة القديمتان)
# حُذفتا مع شاشة «📤 الرفع والمتابعة» — كل فعل هنا يُستدعى مباشرةً بمعرّف
# ملف من `build_profile_detail`، فلا حاجة لاستعلام قائمة يغذّيها.

from __future__ import annotations

import logging

from modules.residency.constants import PAPERS_ADVANCE

logger = logging.getLogger(__name__)

def advance_papers_stage(*, profile_id: int, performed_by: int | None) -> tuple[bool, str, str]:
    """
    ينقل المريض **وكل مرافقيه** للمرحلة التالية بضغطة واحدة.

    المرافقون يتحركون مع المريض لأن أوراق المستشفى تُرفع وتُستلم للعائلة
    دفعةً واحدة عملياً (قرار المستخدم) — وإفرادهم كان سيعني ضغطات مكرَّرة
    يومياً بلا فائدة.

    Returns: (نجح, اسم المريض, الحالة الجديدة)
    """
    from db.session import get_db
    from db.models import ResidencyProfile, ResidencyCompanion, ResidencyUpdate
    from modules.residency.views import format_status

    with get_db() as db:
        p = db.query(ResidencyProfile).filter(ResidencyProfile.id == profile_id).first()
        if p is None:
            return False, "", ""

        old = p.status or "active"
        _, new = PAPERS_ADVANCE.get(old, (None, None))
        if new is None:
            # `extension_received` ⇒ الزر يفتح مسار rnr: لا ينقل حالة
            return False, p.name or "", old

        action = "papers_submitted" if new == "renewal_submitted" else "extension_received"
        label  = format_status(new)

        p.status = new
        db.add(ResidencyUpdate(
            profile_id=  profile_id,
            action_type= action,
            action_label=label,
            old_status=  old,
            new_status=  new,
            performed_by=performed_by,
        ))

        for c in db.query(ResidencyCompanion).filter(
            ResidencyCompanion.profile_id == profile_id
        ).all():
            c_old = c.status or "active"
            if c_old in ("inactive", new):
                continue
            c.status = new
            db.add(ResidencyUpdate(
                profile_id=  profile_id,
                companion_id=c.id,
                action_type= action,
                action_label=f"{label} — {c.name}",
                old_status=  c_old,
                new_status=  new,
                performed_by=performed_by,
            ))

        name = p.name or ""

    logger.info(f"[residency.uploads] advance  profile={profile_id}  {old} → {new}")
    return True, name, new


def save_form_c(*, profile_id: int, file_id: str, performed_by: int | None) -> str:
    """يحفظ فورم C للعائلة ويسجّله في السجل. يعيد اسم المريض."""
    from db.session import get_db
    from db.models import ResidencyProfile, ResidencyUpdate

    with get_db() as db:
        p = db.query(ResidencyProfile).filter(ResidencyProfile.id == profile_id).first()
        if p is None:
            return ""
        p.form_c_file_id = file_id
        db.add(ResidencyUpdate(
            profile_id=  profile_id,
            action_type= "form_c_uploaded",
            action_label="تم رفع فورم C",
            old_status=  p.status or "",
            new_status=  p.status or "",
            residency_file_id=file_id,
            performed_by=performed_by,
        ))
        name = p.name or ""

    logger.info(f"[residency.uploads] form C saved  profile={profile_id}")
    return name


def save_patient_photo(*, profile_id: int, file_id: str, performed_by: int | None) -> str:
    """يحفظ الصورة الشخصية للمريض ويسجّلها في السجل. يعيد اسم المريض."""
    from db.session import get_db
    from db.models import ResidencyProfile, ResidencyUpdate

    with get_db() as db:
        p = db.query(ResidencyProfile).filter(ResidencyProfile.id == profile_id).first()
        if p is None:
            return ""
        p.photo_file_id = file_id
        db.add(ResidencyUpdate(
            profile_id=  profile_id,
            action_type= "photo_uploaded",
            action_label="تم رفع الصورة الشخصية",
            old_status=  p.status or "",
            new_status=  p.status or "",
            residency_file_id=file_id,
            performed_by=performed_by,
        ))
        name = p.name or ""

    logger.info(f"[residency.uploads] photo saved  profile={profile_id}")
    return name

