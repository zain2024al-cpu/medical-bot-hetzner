# modules/residency/renewal/repository.py
# Read helpers for the renewal flow.

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


def get_profile_with_companions(profile_id: int) -> tuple[dict | None, list[dict]]:
    """
    Return (profile_dict, companions_list) for a given profile_id.
    companions_list contains dicts with: id, name, status, expiry_date
    """
    from db.session import get_db
    from db.models import ResidencyProfile, ResidencyCompanion

    with get_db() as db:
        p = db.query(ResidencyProfile).filter(ResidencyProfile.id == profile_id).first()
        if p is None:
            return None, []

        profile_dict = {
            "id":          p.id,
            "name":        p.name or "—",
            "status":      p.status or "active",
            "expiry_date": p.expiry_date or "",
        }

        companions = (
            db.query(ResidencyCompanion)
            .filter(ResidencyCompanion.profile_id == profile_id)
            .order_by(ResidencyCompanion.id.asc())
            .all()
        )
        companion_list = [
            {
                "id":          c.id,
                "name":        c.name or "—",
                "status":      c.status or "active",
                "expiry_date": c.expiry_date or "",
            }
            for c in companions
        ]

    return profile_dict, companion_list
