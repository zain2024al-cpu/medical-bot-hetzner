# modules/healthcare/supplies/session.py

from dataclasses import dataclass
from datetime import datetime

_KEY = "_hcsup_add"

# ── Step identifiers (mirrors medications workflow) ───────────────────────────
STEP_DATE             = "date"
STEP_DATE_CUSTOM      = "date_custom"
STEP_PATIENT          = "patient"
STEP_DEPARTMENT       = "department"
STEP_DEPT_OTHER       = "dept_other"
STEP_COUNT            = "count"            # عدد المستلزمات (نص حر: رقم أو وصف)
STEP_IMAGES           = "images"
STEP_DISPENSE_SOURCE  = "dispense_source"
STEP_NOTES            = "notes"
STEP_SPECIALIST       = "specialist"
STEP_REVIEW           = "review"


@dataclass
class SuppliesSession:
    step:                      str
    patient_id:                int | None
    patient_name:              str
    medical_department_ids:    list[str]
    medical_department_labels: list[str]
    item_count:                str         # عدد المستلزمات — نص حر (رقم و/أو وصف)
    dispense_source:           str
    images:                    list[dict]
    notes:                     str
    specialist_name:           str
    created_at:                str
    edit_from_review:          bool        # True while editing a section from review screen

    @property
    def image_count(self) -> int:
        return len(self.images)

    def save(self, user_data: dict) -> None:
        user_data[_KEY] = {
            "step":                      self.step,
            "patient_id":                self.patient_id,
            "patient_name":              self.patient_name,
            "medical_department_ids":    self.medical_department_ids,
            "medical_department_labels": self.medical_department_labels,
            "item_count":                self.item_count,
            "dispense_source":           self.dispense_source,
            "images":                    self.images,
            "notes":                     self.notes,
            "specialist_name":           self.specialist_name,
            "created_at":                self.created_at,
            "edit_from_review":          self.edit_from_review,
        }

    @classmethod
    def create(cls, user_data: dict) -> "SuppliesSession":
        session = cls(
            step=                     STEP_DATE,
            patient_id=               None,
            patient_name=             "",
            medical_department_ids=   [],
            medical_department_labels=[],
            item_count=               "",
            dispense_source=          "",
            images=                   [],
            notes=                    "",
            specialist_name=          "",
            created_at=               datetime.utcnow().isoformat(),
            edit_from_review=         False,
        )
        session.save(user_data)
        return session

    @classmethod
    def load(cls, user_data: dict) -> "SuppliesSession | None":
        raw = user_data.get(_KEY)
        if not raw:
            return None
        return cls(
            step=                     raw.get("step",                     STEP_DATE),
            patient_id=               raw.get("patient_id"),
            patient_name=             raw.get("patient_name",             ""),
            medical_department_ids=   raw.get("medical_department_ids",   []),
            medical_department_labels=raw.get("medical_department_labels",[]),
            item_count=               raw.get("item_count",               ""),
            dispense_source=          raw.get("dispense_source",          ""),
            images=                   raw.get("images",                   []),
            notes=                    raw.get("notes",                    ""),
            specialist_name=          raw.get("specialist_name",          ""),
            created_at=               raw.get("created_at",               ""),
            edit_from_review=         raw.get("edit_from_review",         False),
        )

    @classmethod
    def clear(cls, user_data: dict) -> None:
        user_data.pop(_KEY, None)
