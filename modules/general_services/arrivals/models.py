# modules/general_services/arrivals/models.py

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SavedArrivalBatch:
    batch_id:         int
    specialist_label: str
    patient_count:    int


def save_arrival_batch(
    *,
    specialist_id:    str,
    specialist_label: str,
    patients:         list[dict],
    created_by:       int | None,
) -> SavedArrivalBatch:
    """
    Persist the batch header, all patients, and companions atomically.
    Returns a SavedArrivalBatch with the new batch ID.

    ✅ لا معاملات hospital_id/hospital_label بعد الآن — "الجهة الموصلة" أصبحت
    حقلاً خاصاً بكل فرد (escort_entity) بدل خطوة واحدة للدفعة كاملة.
    عمودا ArrivalBatch.hospital_id/hospital_label يبقيان في القاعدة (بيانات
    الدفعات القديمة) لكن لا تُغذّى بعد الآن لأي دفعة جديدة.
    """
    from db.session import get_db
    from db.models import ArrivalBatch, ArrivalPatient, ArrivalCompanion

    with get_db() as db:
        batch = ArrivalBatch(
            specialist_id=     specialist_id,
            specialist_label=  specialist_label,
            patient_count=     len(patients),
            created_by=        created_by,
        )
        db.add(batch)
        db.flush()
        batch_id = batch.id

        for p in patients:
            patient_row = ArrivalPatient(
                batch_id=             batch_id,
                name=                 p.get("name", ""),
                arrival_date=         p.get("arrival_date", ""),
                passport_expiry=      p.get("passport_expiry", ""),
                visa_expiry=          p.get("visa_expiry", ""),
                has_companion=        bool(p.get("has_companion", False)),
                passport_file_id=     p.get("passport_file_id", ""),
                visa_file_id=         p.get("visa_file_id", ""),
                entry_stamp_file_id=  p.get("entry_stamp_file_id", ""),
                tickets_file_id=      p.get("tickets_file_id", ""),
                residence_file_id=    p.get("residence_file_id", ""),
                residence_expiry=     p.get("residence_expiry", ""),
                notes=                p.get("notes", ""),
                services_provided=    p.get("services_provided", ""),
                escort_entity=        p.get("escort_entity", ""),
                residence_address=    p.get("residence_address", ""),
            )
            db.add(patient_row)
            db.flush()
            patient_id = patient_row.id

            for c in p.get("companions", []):
                companion_row = ArrivalCompanion(
                    patient_id=           patient_id,
                    name=                 c.get("name", ""),
                    arrival_date=         c.get("arrival_date", ""),
                    passport_expiry=      c.get("passport_expiry", ""),
                    passport_file_id=     c.get("passport_file_id", ""),
                    visa_file_id=         c.get("visa_file_id", ""),
                    entry_stamp_file_id=  c.get("entry_stamp_file_id", ""),
                    tickets_file_id=      c.get("tickets_file_id", ""),
                    residence_file_id=    c.get("residence_file_id", ""),
                    residence_expiry=     c.get("residence_expiry", ""),
                    notes=                c.get("notes", ""),
                    services_provided=    c.get("services_provided", ""),
                    escort_entity=        c.get("escort_entity", ""),
                    residence_address=    c.get("residence_address", ""),
                )
                db.add(companion_row)

    logger.info(
        f"[arrivals] saved batch id={batch_id}"
        f"  specialist={specialist_label!r}"
        f"  patients={len(patients)}"
    )
    return SavedArrivalBatch(
        batch_id=         batch_id,
        specialist_label= specialist_label,
        patient_count=    len(patients),
    )
