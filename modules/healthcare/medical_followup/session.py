# modules/healthcare/medical_followup/session.py
# Session state for the medical follow-up operational flow — official 11-step spec.
#
# Steps:
#   1. التاريخ               — auto (session.create)
#   2. المريض                — patient_selector
#   3. القسم الطبي           — DEPARTMENT_OPTIONS multiselect (+ dept_other branch)
#   4. نوع الإجراء           — PROCEDURE_TYPE_OPTIONS multiselect (6 opts, no أخرى)
#   5. الشكوى الرئيسية       — COMPLAINT_OPTIONS multiselect (+ أخرى branch)
#   6. العلامات الحيوية      — 4 sequential required text inputs (temp/BP/pulse/SpO2)
#   7. الأدوية والمستلزمات   — MEDS_SUPPLY_OPTIONS multiselect (+ أخرى branch)
#   8. التوثيق / الصور       — uploads (optional, 0-10)
#   9. الملاحظات             — free-text (optional, skip allowed)
#  10. اسم الصحي             — fixed 3-name selector (required, no skip)
#  11. مراجعة + نشر          — review → confirm

from dataclasses import dataclass
from datetime import datetime

from shared.uploads._models import UploadedFile

_KEY = "_hcfu_add"

# ── Step identifiers ──────────────────────────────────────────────────────────
STEP_DATE               = "date"         # 1. اختيار التاريخ  (first visible step)
STEP_DATE_CUSTOM        = "date_custom"  # 1b. free-text date entry
STEP_PATIENT            = "patient"
STEP_DEPARTMENT         = "department"
STEP_DEPT_OTHER         = "dept_other"
STEP_PROC_TYPE          = "proc_type"
STEP_COMPLAINT          = "complaint"
STEP_COMPLAINT_OTHER    = "complaint_other"
STEP_VITALS_TEMP        = "vitals_temp"
STEP_VITALS_BP          = "vitals_bp"
STEP_VITALS_PULSE       = "vitals_pulse"
STEP_VITALS_SPO2        = "vitals_spo2"
STEP_MEDS_SUPPLY        = "meds_supply"
STEP_MEDS_SUPPLY_OTHER  = "meds_supply_other"
STEP_IMAGES             = "images"
STEP_NOTES              = "notes"
STEP_SPECIALIST         = "specialist"
STEP_REVIEW             = "review"


@dataclass
class MedicalFollowupSession:
    step:                       str
    patient_id:                 int | None
    patient_name:               str
    medical_department_ids:     list[str]    # multiselect option IDs
    medical_department_labels:  list[str]    # display labels
    procedure_type_ids:         list[str]    # multiselect option IDs
    procedure_type_labels:      list[str]    # display labels
    complaint_ids:              list[str]    # multiselect option IDs
    complaint_labels:           list[str]    # display labels
    vitals_temp:                str          # درجة الحرارة (required)
    vitals_bp:                  str          # ضغط الدم (required)
    vitals_pulse:               str          # النبض (required)
    vitals_spo2:                str          # تشبع الأكسجين (required)
    meds_supply_ids:            list[str]    # multiselect option IDs
    meds_supply_labels:         list[str]    # display labels
    images:                     list[dict]   # list[UploadedFile.to_dict()]
    notes:                      str          # optional
    specialist_name:            str          # one of: د. فضل / د. سرور / د. زكريا
    created_at:                 str          # ISO datetime string set at session creation
    edit_from_review:           bool         # True while editing a section from review screen

    @property
    def image_count(self) -> int:
        return len(self.images)

    @property
    def is_complete(self) -> bool:
        return bool(
            self.patient_name
            and self.medical_department_ids
            and self.procedure_type_ids
            and self.vitals_temp
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
            "procedure_type_ids":        self.procedure_type_ids,
            "procedure_type_labels":     self.procedure_type_labels,
            "complaint_ids":             self.complaint_ids,
            "complaint_labels":          self.complaint_labels,
            "vitals_temp":               self.vitals_temp,
            "vitals_bp":                 self.vitals_bp,
            "vitals_pulse":              self.vitals_pulse,
            "vitals_spo2":               self.vitals_spo2,
            "meds_supply_ids":           self.meds_supply_ids,
            "meds_supply_labels":        self.meds_supply_labels,
            "images":                    self.images,
            "notes":                     self.notes,
            "specialist_name":           self.specialist_name,
            "created_at":                self.created_at,
            "edit_from_review":          self.edit_from_review,
        }

    @classmethod
    def create(cls, user_data: dict) -> "MedicalFollowupSession":
        session = cls(
            step=                      STEP_DATE,
            patient_id=                None,
            patient_name=              "",
            medical_department_ids=    [],
            medical_department_labels= [],
            procedure_type_ids=        [],
            procedure_type_labels=     [],
            complaint_ids=             [],
            complaint_labels=          [],
            vitals_temp=               "",
            vitals_bp=                 "",
            vitals_pulse=              "",
            vitals_spo2=               "",
            meds_supply_ids=           [],
            meds_supply_labels=        [],
            images=                    [],
            notes=                     "",
            specialist_name=           "",
            created_at=                datetime.utcnow().isoformat(),
            edit_from_review=          False,
        )
        session.save(user_data)
        return session

    @classmethod
    def load(cls, user_data: dict) -> "MedicalFollowupSession | None":
        raw = user_data.get(_KEY)
        if not raw:
            return None
        return cls(
            step=                      raw.get("step",                      STEP_DATE),
            patient_id=                raw.get("patient_id"),
            patient_name=              raw.get("patient_name",              ""),
            medical_department_ids=    raw.get("medical_department_ids",    []),
            medical_department_labels= raw.get("medical_department_labels", []),
            procedure_type_ids=        raw.get("procedure_type_ids",        []),
            procedure_type_labels=     raw.get("procedure_type_labels",     []),
            complaint_ids=             raw.get("complaint_ids",             []),
            complaint_labels=          raw.get("complaint_labels",          []),
            vitals_temp=               raw.get("vitals_temp",               ""),
            vitals_bp=                 raw.get("vitals_bp",                 ""),
            vitals_pulse=              raw.get("vitals_pulse",              ""),
            vitals_spo2=               raw.get("vitals_spo2",               ""),
            meds_supply_ids=           raw.get("meds_supply_ids",           []),
            meds_supply_labels=        raw.get("meds_supply_labels",        []),
            images=                    raw.get("images",                    []),
            notes=                     raw.get("notes",                     ""),
            specialist_name=           raw.get("specialist_name",           ""),
            created_at=                raw.get("created_at",                ""),
            edit_from_review=          raw.get("edit_from_review",          False),
        )

    @classmethod
    def clear(cls, user_data: dict) -> None:
        user_data.pop(_KEY, None)
