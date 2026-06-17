# modules/residency/profiles/models.py
# Write operations for ResidencyProfile and ResidencyCompanion.
# Also provides create_profiles_from_arrival_batch() — the auto-creation hook.

from __future__ import annotations
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def update_profile_expiry_date(
    profile_id:  int,
    expiry_date: str,
    performed_by: int | None = None,
) -> bool:
    """
    Directly update expiry_date on a ResidencyProfile and append a timeline entry.
    Returns True on success.
    Used for quick date correction from the archive profile view.
    """
    from db.session import get_db
    from db.models import ResidencyProfile, ResidencyUpdate
    try:
        with get_db() as db:
            p = db.query(ResidencyProfile).filter(ResidencyProfile.id == profile_id).first()
            if p is None:
                return False
            old_expiry  = p.expiry_date or ""
            p.expiry_date = expiry_date
            db.add(ResidencyUpdate(
                profile_id=      profile_id,
                action_type=     "date_updated",
                action_label=    "تعديل تاريخ الانتهاء",
                old_expiry_date= old_expiry,
                new_expiry_date= expiry_date,
                new_status=      p.status or "active",
                performed_by=    performed_by,
            ))
        logger.info(
            f"[residency.profiles] update_profile_expiry_date"
            f"  id={profile_id}  date={expiry_date!r}"
        )
        return True
    except Exception as exc:
        logger.error(
            f"[residency.profiles] update_profile_expiry_date FAILED"
            f"  id={profile_id}: {exc}",
            exc_info=True,
        )
        return False


@dataclass
class SavedProfile:
    profile_id: int
    name:       str


def save_profile(
    *,
    name:             str,
    expiry_date:      str,
    residency_number: str,
    documents:        list[dict],
    companions:       list[dict],
    notes:            str,
    source:           str = "manual",
    arrival_patient_id: int | None = None,
    created_by:       int | None = None,
) -> SavedProfile:
    """
    Persist a new residency profile with companions and an initial timeline entry.
    Returns a SavedProfile with the new profile ID.
    """
    from db.session import get_db
    from db.models import ResidencyProfile, ResidencyCompanion, ResidencyUpdate

    # Extract the first document file_id if documents were uploaded
    latest_res_fid = ""
    if documents:
        latest_res_fid = documents[0].get("file_id", "") if documents else ""

    with get_db() as db:
        profile = ResidencyProfile(
            arrival_patient_id=       arrival_patient_id,
            source=                   source,
            name=                     name,
            status=                   "active",
            residency_number=         residency_number,
            expiry_date=              expiry_date,
            latest_residency_file_id= latest_res_fid,
            notes=                    notes,
            created_by=               created_by,
        )
        db.add(profile)
        db.flush()
        profile_id = profile.id

        for c in companions:
            comp = ResidencyCompanion(
                profile_id=  profile_id,
                name=        c.get("name", ""),
                expiry_date= c.get("expiry_date", ""),
                status=      "active",
            )
            db.add(comp)

        update = ResidencyUpdate(
            profile_id=   profile_id,
            action_type=  "manual_add",
            action_label= "إضافة يدوية",
            new_status=   "active",
            new_expiry_date= expiry_date,
            performed_by= created_by,
        )
        db.add(update)

    logger.info(f"[residency.profiles] saved profile id={profile_id}  name={name!r}  source={source!r}")
    return SavedProfile(profile_id=profile_id, name=name)


