# modules/general_services/arrivals/session.py

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

_SESSION_KEY = "_gsarr_add"

# ── Steps ─────────────────────────────────────────────────────────────────────
STEP_DATE               = "date"
STEP_DATE_CUSTOM        = "date_custom"
STEP_SPECIALIST         = "specialist"
STEP_PATIENT_COUNT      = "patient_count"
STEP_P_NAME             = "p_name"
# ✅ حقول فردية جديدة (جولة توسيع تدفق الواصلين — اختيار إلزامي من السجل)
STEP_P_ARRIVAL_DATE     = "p_arrival_date"
STEP_P_PASSPORT_EXPIRY  = "p_passport_expiry"
STEP_P_VISA_EXPIRY      = "p_visa_expiry"
STEP_P_HAS_COMPANION    = "p_has_companion"
STEP_P_PASSPORT         = "p_passport"
STEP_P_VISA             = "p_visa"
STEP_P_ENTRY_STAMP      = "p_entry_stamp"
STEP_P_TICKETS          = "p_tickets"
STEP_P_RESIDENCE        = "p_residence"
STEP_P_RESIDENCE_EXPIRY = "p_residence_expiry"
STEP_P_INDIV_NOTES      = "p_indiv_notes"
STEP_P_SERVICES         = "p_services"
STEP_P_ESCORT_ENTITY    = "p_escort_entity"
STEP_P_RESIDENCE_ADDRESS = "p_residence_address"
STEP_P_NOTES            = "p_notes"          # kept for legacy session compat only
STEP_BATCH_NOTES        = "batch_notes"
STEP_C_NAME             = "c_name"
STEP_C_ARRIVAL_DATE     = "c_arrival_date"
STEP_C_PASSPORT_EXPIRY  = "c_passport_expiry"
STEP_C_VISA_EXPIRY      = "c_visa_expiry"
STEP_C_PASSPORT         = "c_passport"
STEP_C_VISA             = "c_visa"
STEP_C_ENTRY_STAMP      = "c_entry_stamp"
STEP_C_TICKETS          = "c_tickets"
STEP_C_INDIV_NOTES      = "c_indiv_notes"
STEP_C_SERVICES         = "c_services"
STEP_C_ESCORT_ENTITY    = "c_escort_entity"
STEP_C_RESIDENCE_ADDRESS = "c_residence_address"
STEP_C_RESIDENCE        = "c_residence"         # kept for legacy session compat only
STEP_C_RESIDENCE_EXPIRY = "c_residence_expiry"  # kept for legacy session compat only
STEP_REVIEW             = "review"


@dataclass
class ArrivalSession:
    step:               str
    created_at:         str          # ISO datetime
    specialist_id:      str
    specialist_label:   str
    patient_count:      int
    completed_patients: list[dict]   # finished patients
    current_patient:    dict         # patient being filled
    current_companion:  dict         # companion being filled
    patient_index:      int          # 0-based index of current patient
    batch_notes:        str          # single notes field for the whole batch

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, user_data: dict) -> None:
        user_data[_SESSION_KEY] = {
            "step":               self.step,
            "created_at":         self.created_at,
            "specialist_id":      self.specialist_id,
            "specialist_label":   self.specialist_label,
            "patient_count":      self.patient_count,
            "completed_patients": self.completed_patients,
            "current_patient":    self.current_patient,
            "current_companion":  self.current_companion,
            "patient_index":      self.patient_index,
            "batch_notes":        self.batch_notes,
        }
        logger.info(
            f"[ArrivalSession.save] step={self.step!r}"
            f"  patient_index={self.patient_index}"
            f"  patient_count={self.patient_count}"
            f"  _gsarr_add_id={id(user_data.get(_SESSION_KEY))}"
        )

    @classmethod
    def load(cls, user_data: dict) -> ArrivalSession | None:
        raw = user_data.get(_SESSION_KEY)
        if not raw:
            logger.info("[ArrivalSession.load] key _gsarr_add missing → None")
            return None
        logger.info(
            f"[ArrivalSession.load] step={raw.get('step')!r}"
            f"  patient_index={raw.get('patient_index')}"
            f"  patient_count={raw.get('patient_count')}"
        )
        return cls(
            step=               raw.get("step",               STEP_DATE),
            created_at=         raw.get("created_at",         datetime.utcnow().isoformat()),
            specialist_id=      raw.get("specialist_id",      ""),
            specialist_label=   raw.get("specialist_label",   ""),
            patient_count=      raw.get("patient_count",      0),
            completed_patients= raw.get("completed_patients", []),
            current_patient=    raw.get("current_patient",    {}),
            current_companion=  raw.get("current_companion",  {}),
            patient_index=      raw.get("patient_index",      0),
            batch_notes=        raw.get("batch_notes",        ""),
        )

    @classmethod
    def create(cls, user_data: dict) -> ArrivalSession:
        session = cls(
            step=               STEP_DATE,
            created_at=         datetime.utcnow().isoformat(),
            specialist_id=      "",
            specialist_label=   "",
            patient_count=      0,
            completed_patients= [],
            current_patient=    {},
            current_companion=  {},
            patient_index=      0,
            batch_notes=        "",
        )
        session.save(user_data)
        return session

    @classmethod
    def clear(cls, user_data: dict) -> None:
        user_data.pop(_SESSION_KEY, None)

    # ── Patient helpers ────────────────────────────────────────────────────────

    def init_current_patient(self) -> None:
        self.current_patient = {
            "name":                "",
            "arrival_date":        "",
            "passport_expiry":     "",
            "visa_expiry":         "",
            "has_companion":       False,
            "passport_file_id":    "",
            "visa_file_id":        "",
            "entry_stamp_file_id": "",
            "tickets_file_id":     "",
            "residence_file_id":   "",
            "residence_expiry":    "",
            "notes":               "",
            "services_provided":   "",
            "escort_entity":       "",
            "residence_address":   "",
            "companions":          [],
        }
        self.current_companion = {}

    def finish_current_patient(self) -> None:
        self.completed_patients.append(dict(self.current_patient))
        self.current_patient = {}
        self.current_companion = {}
        self.patient_index += 1

    def add_companion_to_current(self, companion: dict) -> None:
        self.current_patient.setdefault("companions", [])
        self.current_patient["companions"].append(dict(companion))

    @property
    def patients_done(self) -> bool:
        return self.patient_index >= self.patient_count
