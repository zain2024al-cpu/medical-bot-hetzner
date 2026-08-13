# modules/residency/uploads/repository.py
# منطق ملحق بملف مريض واحد: حفظ فورم C، حفظ الصورة الشخصية.
#
# ⚠️ `get_papers_entries` وَ`get_hub_counts` (شاشتا القائمة القديمتان)
# حُذفتا مع شاشة «📤 الرفع والمتابعة» — كل فعل هنا يُستدعى مباشرةً بمعرّف
# ملف من `build_profile_detail`، فلا حاجة لاستعلام قائمة يغذّيها.

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


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


def save_companion_photo(*, profile_id: int, companion_id: int, file_id: str, performed_by: int | None) -> str:
    """يحفظ الصورة الشخصية لمرافق ويسجّلها في السجل. يعيد اسم المرافق."""
    from db.session import get_db
    from db.models import ResidencyCompanion, ResidencyUpdate

    with get_db() as db:
        c = db.query(ResidencyCompanion).filter(ResidencyCompanion.id == companion_id).first()
        if c is None:
            return ""
        c.photo_file_id = file_id
        db.add(ResidencyUpdate(
            profile_id=   profile_id,
            companion_id= companion_id,
            action_type=  "photo_uploaded",
            action_label= f"تم رفع الصورة الشخصية — {c.name}",
            old_status=   c.status or "",
            new_status=   c.status or "",
            residency_file_id=file_id,
            performed_by= performed_by,
        ))
        name = c.name or ""

    logger.info(f"[residency.uploads] companion photo saved  profile={profile_id}  companion={companion_id}")
    return name