def save_manual_batch(
    *,
    patients:   list[dict],
    batch_notes: str,
    created_at:  str,
    created_by:  int | None = None,
) -> int:
    """
    Persist a manually entered batch of residency profiles (new arrivals-style flow).
    Each patient dict contains: name, visa_expiry, passport_file_id, visa_file_id,
    has_companion, companions:[{name, visa_expiry, passport_file_id, visa_file_id}].
    Returns the number of profiles created.
    """
    from db.session import get_db
    from db.models import ResidencyProfile, ResidencyCompanion, ResidencyUpdate

    count = 0
    with get_db() as db:
        for p in patients:
            profile = ResidencyProfile(
                source=           "manual",
                name=             p.get("name", ""),
                status=           "active",
                residency_number= "",
                expiry_date=      p.get("visa_expiry", ""),
                passport_file_id= p.get("passport_file_id", ""),
                visa_file_id=     p.get("visa_file_id", ""),
                notes=            batch_notes,
                created_by=       created_by,
            )
            db.add(profile)
            db.flush()
            profile_id = profile.id

            for c in p.get("companions", []):
                comp = ResidencyCompanion(
                    profile_id=      profile_id,
                    name=            c.get("name", ""),
                    status=          "active",
                    expiry_date=     c.get("visa_expiry", ""),
                    passport_file_id=c.get("passport_file_id", ""),
                    visa_file_id=    c.get("visa_file_id", ""),
                )
                db.add(comp)

            history = ResidencyUpdate(
                profile_id=      profile_id,
                action_type=     "manual_add",
                action_label=    "إضافة يدوية",
                new_status=      "active",
                new_expiry_date= p.get("visa_expiry", ""),
                performed_by=    created_by,
            )
            db.add(history)
            count += 1

    logger.info(
        f"[residency.profiles] save_manual_batch: {count} profiles saved"
        f"  created_by={created_by}"
    )
    return count


def create_profiles_from_arrival_batch(
    batch_id:  int,
    patients:  list[dict],
    created_by: int | None = None,
) -> int:
    """
    Auto-create ResidencyProfile + ResidencyCompanion rows from a just-published
    ArrivalBatch.  Called from arrivals/flow.py confirm handler — errors are
    logged and swallowed so they never break the arrivals publish.

    Returns the number of profiles created.
    """
    from db.session import get_db
    from db.models import ResidencyProfile, ResidencyCompanion, ResidencyUpdate, ArrivalPatient, ArrivalCompanion

    count = 0
    try:
        with get_db() as db:
            # Fetch freshly-persisted patients for this batch
            arrival_patients = (
                db.query(ArrivalPatient)
                .filter(ArrivalPatient.batch_id == batch_id)
                .order_by(ArrivalPatient.id.asc())
                .all()
            )

            for ap in arrival_patients:
                profile = ResidencyProfile(
                    arrival_patient_id=       ap.id,
                    source=                   "arrivals",
                    name=                     ap.name or "—",
                    status=                   "active",
                    expiry_date=              ap.residence_expiry or "",
                    passport_file_id=         ap.passport_file_id  or "",
                    visa_file_id=             ap.visa_file_id       or "",
                    latest_residency_file_id= ap.residence_file_id  or "",
                    created_by=               created_by,
                )
                db.add(profile)
                db.flush()
                profile_id = profile.id

                # Fetch companions for this patient
                companions = (
                    db.query(ArrivalCompanion)
                    .filter(ArrivalCompanion.patient_id == ap.id)
                    .order_by(ArrivalCompanion.id.asc())
                    .all()
                )
                for ac in companions:
                    comp = ResidencyCompanion(
                        profile_id=              profile_id,
                        arrival_companion_id=    ac.id,
                        name=                    ac.name or "—",
                        status=                  "active",
                        expiry_date=             ac.residence_expiry   or "",
                        passport_file_id=        ac.passport_file_id   or "",
                        visa_file_id=            ac.visa_file_id        or "",
                        latest_residency_file_id=ac.residence_file_id  or "",
                    )
                    db.add(comp)

                update = ResidencyUpdate(
                    profile_id=   profile_id,
                    action_type=  "profile_created",
                    action_label= "إنشاء تلقائي من الوصول",
                    new_status=   "active",
                    new_expiry_date= ap.residence_expiry or "",
                    performed_by= created_by,
                )
                db.add(update)
                count += 1

    except Exception as exc:
        logger.error(
            f"[residency.profiles] create_profiles_from_arrival_batch FAILED"
            f"  batch_id={batch_id}: {exc}",
            exc_info=True,
        )

    logger.info(
        f"[residency.profiles] auto-created {count} profiles from batch_id={batch_id}"
    )
    return count
