# modules/residency/renewal/models.py
# Write operations for issuance/renewal.

from __future__ import annotations
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SavedRenewal:
    profile_id:   int
    profile_name: str


def save_renewal(
    *,
    profile_id:           int,
    new_expiry_date:      str,
    new_residency_number: str  = "",
    document_file_id:     str,
    notes:                str,
    completed_companions: list[dict],   # [{id, new_expiry, file_id, skipped, residency_number}]
    performed_by:         int | None = None,
) -> SavedRenewal:
    """
    Persist a residency renewal:
    - Update ResidencyProfile: status, expiry_date, latest_residency_file_id
    - Update each companion accordingly
    - Append ResidencyUpdate rows
    - Set status to 'issued' if all companions resolved,
      or 'dependent_pending' if any companion was skipped.
    """
    from db.session import get_db
    from db.models import ResidencyProfile, ResidencyCompanion, ResidencyUpdate

    with get_db() as db:
        profile = db.query(ResidencyProfile).filter(ResidencyProfile.id == profile_id).first()
        if profile is None:
            raise ValueError(f"ResidencyProfile id={profile_id} not found")

        profile_name    = profile.name or "—"
        old_status      = profile.status
        old_expiry      = profile.expiry_date

        has_pending_companion = any(c.get("skipped") for c in completed_companions)
        new_status = "dependent_pending" if has_pending_companion else "issued"

        profile.status                   = new_status
        profile.expiry_date              = new_expiry_date
        if new_residency_number:
            profile.residency_number = new_residency_number
        if document_file_id:
            profile.latest_residency_file_id = document_file_id

        # Build action label that includes the residency number for history display
        _res_num_tag = f" رقم {new_residency_number}" if new_residency_number else ""

        # Main profile update log
        db.add(ResidencyUpdate(
            profile_id=       profile_id,
            action_type=      "issued",
            action_label=     f"تم إصدار الإقامة{_res_num_tag}",
            old_status=       old_status,
            new_status=       new_status,
            old_expiry_date=  old_expiry,
            new_expiry_date=  new_expiry_date,
            residency_file_id=document_file_id,
            notes=            notes,
            performed_by=     performed_by,
        ))

        # Process companions
        for c_data in completed_companions:
            c_id     = c_data.get("id")
            skipped  = c_data.get("skipped", False)
            c_expiry = c_data.get("new_expiry", "")
            c_fid    = c_data.get("file_id", "")

            comp = db.query(ResidencyCompanion).filter(ResidencyCompanion.id == c_id).first()
            if comp is None:
                continue

            old_c_status    = comp.status
            c_residency_num = c_data.get("residency_number", "")
            if skipped:
                # Leave companion status as-is; dependent_pending already set on profile
                db.add(ResidencyUpdate(
                    profile_id=   profile_id,
                    companion_id= c_id,
                    action_type=  "companion_skipped",
                    action_label= f"تخطي مؤقت — {comp.name}",
                    old_status=   old_c_status,
                    new_status=   old_c_status,
                    performed_by= performed_by,
                ))
            else:
                comp.status      = "issued"
                comp.expiry_date = c_expiry
                if c_residency_num:
                    comp.residency_number = c_residency_num
                if c_fid:
                    comp.latest_residency_file_id = c_fid
                _c_num_tag = f" رقم {c_residency_num}" if c_residency_num else ""
                db.add(ResidencyUpdate(
                    profile_id=       profile_id,
                    companion_id=     c_id,
                    action_type=      "companion_issued",
                    action_label=     f"تم إصدار إقامة{_c_num_tag} — {comp.name}",
                    old_status=       old_c_status,
                    new_status=       "issued",
                    new_expiry_date=  c_expiry,
                    residency_file_id=c_fid,
                    performed_by=     performed_by,
                ))

    logger.info(
        f"[residency.renewal] saved renewal  profile_id={profile_id}"
        f"  new_status={new_status}  companions={len(completed_companions)}"
    )
    return SavedRenewal(profile_id=profile_id, profile_name=profile_name)
