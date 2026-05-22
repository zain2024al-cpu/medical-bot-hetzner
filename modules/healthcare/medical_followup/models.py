# modules/healthcare/medical_followup/models.py
# Database persistence for medical follow-up records — official 11-step workflow.

import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SavedFollowupRecord:
    """Returned after a successful DB save."""
    record_id:             int
    patient_name:          str
    department_labels:     list[str]
    procedure_type_labels: list[str]
    complaint_labels:      list[str]
    image_count:           int
    specialist_name:       str


def save_followup_record(
    *,
    patient_id:                int | None,
    patient_name:              str,
    medical_department_ids:    list[str],
    medical_department_labels: list[str],
    procedure_type_ids:        list[str],
    procedure_type_labels:     list[str],
    complaint_ids:             list[str],
    complaint_labels:          list[str],
    vitals_temp:               str,
    vitals_bp:                 str,
    vitals_pulse:              str,
    vitals_spo2:               str,
    meds_supply_ids:           list[str],
    meds_supply_labels:        list[str],
    images:                    list[dict],   # list[UploadedFile.to_dict()]
    notes:                     str,
    specialist_name:           str,
    created_by:                int | None,
) -> SavedFollowupRecord:
    """
    Persist a medical follow-up record to the database.

    Returns a SavedFollowupRecord with the new row's ID.
    Raises on DB error — caller should handle and show user-facing message.
    """
    from db.session import get_db
    from db.models import MedicalFollowupRecord

    image_file_ids = [d.get("file_id", "") for d in images]

    with get_db() as db:
        record = MedicalFollowupRecord(
            patient_id=               patient_id,
            patient_name=             patient_name,
            medical_departments_json= json.dumps(medical_department_labels, ensure_ascii=False),
            procedure_type_json=      json.dumps(procedure_type_labels,     ensure_ascii=False),
            complaint_labels_json=    json.dumps(complaint_labels,          ensure_ascii=False),
            vitals_temp=              vitals_temp  or "",
            vitals_bp=                vitals_bp    or "",
            vitals_pulse=             vitals_pulse or "",
            vitals_spo2=              vitals_spo2  or "",
            meds_supply_labels_json=  json.dumps(meds_supply_labels, ensure_ascii=False),
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
        f"[followup] saved record id={record_id}"
        f"  patient={patient_name!r}  depts={medical_department_labels}"
        f"  proc={procedure_type_labels}  complaints={complaint_labels}"
        f"  vitals={vitals_temp}/{vitals_bp}/{vitals_pulse}/{vitals_spo2}"
        f"  meds={meds_supply_labels}  images={len(images)}"
        f"  specialist={specialist_name!r}  by={created_by}"
    )

    return SavedFollowupRecord(
        record_id=             record_id,
        patient_name=          patient_name,
        department_labels=     medical_department_labels,
        procedure_type_labels= procedure_type_labels,
        complaint_labels=      complaint_labels,
        image_count=           len(images),
        specialist_name=       specialist_name,
    )
