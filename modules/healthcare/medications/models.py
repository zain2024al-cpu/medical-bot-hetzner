# modules/healthcare/medications/models.py

import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SavedMedicationRecord:
    record_id:         int
    patient_name:      str
    department_labels: list[str]   # medical specialty labels
    item_count:        int         # عدد الأصناف
    image_count:       int
    specialist_name:   str


def save_medication_record(
    *,
    patient_id:               int | None,
    patient_name:             str,
    medical_department_ids:   list[str],
    medical_department_labels: list[str],
    item_count:               int,
    images:                   list[dict],
    notes:                    str,
    specialist_name:          str,
    created_by:               int | None,
) -> SavedMedicationRecord:
    from db.session import get_db
    from db.models import MedicationRecord

    image_file_ids = [d.get("file_id", "") for d in images]

    with get_db() as db:
        record = MedicationRecord(
            patient_id=               patient_id,
            patient_name=             patient_name,
            medical_departments_json= json.dumps(medical_department_labels, ensure_ascii=False),
            item_count=               item_count,
            image_file_ids=           json.dumps(image_file_ids, ensure_ascii=False),
            image_count=              len(images),
            notes=                    notes or "",
            specialist_name=          specialist_name or "",
            created_by=               created_by,
        )
        db.add(record)
        db.flush()
        record_id = record.id

    logger.info(
        f"[medications] saved record id={record_id}"
        f"  patient={patient_name!r}"
        f"  depts={medical_department_labels}"
        f"  item_count={item_count}"
    )

    return SavedMedicationRecord(
        record_id=         record_id,
        patient_name=      patient_name,
        department_labels= medical_department_labels,
        item_count=        item_count,
        image_count=       len(images),
        specialist_name=   specialist_name,
    )
