# modules/healthcare/woundcare/models.py
# Database persistence for wound care records.
# Uses the existing SQLite + SQLAlchemy infrastructure.

import json
import logging

from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SavedWoundRecord:
    """Returned after a successful DB save."""
    record_id: int
    patient_name: str
    wound_type_labels: list[str]
    image_count: int


def save_wound_record(
    *,
    patient_id:       int | None,
    patient_name:     str,
    wound_type_ids:   list[str],
    wound_type_labels: list[str],
    images:           list[dict],   # list[UploadedFile.to_dict()]
    notes:            str,
    created_by:       int | None,
) -> SavedWoundRecord:
    """
    Persist a wound care record to the database.

    Returns a SavedWoundRecord with the new row's ID.
    Raises on DB error — caller should handle and show user-facing message.
    """
    from db.session import get_db
    from db.models import WoundRecord

    image_file_ids = [d.get("file_id", "") for d in images]

    with get_db() as db:
        record = WoundRecord(
            patient_id=        patient_id,
            patient_name=      patient_name,
            wound_types=       json.dumps(wound_type_ids,    ensure_ascii=False),
            wound_type_labels= json.dumps(wound_type_labels, ensure_ascii=False),
            image_file_ids=    json.dumps(image_file_ids,    ensure_ascii=False),
            image_count=       len(images),
            notes=             notes or "",
            created_by=        created_by,
        )
        db.add(record)
        db.flush()   # populate record.id before commit
        record_id = record.id

    logger.info(
        f"[woundcare] saved record id={record_id}"
        f"  patient={patient_name!r}  types={wound_type_ids}"
        f"  images={len(images)}  by={created_by}"
    )

    return SavedWoundRecord(
        record_id=         record_id,
        patient_name=      patient_name,
        wound_type_labels= wound_type_labels,
        image_count=       len(images),
    )
