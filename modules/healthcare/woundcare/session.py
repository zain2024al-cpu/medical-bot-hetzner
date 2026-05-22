# modules/healthcare/woundcare/session.py
# Typed session state for the woundcare operational flow — official 11-step spec.
#
# Steps:
#   1. التاريخ          — auto (session.create)
#   2. المريض           — patient_selector
#   3. القسم الطبي      — DEPARTMENT_OPTIONS multiselect (+ dept_other branch)
#   4. اسم العملية      — free-text (required, no skip)
#   5. مرحلة المجارحة   — single-select callback (4 options)
#   6. وصف الحالة       — free-text (required, no skip)
#   7. المستلزمات الطبية — SUPPLIES_OPTIONS multiselect (+ supplies_other branch)
#   8. التوثيق / الصور  — uploads (optional, 0-10)
#   9. الملاحظات        — free-text (optional, skip allowed)
#  10. اسم الصحي        — fixed 3-name selector (required, no skip)
#  11. مراجعة + نشر     — review → confirm

from dataclasses import dataclass, field
from datetime import datetime
from shared.uploads._models import UploadedFile

_KEY = "_wc_add"

# ── Step identifiers ──────────────────────────────────────────────────────────
STEP_DATE            = "date"       # 1. اختيار التاريخ  (first visible step)
STEP_DATE_CUSTOM     = "date_custom"  # 1b. free-text date entry (manual calendar)
STEP_PATIENT         = "patient"
STEP_DEPARTMENT      = "department"
STEP_DEPT_OTHER      = "dept_other"
STEP_OPERATION_NAME  = "operation_name"
STEP_PHASE           = "phase"
STEP_DESCRIPTION       = "description"        # multiselect for condition
STEP_DESCRIPTION_OTHER = "description_other"  # free-text for "أخرى" branch
STEP_SUPPLIES        = "supplies"
STEP_SUPPLIES_OTHER  = "supplies_other"
STEP_IMAGES          = "images"
STEP_NOTES           = "notes"
STEP_SPECIALIST      = "specialist"
STEP_REVIEW          = "review"


@dataclass
class WoundcareAddSession:
    step:                       str
    patient_id:                 int | None
    patient_name:               str
    medical_department_ids:     list[str]    # multiselect option IDs
    medical_department_labels:  list[str]    # display labels
    operation_name:             str          # اسم العملية (free text, required)
    phase:                      str          # callback key e.g. "phase_pre_op"
    phase_label:                str          # Arabic display e.g. "قبل العملية"
    condition_ids:               list[str]    # multiselect option IDs
    condition_labels:            list[str]    # display labels
    condition_other:             str          # free-text when "أخرى" selected
    supply_ids:                 list[str]    # multiselect option IDs
    supply_labels:              list[str]    # display labels
    images:                     list[dict]   # list[UploadedFile.to_dict()]
    notes:                      str          # optional
    specialist_name:            str          # one of: د. فضل / د. سرور / د. زكريا
    created_at:                 str          # ISO datetime string set at session creation

    @property
    def image_count(self) -> int:
        return len(self.images)

    @property
    def is_complete(self) -> bool:
        return bool(
            self.patient_name
            and self.medical_department_ids
            and self.operation_name
            and self.phase
        )

    def get_images(self) -> list[UploadedFile]:
        return [UploadedFile.from_dict(d) for d in self.images]

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, user_data: dict) -> None:
        user_data[_KEY] = {
            "step":                      self.step,
            "patient_id":                self.patient_id,
            "patient_name":              self.patient_name,
            "medical_department_ids":    self.medical_department_ids,
            "medical_department_labels": self.medical_department_labels,
            "operation_name":            self.operation_name,
            "phase":                     self.phase,
            "phase_label":               self.phase_label,
            "condition_ids":              self.condition_ids,
            "condition_labels":           self.condition_labels,
            "condition_other":            self.condition_other,
            "supply_ids":                self.supply_ids,
            "supply_labels":             self.supply_labels,
            "images":                    self.images,
            "notes":                     self.notes,
            "specialist_name":           self.specialist_name,
            "created_at":                self.created_at,
        }

    @classmethod
    def create(cls, user_data: dict) -> "WoundcareAddSession":
        session = cls(
            step=                      STEP_DATE,
            patient_id=                None,
            patient_name=              "",
            medical_department_ids=    [],
            medical_department_labels= [],
            operation_name=            "",
            phase=                     "",
            phase_label=               "",
            condition_ids=             [],
            condition_labels=          [],
            condition_other=           "",
            supply_ids=                [],
            supply_labels=             [],
            images=                    [],
            notes=                     "",
            specialist_name=           "",
            created_at=                datetime.utcnow().isoformat(),
        )
        session.save(user_data)
        return session

    @classmethod
    def load(cls, user_data: dict) -> "WoundcareAddSession | None":
        raw = user_data.get(_KEY)
        if not raw:
            return None
        return cls(
            step=                      raw.get("step",                      STEP_DATE),
            patient_id=                raw.get("patient_id"),
            patient_name=              raw.get("patient_name",              ""),
            medical_department_ids=    raw.get("medical_department_ids",    []),
            medical_department_labels= raw.get("medical_department_labels", []),
            operation_name=            raw.get("operation_name",            ""),
            phase=                     raw.get("phase",                     ""),
            phase_label=               raw.get("phase_label",               ""),
            condition_ids=             raw.get("condition_ids",             []),
            condition_labels=          raw.get("condition_labels",          []),
            condition_other=           raw.get("condition_other",           ""),
            supply_ids=                raw.get("supply_ids",                []),
            supply_labels=             raw.get("supply_labels",             []),
            images=                    raw.get("images",                    []),
            notes=                     raw.get("notes",                     ""),
            specialist_name=           raw.get("specialist_name",           ""),
            created_at=                raw.get("created_at",                ""),
        )

    @classmethod
    def clear(cls, user_data: dict) -> None:
        user_data.pop(_KEY, None)
