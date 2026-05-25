# modules/general_services/public_services/models.py

import json
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SavedPublicServiceRecord:
    record_id:        int
    patient_name:     str
    service_labels:   list[str]
    item_count:       int
    specialist_label: str
    image_count:      int


def save_public_service_record(
    *,
    patient_id:           Optional[int],
    patient_name:         str,
    service_type_labels:  list[str],
    item_count:           int,
    images:               list[dict],
    notes:                str,
    specialist_id:        str,
    specialist_label:     str,
    created_by:           Optional[int],
) -> SavedPublicServiceRecord:
    from db.session import get_db
    from db.models import PublicServiceRecord

    image_file_ids = [d.get("file_id", "") for d in images]

    with get_db() as db:
        record = PublicServiceRecord(
            patient_id=        patient_id,
            patient_name=      patient_name or "",
            service_type_json= json.dumps(service_type_labels, ensure_ascii=False),
            item_count=        item_count,
            image_file_ids=    json.dumps(image_file_ids, ensure_ascii=False),
            image_count=       len(images),
            notes=             notes or "",
            specialist_id=     specialist_id,
            specialist_label=  specialist_label,
            created_by=        created_by,
        )
        db.add(record)
        db.flush()
        record_id = record.id

    logger.info(
        f"[public_services] saved record id={record_id}"
        f"  patient={patient_name!r}  services={service_type_labels}"
        f"  item_count={item_count}  images={len(images)}"
    )
    return SavedPublicServiceRecord(
        record_id=        record_id,
        patient_name=     patient_name,
        service_labels=   service_type_labels,
        item_count=       item_count,
        specialist_label= specialist_label,
        image_count=      len(images),
    )
