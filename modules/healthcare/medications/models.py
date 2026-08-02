# modules/healthcare/medications/models.py

import json
import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SavedMedicationRecord:
    record_id:         int
    patient_name:      str
    department_labels: list[str]   # medical specialty labels
    item_count:        str         # عدد الأصناف — نص حر (رقم و/أو وصف)
    dispense_source:   str         # الصيدلية / المخزن
    image_count:       int
    specialist_name:   str


def save_medication_record(
    *,
    patient_id:               int | None,
    patient_name:             str,
    medical_department_ids:   list[str],
    medical_department_labels: list[str],
    item_count:               str,
    dispense_source:          str = "",
    images:                   list[dict],
    notes:                    str,
    specialist_name:          str,
    created_by:               int | None,
    created_at:               "datetime | None" = None,
) -> SavedMedicationRecord:
    from db.session import get_db
    from db.models import MedicationRecord

    image_file_ids = [d.get("file_id", "") for d in images]

    logger.debug(
        "[healthcare.publish] save_medication_record entering DB write"
        f"  patient_id={patient_id}  item_count={item_count}"
        f"  dispense_source={dispense_source!r}"
        f"  depts={medical_department_labels}"
    )

    with get_db() as db:
        record = MedicationRecord(
            patient_id=               patient_id,
            patient_name=             patient_name,
            medical_departments_json= json.dumps(medical_department_labels, ensure_ascii=False),
            item_count=               item_count,
            dispense_source=          dispense_source or "",
            image_file_ids=           json.dumps(image_file_ids, ensure_ascii=False),
            image_count=              len(images),
            notes=                    notes or "",
            specialist_name=          specialist_name or "",
            created_by=               created_by,
            # ✅ تاريخ الصرف الفعلي الذي اختاره المستخدم في خطوة "📅 اختر
            # التاريخ" (اليوم أو من التقويم) — وليس وقت النشر الفعلي. بدون هذا
            # كان العمود يأخذ القيمة الافتراضية (datetime.utcnow عند الحفظ)،
            # فيتجاهل اختيار المستخدم تماماً ويظهر تاريخ خاطئ لاحقاً في مسير
            # إخلاء الصيدلية (الذي يقرأ هذا العمود بالضبط).
            created_at=               created_at or datetime.utcnow(),
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
        dispense_source=   dispense_source or "",
        image_count=       len(images),
        specialist_name=   specialist_name,
    )
