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
    notes:            str
    source:           str
    companion_count:  int = 0


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


@dataclass
class HistoryRow:
    action_label:   str
    new_status:     str
    new_expiry_date:str
    created_at:     str
    companion_id:   int | None


def get_profiles_page(page: int = 0) -> tuple[list[ProfileRow], int]:
    """
    Return (profiles_for_page, total_count).
    Profiles are ordered by created_at DESC.
    """
    from db.session import get_db
    from db.models import ResidencyProfile, ResidencyCompanion

    offset = page * PROFILES_PAGE_SIZE
    with get_db() as db:
        total = db.query(ResidencyProfile).count()
        rows = (
            db.query(ResidencyProfile)
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
            )
            for r in rows
        ]


def get_history_for_profile(profile_id: int, limit: int = 10) -> list[HistoryRow]:
    from db.session import get_db
    from db.models import ResidencyUpdate

    with get_db() as db:
        rows = (
            db.query(ResidencyUpdate)
            .filter(ResidencyUpdate.profile_id == profile_id)
            .order_by(ResidencyUpdate.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            HistoryRow(
                action_label=    r.action_label or r.action_type,
                new_status=      r.new_status or "",
                new_expiry_date= r.new_expiry_date or "",
                created_at=      r.created_at.isoformat() if r.created_at else "",
                companion_id=    r.companion_id,
            )
            for r in rows
        ]


def search_profiles(query: str) -> list[ProfileRow]:
    """Simple name-contains search. Returns up to 20 matches."""
    from db.session import get_db
    from db.models import ResidencyProfile

    q = f"%{query.strip()}%"
    with get_db() as db:
        rows = (
            db.query(ResidencyProfile)
            .filter(ResidencyProfile.name.ilike(q))
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
                notes=r.notes or "", source=r.source or "arrivals",
                companion_count=0,
            )
            for r in rows
        ]
