# modules/healthcare/woundcare/session.py
# Typed session state for the woundcare "Add Record" flow.
# Stored under a namespaced key in user_data.

from dataclasses import dataclass, field
from shared.uploads._models import UploadedFile

_KEY = "_wc_add"

# ── Step identifiers ──────────────────────────────────────────────────────────
STEP_PATIENT    = "patient"
STEP_WOUND_TYPE = "wound_type"
STEP_IMAGES     = "images"
STEP_NOTES      = "notes"
STEP_REVIEW     = "review"


@dataclass
class WoundcareAddSession:
    step:               str
    patient_id:         int | None
    patient_name:       str
    wound_type_ids:     list[str]    # multiselect option IDs
    wound_type_labels:  list[str]    # display labels for review / DB
    images:             list[dict]   # list[UploadedFile.to_dict()]
    notes:              str

    @property
    def image_count(self) -> int:
        return len(self.images)

    @property
    def is_complete(self) -> bool:
        return bool(self.patient_name and self.wound_type_ids)

    def get_images(self) -> list[UploadedFile]:
        return [UploadedFile.from_dict(d) for d in self.images]

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, user_data: dict) -> None:
        user_data[_KEY] = {
            "step":               self.step,
            "patient_id":         self.patient_id,
            "patient_name":       self.patient_name,
            "wound_type_ids":     self.wound_type_ids,
            "wound_type_labels":  self.wound_type_labels,
            "images":             self.images,
            "notes":              self.notes,
        }

    @classmethod
    def create(cls, user_data: dict) -> "WoundcareAddSession":
        session = cls(
            step=              STEP_PATIENT,
            patient_id=        None,
            patient_name=      "",
            wound_type_ids=    [],
            wound_type_labels= [],
            images=            [],
            notes=             "",
        )
        session.save(user_data)
        return session

    @classmethod
    def load(cls, user_data: dict) -> "WoundcareAddSession | None":
        raw = user_data.get(_KEY)
        if not raw:
            return None
        return cls(
            step=              raw.get("step",               STEP_PATIENT),
            patient_id=        raw.get("patient_id"),
            patient_name=      raw.get("patient_name",       ""),
            wound_type_ids=    raw.get("wound_type_ids",     []),
            wound_type_labels= raw.get("wound_type_labels",  []),
            images=            raw.get("images",             []),
            notes=             raw.get("notes",              ""),
        )

    @classmethod
    def clear(cls, user_data: dict) -> None:
        user_data.pop(_KEY, None)
