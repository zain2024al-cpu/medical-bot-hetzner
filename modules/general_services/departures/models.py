# modules/general_services/departures/models.py

import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SavedDepartureRecord:
    record_id:        int
    hospital_label:   str
    specialist_label: str
    image_count:      int


def save_departure_record(
    *,
    arrival_patient_ids: list[int],
    patients_text:       str,
    hospital_id:         str,
    hospital_label:      str,
    images:              list[dict],
    notes:               str,
    specialist_id:       str,
    specialist_label:    str,
    created_by:          int | None,
) -> SavedDepartureRecord:
    from db.session import get_db
    from db.models import DepartureRecord

    image_file_ids = [d.get("file_id", "") for d in images]

    with get_db() as db:
        record = DepartureRecord(
            arrival_patient_ids= json.dumps(arrival_patient_ids, ensure_ascii=False),
            patients_text=       patients_text or "",
            hospital_id=         hospital_id,
            hospital_label=      hospital_label,
            image_file_ids=      json.dumps(image_file_ids, ensure_ascii=False),
            image_count=         len(images),
            notes=               notes or "",
            specialist_id=       specialist_id,
            specialist_label=    specialist_label,
            created_by=          created_by,
        )
        db.add(record)
        db.flush()
        record_id = record.id

    logger.info(
        f"[departures] saved record id={record_id}"
        f"  hospital={hospital_label!r}  specialist={specialist_label!r}"
        f"  patients={len(arrival_patient_ids)}  images={len(images)}"
    )
    return SavedDepartureRecord(
        record_id=        record_id,
        hospital_label=   hospital_label,
        specialist_label= specialist_label,
        image_count=      len(images),
    )
