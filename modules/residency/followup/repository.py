# modules/residency/followup/repository.py
# Read queries for the followup and pending-updates screens.

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from modules.residency.constants import (
    EXPIRING_SOON_DAYS, PASSPORT_EXPIRING_SOON_DAYS,
    TRACKABLE_STATUSES, COMPANION_PENDING_STATUSES,
)

logger = logging.getLogger(__name__)


@dataclass
class ExpiringEntry:
    profile_id:       int
    name:             str
    status:           str
    expiry_date:      str
    days_remaining:   int
    is_companion:     bool = False
    companion_id:     int  = 0
    companion_name:   str  = ""
    residency_number: str  = ""


@dataclass
class PendingEntry:
    profile_id:             int
    name:                   str
    pending_companion_count: int
    companions:             list[dict] = field(default_factory=list)


def get_expiring_soon() -> list[ExpiringEntry]:
    """
    Return profiles AND companions whose expiry_date is within EXPIRING_SOON_DAYS
    and whose status is active, expiring, or renewal_submitted.
    Ordered by days_remaining ASC (most urgent first).
    """
    from db.session import get_db
    from db.models import ResidencyProfile, ResidencyCompanion

    threshold = datetime.utcnow().date() + timedelta(days=EXPIRING_SOON_DAYS)
    today     = datetime.utcnow().date()

    results: list[ExpiringEntry] = []

    trackable_statuses = TRACKABLE_STATUSES

    with get_db() as db:
        profiles = (
            db.query(ResidencyProfile)
            .filter(
                ResidencyProfile.status.in_(trackable_statuses),
                ResidencyProfile.expiry_date != "",
                ResidencyProfile.expiry_date.isnot(None),
            )
            .all()
        )
        for p in profiles:
            try:
                exp   = datetime.strptime(p.expiry_date[:10], "%Y-%m-%d").date()
                delta = (exp - today).days
                if delta <= EXPIRING_SOON_DAYS:
                    results.append(ExpiringEntry(
                        profile_id=       p.id,
                        name=             p.name or "—",
                        status=           p.status or "active",
                        expiry_date=      p.expiry_date,
                        days_remaining=   delta,
                        residency_number= p.residency_number or "",
                    ))
            except Exception:
                pass

        companions = (
            db.query(ResidencyCompanion)
            .filter(
                ResidencyCompanion.status.in_(trackable_statuses),
                ResidencyCompanion.expiry_date != "",
                ResidencyCompanion.expiry_date.isnot(None),
            )
            .all()
        )
        for c in companions:
            # Resolve profile name
            profile = db.query(ResidencyProfile).filter(ResidencyProfile.id == c.profile_id).first()
            p_name  = profile.name if profile else "—"
            try:
                exp   = datetime.strptime(c.expiry_date[:10], "%Y-%m-%d").date()
                delta = (exp - today).days
                if delta <= EXPIRING_SOON_DAYS:
                    results.append(ExpiringEntry(
                        profile_id=       c.profile_id,
                        name=             p_name,
                        status=           c.status or "active",
                        expiry_date=      c.expiry_date,
                        days_remaining=   delta,
                        is_companion=     True,
                        companion_id=     c.id,
                        companion_name=   c.name or "—",
                        residency_number= c.residency_number or "",
                    ))
            except Exception:
                pass

    results.sort(key=lambda e: e.days_remaining)
    logger.debug(f"[residency.followup] get_expiring_soon → {len(results)} entries")
    return results


