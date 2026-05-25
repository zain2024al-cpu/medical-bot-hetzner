# modules/general_services/public_services/session.py

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

_SESSION_KEY = "_gspub_add"

# ── Steps ─────────────────────────────────────────────────────────────────────
STEP_DATE         = "date"
STEP_DATE_CUSTOM  = "date_custom"
STEP_PATIENT      = "patient"
STEP_SERVICE_TYPE = "service_type"
STEP_COUNT        = "count"
STEP_IMAGES       = "images"
STEP_NOTES        = "notes"
STEP_SPECIALIST   = "specialist"
STEP_REVIEW       = "review"


@dataclass
class PublicServiceSession:
    step:                 str
    created_at:           str
    patient_id:           Optional[int]
    patient_name:         str
    service_type_labels:  list[str]
    item_count:           int
    images:               list[dict]
    notes:                str
    specialist_id:        str
    specialist_label:     str
    edit_from_review:     bool

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, user_data: dict) -> None:
        user_data[_SESSION_KEY] = {
            "step":                self.step,
            "created_at":          self.created_at,
            "patient_id":          self.patient_id,
            "patient_name":        self.patient_name,
            "service_type_labels": self.service_type_labels,
            "item_count":          self.item_count,
            "images":              self.images,
            "notes":               self.notes,
            "specialist_id":       self.specialist_id,
            "specialist_label":    self.specialist_label,
            "edit_from_review":    self.edit_from_review,
        }

    @classmethod
    def load(cls, user_data: dict) -> PublicServiceSession | None:
        raw = user_data.get(_SESSION_KEY)
        if not raw:
            return None
        return cls(
            step=                raw.get("step",                STEP_DATE),
            created_at=          raw.get("created_at",          datetime.utcnow().isoformat()),
            patient_id=          raw.get("patient_id",          None),
            patient_name=        raw.get("patient_name",        ""),
            service_type_labels= raw.get("service_type_labels", []),
            item_count=          raw.get("item_count",          0),
            images=              raw.get("images",              []),
            notes=               raw.get("notes",               ""),
            specialist_id=       raw.get("specialist_id",       ""),
            specialist_label=    raw.get("specialist_label",    ""),
            edit_from_review=    raw.get("edit_from_review",    False),
        )

    @classmethod
    def create(cls, user_data: dict) -> PublicServiceSession:
        session = cls(
            step=                STEP_DATE,
            created_at=          datetime.utcnow().isoformat(),
            patient_id=          None,
            patient_name=        "",
            service_type_labels= [],
            item_count=          0,
            images=              [],
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
