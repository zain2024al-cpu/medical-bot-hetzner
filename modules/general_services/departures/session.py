# modules/general_services/departures/session.py

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime

_SESSION_KEY = "_gsdep_add"

# ── Steps ─────────────────────────────────────────────────────────────────────
STEP_DATE            = "date"
STEP_DATE_CUSTOM     = "date_custom"
STEP_SELECT_ARRIVALS = "select_arrivals"   # replaced free-text STEP_PATIENTS
STEP_IMAGES          = "images"
STEP_HOSPITAL        = "hospital"
STEP_NOTES           = "notes"
STEP_SPECIALIST      = "specialist"
STEP_REVIEW          = "review"


@dataclass
class DepartureSession:
    step:                str
    created_at:          str
    arrival_patient_ids: list[int]   # IDs selected from arrival archive
    patients_text:       str         # auto-generated from patient + companion names
    images:              list[dict]
    hospital_id:         str
    hospital_label:      str
    notes:               str
    specialist_id:       str
    specialist_label:    str
    edit_from_review:    bool

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, user_data: dict) -> None:
        user_data[_SESSION_KEY] = {
            "step":                self.step,
            "created_at":          self.created_at,
            "arrival_patient_ids": self.arrival_patient_ids,
            "patients_text":       self.patients_text,
            "images":              self.images,
            "hospital_id":         self.hospital_id,
            "hospital_label":      self.hospital_label,
            "notes":               self.notes,
            "specialist_id":       self.specialist_id,
            "specialist_label":    self.specialist_label,
            "edit_from_review":    self.edit_from_review,
        }

    @classmethod
    def load(cls, user_data: dict) -> DepartureSession | None:
        raw = user_data.get(_SESSION_KEY)
        if not raw:
            return None
        return cls(
            step=                raw.get("step",                STEP_DATE),
            created_at=          raw.get("created_at",          datetime.utcnow().isoformat()),
            arrival_patient_ids= raw.get("arrival_patient_ids", []),
            patients_text=       raw.get("patients_text",       ""),
            images=              raw.get("images",              []),
            hospital_id=         raw.get("hospital_id",         ""),
            hospital_label=      raw.get("hospital_label",      ""),
            notes=               raw.get("notes",               ""),
            specialist_id=       raw.get("specialist_id",       ""),
            specialist_label=    raw.get("specialist_label",    ""),
            edit_from_review=    raw.get("edit_from_review",    False),
        )

    @classmethod
    def create(cls, user_data: dict) -> DepartureSession:
        session = cls(
            step=                STEP_DATE,
            created_at=          datetime.utcnow().isoformat(),
            arrival_patient_ids= [],
            patients_text=       "",
            images=              [],
            hospital_id=         "",
            hospital_label=      "",
            notes=               "",
            specialist_id=       "",
            specialist_label=    "",
            edit_from_review=    False,
        )
        session.save(user_data)
        return session

    @classmethod
    def clear(cls, user_data: dict) -> None:
        user_data.pop(_SESSION_KEY, None)

    @property
    def image_count(self) -> int:
        return len(self.images)