def get_passport_expiring_soon() -> list[ExpiringEntry]:
    """
    Return profiles AND companions whose **passport** expires within
    PASSPORT_EXPIRING_SOON_DAYS (6 months). Ordered by days_remaining ASC.

    ✅ يعيد استخدام ExpiringEntry نفسه، لكن `expiry_date` هنا يحمل تاريخ
    انتهاء **الجواز** لا الإقامة (نفس بنية العرض، مصدر مختلف).

    ملاحظة: يتجاهل من انتهى جوازه فعلاً (delta < 0) — تلك حالة متأخرة تحتاج
    إجراءً مختلفاً لا تنبيهاً مسبقاً، وإبقاؤها كان سيُغرق التنبيه اليومي
    بأسماء قديمة إلى الأبد. تنبيه الإقامة يُبقيها عمداً (سلوكه الأصلي).
    """
    from db.session import get_db
    from db.models import ResidencyProfile, ResidencyCompanion

    today = datetime.utcnow().date()
    results: list[ExpiringEntry] = []
    trackable_statuses = TRACKABLE_STATUSES

    def _delta(raw: str) -> int | None:
        try:
            return (datetime.strptime(raw[:10], "%Y-%m-%d").date() - today).days
        except Exception:
            return None

    with get_db() as db:
        for p in (
            db.query(ResidencyProfile)
            .filter(
                ResidencyProfile.status.in_(trackable_statuses),
                ResidencyProfile.passport_expiry != "",
                ResidencyProfile.passport_expiry.isnot(None),
            )
            .all()
        ):
            d = _delta(p.passport_expiry)
            if d is not None and 0 <= d <= PASSPORT_EXPIRING_SOON_DAYS:
                results.append(ExpiringEntry(
                    profile_id=       p.id,
                    name=             p.name or "—",
                    status=           p.status or "active",
                    expiry_date=      p.passport_expiry,
                    days_remaining=   d,
                    residency_number= p.residency_number or "",
                ))

        for c in (
            db.query(ResidencyCompanion)
            .filter(
                ResidencyCompanion.status.in_(trackable_statuses),
                ResidencyCompanion.passport_expiry != "",
                ResidencyCompanion.passport_expiry.isnot(None),
            )
            .all()
        ):
            d = _delta(c.passport_expiry)
            if d is None or not (0 <= d <= PASSPORT_EXPIRING_SOON_DAYS):
                continue
            profile = db.query(ResidencyProfile).filter(ResidencyProfile.id == c.profile_id).first()
            results.append(ExpiringEntry(
                profile_id=       c.profile_id,
                name=             profile.name if profile else "—",
                status=           c.status or "active",
                expiry_date=      c.passport_expiry,
                days_remaining=   d,
                is_companion=     True,
                companion_id=     c.id,
                companion_name=   c.name or "—",
                residency_number= c.residency_number or "",
            ))

    results.sort(key=lambda e: e.days_remaining)
    logger.debug(f"[residency.followup] get_passport_expiring_soon → {len(results)} entries")
    return results


def get_dependent_pending() -> list[PendingEntry]:
    """Return profiles with status='dependent_pending' (issued but companions still pending)."""
    from db.session import get_db
    from db.models import ResidencyProfile, ResidencyCompanion

    results: list[PendingEntry] = []
    with get_db() as db:
        profiles = (
            db.query(ResidencyProfile)
            .filter(ResidencyProfile.status == "dependent_pending")
            .order_by(ResidencyProfile.updated_at.asc())
            .all()
        )
        for p in profiles:
            pending_comps = (
                db.query(ResidencyCompanion)
                .filter(
                    ResidencyCompanion.profile_id == p.id,
                    ResidencyCompanion.status.in_(COMPANION_PENDING_STATUSES),
                )
                .all()
            )
            results.append(PendingEntry(
                profile_id=              p.id,
                name=                    p.name or "—",
                pending_companion_count= len(pending_comps),
                companions=              [
                    {"id": c.id, "name": c.name or "—", "status": c.status, "expiry_date": c.expiry_date}
                    for c in pending_comps
                ],
            ))

    logger.debug(f"[residency.followup] get_dependent_pending → {len(results)} entries")
    return results


def mark_renewal_submitted(profile_id: int, companion_id: int | None, performed_by: int | None) -> None:
    """Mark a profile (or companion) status as renewal_submitted."""
    from db.session import get_db
    from db.models import ResidencyProfile, ResidencyCompanion, ResidencyUpdate

    with get_db() as db:
        if companion_id:
            row = db.query(ResidencyCompanion).filter(ResidencyCompanion.id == companion_id).first()
        else:
            row = db.query(ResidencyProfile).filter(ResidencyProfile.id == profile_id).first()

        if row is None:
            logger.warning(f"[residency.followup] mark_renewal_submitted: not found  profile={profile_id}  companion={companion_id}")
            return

        old_status  = row.status
        row.status  = "renewal_submitted"

        update = ResidencyUpdate(
            profile_id=   profile_id,
            companion_id= companion_id,
            action_type=  "renewal_submitted",
            action_label= "تم التقديم للتجديد",
            old_status=   old_status,
            new_status=   "renewal_submitted",
            performed_by= performed_by,
        )
        db.add(update)

    logger.info(f"[residency.followup] renewal_submitted  profile={profile_id}  companion={companion_id}")
