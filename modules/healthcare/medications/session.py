# modules/healthcare/medications/session.py

from dataclasses import dataclass
from datetime import datetime

_KEY = "_hcmed_add"

# ── Step identifiers (official workflow order) ────────────────────────────────
STEP_DATE             = "date"             # 1.  اختيار التاريخ  (first visible step)
STEP_DATE_CUSTOM      = "date_custom"      # 1b. free-text date entry
STEP_PATIENT          = "patient"          # 2.  اسم المريض
STEP_DEPARTMENT       = "department"       # 3.  القسم (medical specialty multiselect)
STEP_DEPT_OTHER       = "dept_other"       # 3b. free-text when "أخرى" selected
STEP_COUNT            = "count"            # 4.  عدد الأصناف (numeric input)
STEP_IMAGES           = "images"           # 5.  رفع صورة الوصفة
STEP_DISPENSE_SOURCE  = "dispense_source"  # 6.  جهة الصرف (الصيدلية / المخزن)
STEP_NOTES            = "notes"            # 7.  ملاحظات
STEP_SPECIALIST       = "specialist"       # 8.  اسم الصحي (fixed 3-name single-select)
STEP_REVIEW           = "review"           # 9.  مراجعة نهائية


@dataclass
class MedicationSession:
    step:                     str
    patient_id:               int | None
    patient_name:             str
    medical_department_ids:   list[str]   # multiselect IDs from DEPARTMENT step
    medical_department_labels: list[str]  # display labels (may include free-text replacement)
    item_count:               int         # عدد الأصناف — numeric input from COUNT step
    images:                   list[dict]
    notes:                    str
    specialist_name:          str         # must be one of: سرور / فضل / زكريا
    created_at:               str

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
            "images":                    self.images,
            "notes":                     self.notes,
            "specialist_name":           self.specialist_name,
            "created_at":                self.created_at,
        }

    @classmethod
    def create(cls, user_data: dict) -> "MedicationSession":
        session = cls(
            step=                     STEP_DATE,
            patient_id=               None,
            patient_name=             "",
            medical_department_ids=   [],
            medical_department_labels=[],
            item_count=               0,
            images=                   [],
            notes=                    "",
            specialist_name=          "",
            created_at=               datetime.utcnow().isoformat(),
        )
        session.save(user_data)
        return session

    @classmethod
    def load(cls, user_data: dict) -> "MedicationSession | None":
        raw = user_data.get(_KEY)
        if not raw:
            return None
        return cls(
            step=                     raw.get("step",                     STEP_DATE),
            patient_id=               raw.get("patient_id"),
            patient_name=             raw.get("patient_name",             ""),
            medical_department_ids=   raw.get("medical_department_ids",   []),
            medical_department_labels=raw.get("medical_department_labels",[]),
            item_count=               raw.get("item_count",               0),
            images=                   raw.get("images",                   []),
            notes=                    raw.get("notes",                    ""),
            specialist_name=          raw.get("specialist_name",          ""),
            created_at=               raw.get("created_at",               ""),
        )

    @classmethod
    def clear(cls, user_data: dict) -> None:
        user_data.pop(_KEY, None)
