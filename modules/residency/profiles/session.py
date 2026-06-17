# modules/residency/profiles/session.py
# Session for the "Add New Patient" batch flow — mirrors ArrivalSession structure.

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

_SESSION_KEY = "_res_add"

# ── Steps (same mental model as arrivals) ─────────────────────────────────────
STEP_DATE            = "date"
STEP_DATE_CUSTOM     = "date_custom"
STEP_PATIENT_COUNT   = "patient_count"
STEP_P_NAME          = "p_name"
STEP_P_VISA_EXPIRY   = "p_visa_expiry"
STEP_P_PASSPORT      = "p_passport"
STEP_P_VISA          = "p_visa"
STEP_P_HAS_COMPANION = "p_has_companion"
STEP_C_NAME          = "c_name"
STEP_C_VISA_EXPIRY   = "c_visa_expiry"
STEP_C_PASSPORT      = "c_passport"
STEP_C_VISA          = "c_visa"
STEP_BATCH_NOTES     = "batch_notes"
STEP_REVIEW          = "review"


@dataclass
class AddProfileSession:
    step:               str
    created_at:         str            # ISO datetime — used as registration date
    # Batch loop
    patient_count:      int
    patient_index:      int            # 0-based index of current patient
    current_patient:    dict           # {name, visa_expiry, passport_file_id, visa_file_id,
                                       #  has_companion, companions:[]}
    current_companion:  dict           # {name, visa_expiry, passport_file_id, visa_file_id}
    completed_patients: list           # finished patient dicts
    batch_notes:        str

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, user_data: dict) -> None:
        user_data[_SESSION_KEY] = {
            "step":               self.step,
            "created_at":         self.created_at,
            "patient_count":      self.patient_count,
            "patient_index":      self.patient_index,
            "current_patient":    self.current_patient,
            "current_companion":  self.current_companion,
            "completed_patients": self.completed_patients,
            "batch_notes":        self.batch_notes,
        }
        logger.debug(
            f"[AddProfileSession.save] step={self.step!r}"
            f"  p={self.patient_index}/{self.patient_count}"
        )

    @classmethod
    def load(cls, user_data: dict) -> AddProfileSession | None:
        raw = user_data.get(_SESSION_KEY)
        if not raw:
            return None
        return cls(
            step=               raw.get("step",               STEP_DATE),
            created_at=         raw.get("created_at",         datetime.utcnow().isoformat()),
            patient_count=      raw.get("patient_count",      0),
            patient_index=      raw.get("patient_index",      0),
            current_patient=    raw.get("current_patient",    {}),
            current_companion=  raw.get("current_companion",  {}),
            completed_patients= raw.get("completed_patients", []),
            batch_notes=        raw.get("batch_notes",        ""),
        )

    @classmethod
    def create(cls, user_data: dict) -> AddProfileSession:
        session = cls(
            step=               STEP_DATE,
            created_at=         datetime.utcnow().isoformat(),
            patient_count=      0,
            patient_index=      0,
            current_patient=    {},
            current_companion=  {},
            completed_patients= [],
            batch_notes=        "",
        )
        session.save(user_data)
        return session

    @classmethod
    def clear(cls, user_data: dict) -> None:
        user_data.pop(_SESSION_KEY, None)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @property
    def patients_done(self) -> bool:
        return len(self.completed_patients) >= self.patient_count

    def init_current_patient(self) -> None:
        self.current_patient = {
            "name": "", "visa_expiry": "",
            "passport_file_id": "", "visa_file_id": "",
            "has_companion": False, "companions": [],
        }

    def finish_current_patient(self) -> None:
        self.completed_patients.append(dict(self.current_patient))
        self.patient_index += 1

    def init_current_companion(self) -> None:
        self.current_companion = {
            "name": "", "visa_expiry": "",
            "passport_file_id": "", "visa_file_id": "",
        }

    def add_companion_to_current(self, companion: dict) -> None:
        if "companions" not in self.current_patient:
            self.current_patient["companions"] = []
        self.current_patient["companions"].append(dict(companion))
        self.current_companion = {}
