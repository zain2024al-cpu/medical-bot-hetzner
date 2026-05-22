# modules/healthcare/other/models.py

import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SavedOtherRecord:
    record_id:      int
    patient_name:   str
    action_labels:  list[str]
    image_count:    int
    specialist_name: str


def save_other_record(
    *,
    patient_id:       int | None,
    patient_name:     str,
    operation_ids:    list[str],
    operation_labels: list[str],
    images:           list[dict],
    notes:            str,
    specialist_name:  str,
    created_by:       int | None,
) -> SavedOtherRecord:
    from db.session import get_db
    from db.models import OtherHealthcareRecord

    image_file_ids = [d.get("file_id", "") for d in images]

    with get_db() as db:
        record = OtherHealthcareRecord(
            patient_id=     patient_id,
            patient_name=   patient_name,
            action_ids=     json.dumps(operation_ids,    ensure_ascii=False),
            action_labels=  json.dumps(operation_labels, ensure_ascii=False),
            image_file_ids= json.dumps(image_file_ids,   ensure_ascii=False),
            image_count=    len(images),
            notes=          notes or "",
            specialist_name=specialist_name or "",
            created_by=     created_by,
        )
        db.add(record)
        db.flush()
        record_id = record.id

    logger.info(
        f"[other_hc] saved record id={record_id}  patient={patient_name!r}"
    )

    return SavedOtherRecord(
        record_id=       record_id,
        patient_name=    patient_name,
        action_labels=   operation_labels,
        image_count=     len(images),
        specialist_name= specialist_name,
    )
