# modules/healthcare/woundcare/models.py
# Database persistence for wound care records — official 11-step workflow.

import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SavedWoundRecord:
    """Returned after a successful DB save."""
    record_id:            int
    patient_name:         str
    department_labels:    list[str]
    operation_name:       str
    phase_label:          str
    condition_description: str
    supply_labels:        list[str]
    image_count:          int
    specialist_name:      str


def save_wound_record(
    *,
    patient_id:                int | None,
    patient_name:              str,
    medical_department_ids:    list[str],
    medical_department_labels: list[str],
    operation_name:            str,
    phase:                     str,
    phase_label:               str,
    condition_description:     str,
    supply_ids:                list[str],
    supply_labels:             list[str],
    images:                    list[dict],   # list[UploadedFile.to_dict()]
    notes:                     str,
    specialist_name:           str,
    created_by:                int | None,
) -> SavedWoundRecord:
    """
    Persist a wound care record to the database.

    Returns a SavedWoundRecord with the new row's ID.
    Raises on DB error — caller should handle and show user-facing message.
    """
    from db.session import get_db
    from db.models import WoundRecord

    image_file_ids = [d.get("file_id", "") for d in images]

    logger.debug(
        "[healthcare.publish] save_wound_record entering DB write"
        f"  patient_id={patient_id}  images={len(images)}"
        f"  depts={medical_department_labels}"
        f"  op={operation_name!r}  phase={phase!r}"
    )

    with get_db() as db:
        record = WoundRecord(
            patient_id=               patient_id,
            patient_name=             patient_name,
            medical_departments_json= json.dumps(medical_department_labels, ensure_ascii=False),
            operation_name=           operation_name or "",
            phase=                    phase or "",
            phase_label=              phase_label or "",
            condition_description=    condition_description or "",
            supplies_json=            json.dumps(supply_labels, ensure_ascii=False),
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
        f"[woundcare] saved record id={record_id}"
        f"  patient={patient_name!r}  depts={medical_department_labels}"
        f"  op={operation_name!r}  phase={phase!r}"
        f"  supplies={supply_labels}  images={len(images)}"
        f"  specialist={specialist_name!r}  by={created_by}"
    )

    return SavedWoundRecord(
        record_id=            record_id,
        patient_name=         patient_name,
        department_labels=    medical_department_labels,
        operation_name=       operation_name,
        phase_label=          phase_label,
        condition_description=condition_description,
        supply_labels=        supply_labels,
        image_count=          len(images),
        specialist_name=      specialist_name,
    )
