# modules/residency/profiles/repository.py
# Read queries for ResidencyProfile and ResidencyCompanion.

from __future__ import annotations
import logging
from dataclasses import dataclass, field

from modules.residency.constants import PROFILES_PAGE_SIZE

logger = logging.getLogger(__name__)


@dataclass
class ProfileRow:
    id:               int
    name:             str
    status:           str
    expiry_date:      str
    residency_number: str
    passport_file_id: str
    visa_file_id:     str
    latest_residency_file_id: str
    # ✅ فورم C — استمارة واحدة للعائلة، تُرفع من وحدة «الرفع والمتابعة»
    form_c_file_id:   str
    passport_expiry:  str
    notes:            str
    source:           str
    companion_count:  int = 0
    # ✅ الصورة الشخصية — مرفق اختياري من «📎 إضافة مرفق» في ملف المريض.
    # لها قيمة افتراضية حتى لا ينكسر أي مُنشئ قائم لا يمرّرها.
    photo_file_id:    str = ""
    tickets_file_id:  str = ""


@dataclass
class CompanionRow:
    id:               int
    profile_id:       int
    name:             str
    status:           str
    expiry_date:      str
    residency_number: str
    passport_file_id: str
    visa_file_id:     str
    latest_residency_file_id: str
    photo_file_id:    str = ""
    tickets_file_id:  str = ""


@dataclass
class MissingItemRow:
    id:          int
    profile_id:  int
    description: str
    status:      str
    file_id:     str
    created_at:  str


def get_pending_missing_items(profile_id: int) -> list[MissingItemRow]:
    """الطلبات الناقصة غير المُغلَقة لملف واحد — تُعرض على ملف المريض."""
    from db.session import get_db
    from db.models import ResidencyMissingItem

    with get_db() as db:
        rows = (
            db.query(ResidencyMissingItem)
            .filter(
                ResidencyMissingItem.profile_id == profile_id,
                ResidencyMissingItem.status == "pending",
            )
            .order_by(ResidencyMissingItem.created_at.asc())
            .all()
        )
        return [
            MissingItemRow(
                id=r.id, profile_id=r.profile_id, description=r.description or "",
                status=r.status or "pending", file_id=r.file_id or "",
                created_at=r.created_at.isoformat() if r.created_at else "",
            )
            for r in rows
        ]


def get_profiles_page(page: int = 0) -> tuple[list[ProfileRow], int]:
    """
    Return (profiles_for_page, total_count).
    Profiles are ordered by created_at DESC.
    """
    from sqlalchemy import or_
    from db.session import get_db
    from db.models import ResidencyProfile, ResidencyCompanion

    # ✅ مصدر الأسماء الوحيد لهذه القائمة هو الواصلون — الإضافة اليدوية
    # (source="manual") مستبعَدة صراحةً (قرار المستخدم: لا تُجلب أسماء
    # الإقامة من الأدمن). NULL يُعامَل كـ"arrivals" مطابقةً للقيمة الافتراضية
    # في db/models.py، فلا تختفي صفوف قديمة سابقة على العمود بالخطأ.
    _arrivals_only = or_(ResidencyProfile.source != "manual", ResidencyProfile.source.is_(None))

    offset = page * PROFILES_PAGE_SIZE
    with get_db() as db:
        total = db.query(ResidencyProfile).filter(_arrivals_only).count()
        rows = (
            db.query(ResidencyProfile)
            .filter(_arrivals_only)
            .order_by(ResidencyProfile.created_at.desc())
            .offset(offset)
            .limit(PROFILES_PAGE_SIZE)
            .all()
        )
        result = []
        for r in rows:
            comp_count = (
                db.query(ResidencyCompanion)
                .filter(ResidencyCompanion.profile_id == r.id)
                .count()
            )
            result.append(ProfileRow(
                id=r.id, name=r.name or "—", status=r.status or "active",
                expiry_date=r.expiry_date or "", residency_number=r.residency_number or "",
                passport_file_id=r.passport_file_id or "",
                visa_file_id=r.visa_file_id or "",
                latest_residency_file_id=r.latest_residency_file_id or "",
                photo_file_id=getattr(r, "photo_file_id", "") or "",
                tickets_file_id=getattr(r, "tickets_file_id", "") or "",
                form_c_file_id=r.form_c_file_id or "",
                passport_expiry=r.passport_expiry or "",
                notes=r.notes or "", source=r.source or "arrivals",
                companion_count=comp_count,
            ))
    logger.debug(f"[residency.repository] page={page}  rows={len(result)}  total={total}")
    return result, total


