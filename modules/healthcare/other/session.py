# modules/healthcare/other/session.py

from dataclasses import dataclass
from datetime import datetime

_KEY = "_hcoth_add"

STEP_DATE        = "date"         # 1. اختيار التاريخ  (first visible step)
STEP_DATE_CUSTOM = "date_custom"  # 1b. free-text date entry
STEP_PATIENT     = "patient"
STEP_OPERATIONS = "operations"
STEP_IMAGES     = "images"
STEP_NOTES      = "notes"
STEP_SPECIALIST = "specialist"
STEP_REVIEW     = "review"


@dataclass
class OtherHealthcareSession:
    step:             str
    patient_id:       int | None
    patient_name:     str
    operation_ids:    list[str]
    operation_labels: list[str]
    images:           list[dict]
    notes:            str
    specialist_name:  str
    created_at:       str

    @property
    def image_count(self) -> int:
        return len(self.images)

    def save(self, user_data: dict) -> None:
        user_data[_KEY] = {
            "step":             self.step,
            "patient_id":       self.patient_id,
            "patient_name":     self.patient_name,
            "operation_ids":    self.operation_ids,
            "operation_labels": self.operation_labels,
            "images":           self.images,
            "notes":            self.notes,
            "specialist_name":  self.specialist_name,
            "created_at":       self.created_at,
        }

    @classmethod
    def create(cls, user_data: dict) -> "OtherHealthcareSession":
        session = cls(
            step=             STEP_DATE,
            patient_id=       None,
            patient_name=     "",
            operation_ids=    [],
            operation_labels= [],
            images=           [],
            notes=            "",
            specialist_name=  "",
            created_at=       datetime.utcnow().isoformat(),
        )
        session.save(user_data)
        return session

    @classmethod
    def load(cls, user_data: dict) -> "OtherHealthcareSession | None":
        raw = user_data.get(_KEY)
        if not raw:
            return None
        return cls(
            step=             raw.get("step",             STEP_DATE),
            patient_id=       raw.get("patient_id"),
            patient_name=     raw.get("patient_name",     ""),
            operation_ids=    raw.get("operation_ids",    []),
            operation_labels= raw.get("operation_labels", []),
            images=           raw.get("images",           []),
            notes=            raw.get("notes",            ""),
            specialist_name=  raw.get("specialist_name",  ""),
            created_at=       raw.get("created_at",       ""),
        )

    @classmethod
    def clear(cls, user_data: dict) -> None:
        user_data.pop(_KEY, None)
