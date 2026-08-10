# modules/residency/uploads/repository.py
# قراءات وكتابات وحدة «📤 الرفع والمتابعة».
#
# ⚠️ لا حالات مكتوبة يدوياً هنا: كل الانتقالات تُقرأ من `PAPERS_ADVANCE` في
# modules/residency/constants.py، والتراجع يُقرأ من سجل `ResidencyUpdate`
# التدقيقي. فلا يوجد جدول انتقالات ثانٍ يمكن أن ينحرف عن الشاشة.

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from modules.residency.constants import PAPERS_ADVANCE, PAPERS_IN_PROGRESS

logger = logging.getLogger(__name__)

# أنواع الأحداث التي تكتبها هذه الوحدة في السجل التدقيقي.
# التراجع يبحث عن آخر حدث من هذه الأنواع ليعرف الحالة السابقة.
_STAGE_ACTIONS = ("papers_submitted", "extension_received")


@dataclass
class PapersEntry:
    """صف واحد في شاشة متابعة أوراق المستشفى."""
    profile_id:       int
    name:             str
    status:           str
    expiry_date:      str
    days_remaining:   int | None
    companion_count:  int
    next_label:       str          # ما يُكتب على زر التقدّم
    next_status:      str | None   # None ⇒ الزر يفتح مسار الإصدار rnr:
    can_undo:         bool


def _days(raw: str | None) -> int | None:
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            d = datetime.strptime(str(raw)[:10], fmt).date()
            return (d - datetime.utcnow().date()).days
        except Exception:
            continue
    return None


def get_papers_entries(*, within_days: int = 60) -> list[PapersEntry]:
    """
    المرضى الذين تحتاج أوراقهم متابعة، مرتَّبين بالأعجل أولاً.

    يُدرَج المريض إذا:
      • دورته جارية فعلاً (`PAPERS_IN_PROGRESS`) — بغضّ النظر عن تاريخ
        الانتهاء، لأن ورقه عند المستشفى الآن ولا يصح أن يختفي من الشاشة، أو
      • اقترب انتهاء إقامته (خلال `within_days`) فحان بدء الدورة.

    النطاق 60 يوماً لا 30 عمداً: بدء الرفع يسبق الانتهاء بمدة، فلو ساوينا
    عتبة «المتابعة» (30) لظهر المريض في شاشة الرفع بعد فوات أوان البدء.
    """
    from db.session import get_db
    from db.models import ResidencyProfile, ResidencyCompanion, ResidencyUpdate

    out: list[PapersEntry] = []
    with get_db() as db:
        profiles = db.query(ResidencyProfile).all()

        # الملفات التي لها حدث مرحلة سابق ⇒ يمكن التراجع عنها
        undoable = {
            r.profile_id
            for r in db.query(ResidencyUpdate)
            .filter(ResidencyUpdate.action_type.in_(_STAGE_ACTIONS))
            .all()
        }

        for p in profiles:
            status = p.status or "active"
            if status == "inactive":
                continue
            d = _days(p.expiry_date)
            in_progress = status in PAPERS_IN_PROGRESS
            due_soon    = d is not None and d <= within_days
            if not (in_progress or due_soon):
                continue

            label, nxt = PAPERS_ADVANCE.get(status, (None, None))
            if label is None:
                continue

            comp_count = (
                db.query(ResidencyCompanion)
                .filter(ResidencyCompanion.profile_id == p.id)
                .count()
            )
            out.append(PapersEntry(
                profile_id=      p.id,
                name=            p.name or "—",
                status=          status,
                expiry_date=     p.expiry_date or "",
                days_remaining=  d,
                companion_count= comp_count,
                next_label=      label,
                next_status=     nxt,
                can_undo=        p.id in undoable,
            ))

    # من بلا تاريخ يُدفع للأسفل بدل أن يتصدّر بقيمة صفرية مضلِّلة
    out.sort(key=lambda e: (e.days_remaining is None, e.days_remaining or 0))
    logger.debug(f"[residency.uploads] get_papers_entries → {len(out)}")
    return out


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


def undo_papers_stage(*, profile_id: int, performed_by: int | None) -> tuple[bool, str, str]:
    """
    يرجع المريض ومرافقيه مرحلةً واحدة للخلف.

    الحالة السابقة تُقرأ من `old_status` في آخر حدث مرحلة بالسجل التدقيقي —
    فلا حاجة لعمود «الحالة السابقة» يكرّر ما يخزّنه السجل أصلاً.

    موجود لأن التقدّم بضغطة واحدة داخل قائمة يجعل الضغط على المريض المجاور
    خطأً حتمياً، وبلا تراجع لا يمكن تصحيحه إلا يدوياً في قاعدة البيانات.

    Returns: (نجح, اسم المريض, الحالة المُستعادة)
    """
    from db.session import get_db
    from db.models import ResidencyProfile, ResidencyCompanion, ResidencyUpdate
    from modules.residency.views import format_status

    with get_db() as db:
        p = db.query(ResidencyProfile).filter(ResidencyProfile.id == profile_id).first()
        if p is None:
            return False, "", ""

        last = (
            db.query(ResidencyUpdate)
            .filter(
                ResidencyUpdate.profile_id == profile_id,
                ResidencyUpdate.companion_id.is_(None),
                ResidencyUpdate.action_type.in_(_STAGE_ACTIONS),
            )
            .order_by(ResidencyUpdate.id.desc())
            .first()
        )
        if last is None or not last.old_status:
            return False, p.name or "", p.status or ""

        cur, prev = p.status or "", last.old_status
        p.status = prev
        db.add(ResidencyUpdate(
            profile_id=  profile_id,
            action_type= "stage_undo",
            action_label=f"تراجع عن: {format_status(cur)}",
            old_status=  cur,
            new_status=  prev,
            performed_by=performed_by,
        ))

        for c in db.query(ResidencyCompanion).filter(
            ResidencyCompanion.profile_id == profile_id
        ).all():
            if (c.status or "") == cur:
                c.status = prev

        # يُستهلَك الحدث حتى لا يتراجع الضغط التالي عن نفس الخطوة مرتين
        db.delete(last)
        name = p.name or ""

    logger.info(f"[residency.uploads] undo  profile={profile_id}  {cur} → {prev}")
    return True, name, prev


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


def get_hub_counts() -> dict[str, int]:
    """أعداد شاشة الوحدة الرئيسية — استعلام واحد لكل مجموعة."""
    from db.session import get_db
    from db.models import ResidencyProfile
    from modules.residency.followup.repository import (
        get_expiring_soon, get_passport_expiring_soon, get_dependent_pending,
    )

    with get_db() as db:
        submitted = db.query(ResidencyProfile).filter(
            ResidencyProfile.status == "renewal_submitted").count()
        received = db.query(ResidencyProfile).filter(
            ResidencyProfile.status == "extension_received").count()

    return {
        "expiring":  len(get_expiring_soon()),
        "passports": len(get_passport_expiring_soon()),
        "pending":   len(get_dependent_pending()),
        "submitted": submitted,
        "received":  received,
    }