def get_profile_by_id(profile_id: int) -> ProfileRow | None:
    """Return a single profile, or None if not found."""
    from db.session import get_db
    from db.models import ResidencyProfile, ResidencyCompanion

    with get_db() as db:
        r = db.query(ResidencyProfile).filter(ResidencyProfile.id == profile_id).first()
        if r is None:
            return None
        comp_count = (
            db.query(ResidencyCompanion)
            .filter(ResidencyCompanion.profile_id == profile_id)
            .count()
        )
        return ProfileRow(
            id=r.id, name=r.name or "—", status=r.status or "active",
            expiry_date=r.expiry_date or "", residency_number=r.residency_number or "",
            passport_file_id=r.passport_file_id or "",
            visa_file_id=r.visa_file_id or "",
            latest_residency_file_id=r.latest_residency_file_id or "",
            photo_file_id=getattr(r, "photo_file_id", "") or "",
            tickets_file_id=getattr(r, "tickets_file_id", "") or "",
            form_c_file_id=r.form_c_file_id or "",
            passport_expiry=r.passport_expiry or "",
            notes=r.notes or "", source=r.source or "arrivals",
            companion_count=comp_count,
        )


def get_companions_for_profile(profile_id: int) -> list[CompanionRow]:
    from db.session import get_db
    from db.models import ResidencyCompanion

    with get_db() as db:
        rows = (
            db.query(ResidencyCompanion)
            .filter(ResidencyCompanion.profile_id == profile_id)
            .order_by(ResidencyCompanion.id.asc())
            .all()
        )
        return [
            CompanionRow(
                id=r.id, profile_id=r.profile_id, name=r.name or "—",
                status=r.status or "active", expiry_date=r.expiry_date or "",
                residency_number=r.residency_number or "",
                passport_file_id=r.passport_file_id or "",
                visa_file_id=r.visa_file_id or "",
                latest_residency_file_id=r.latest_residency_file_id or "",
                photo_file_id=getattr(r, "photo_file_id", "") or "",
                tickets_file_id=getattr(r, "tickets_file_id", "") or "",
            )
            for r in rows
        ]


def search_profiles(query: str) -> list[ProfileRow]:
    """Simple name-contains search. Returns up to 20 matches."""
    from sqlalchemy import or_
    from db.session import get_db
    from db.models import ResidencyProfile

    q = f"%{query.strip()}%"
    with get_db() as db:
        rows = (
            db.query(ResidencyProfile)
            .filter(
                ResidencyProfile.name.ilike(q),
                # ✅ نفس استبعاد الإضافة اليدوية المطبَّق في get_profiles_page —
                # البحث بوابة أخرى لنفس القائمة، فيجب أن يطابق نطاقها.
                or_(ResidencyProfile.source != "manual", ResidencyProfile.source.is_(None)),
            )
            .order_by(ResidencyProfile.created_at.desc())
            .limit(20)
            .all()
        )
        return [
            ProfileRow(
                id=r.id, name=r.name or "—", status=r.status or "active",
                expiry_date=r.expiry_date or "", residency_number=r.residency_number or "",
                passport_file_id=r.passport_file_id or "",
                visa_file_id=r.visa_file_id or "",
                latest_residency_file_id=r.latest_residency_file_id or "",
                photo_file_id=getattr(r, "photo_file_id", "") or "",
                tickets_file_id=getattr(r, "tickets_file_id", "") or "",
                form_c_file_id=r.form_c_file_id or "",
                passport_expiry=r.passport_expiry or "",
                notes=r.notes or "", source=r.source or "arrivals",
                companion_count=0,
            )
            for r in rows
        ]
