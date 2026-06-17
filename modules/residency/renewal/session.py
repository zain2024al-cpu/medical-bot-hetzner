# modules/residency/renewal/session.py
# Session for the Renewal (issuance) flow.

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

_SESSION_KEY = "_res_ren"

# ── Steps ─────────────────────────────────────────────────────────────────────
STEP_EXPIRY_DATE          = "expiry_date"          # calendar: new expiry
STEP_RESIDENCY_NUMBER     = "residency_number"      # text: new residency number (skippable)
STEP_DOCUMENT             = "document"              # uploads: new residency doc
STEP_COMPANIONS           = "companions"            # ask: any companions to update?
STEP_C_EXPIRY_DATE        = "c_expiry_date"        # calendar: companion new expiry
STEP_C_RESIDENCY_NUMBER   = "c_residency_number"   # text: companion residency number (skippable)
STEP_C_DOCUMENT           = "c_document"           # uploads: companion residency doc
STEP_NOTES                = "notes"                # text, skippable
STEP_REVIEW               = "review"


@dataclass
class RenewalSession:
    step:                str
    profile_id:          int
    profile_name:        str
    new_expiry_date:     str             # ISO date YYYY-MM-DD
    new_residency_number: str            # Residency number issued for the main patient
    document_file_id:    str             # Telegram file_id for new residency doc
    # Companion renewal loop
    companions:          list[dict]      # [{id, name, status, expiry_date}, …] loaded from DB
    companion_index:     int             # current companion being processed
    completed_companions: list[dict]     # finished: [{id, new_expiry, file_id, skipped, residency_number}, …]
    # Extra
    notes:               str
    companions_only:     bool = False    # True when opened for companion-completion only

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, user_data: dict) -> None:
        user_data[_SESSION_KEY] = {
            "step":                   self.step,
            "profile_id":             self.profile_id,
            "profile_name":           self.profile_name,
            "new_expiry_date":        self.new_expiry_date,
            "new_residency_number":   self.new_residency_number,
            "document_file_id":       self.document_file_id,
            "companions":             self.companions,
            "companion_index":        self.companion_index,
            "completed_companions":   self.completed_companions,
            "notes":                  self.notes,
            "companions_only":        self.companions_only,
        }
        logger.debug(f"[RenewalSession.save] step={self.step!r}  profile={self.profile_id}")

    @classmethod
    def load(cls, user_data: dict) -> RenewalSession | None:
        raw = user_data.get(_SESSION_KEY)
        if not raw:
            return None
        return cls(
            step=                   raw.get("step",                  STEP_EXPIRY_DATE),
            profile_id=             raw.get("profile_id",            0),
            profile_name=           raw.get("profile_name",          ""),
            new_expiry_date=        raw.get("new_expiry_date",       ""),
            new_residency_number=   raw.get("new_residency_number",  ""),
            document_file_id=       raw.get("document_file_id",      ""),
            companions=             raw.get("companions",             []),
            companion_index=        raw.get("companion_index",       0),
            completed_companions=   raw.get("completed_companions",   []),
            notes=                  raw.get("notes",                 ""),
            companions_only=        raw.get("companions_only",       False),
        )

    @classmethod
    def create(
        cls,
        user_data: dict,
        profile_id: int,
        profile_name: str,
        companions: list[dict],
        companions_only: bool = False,
    ) -> RenewalSession:
        start_step = STEP_COMPANIONS if companions_only else STEP_EXPIRY_DATE
        session = cls(
            step=                  start_step,
            profile_id=            profile_id,
            profile_name=          profile_name,
            new_expiry_date=       "",
            new_residency_number=  "",
            document_file_id=      "",
            companions=            companions,
            companion_index=       0,
            completed_companions=  [],
            notes=                 "",
            companions_only=       companions_only,
        )
        session.save(user_data)
        return session

    @classmethod
    def clear(cls, user_data: dict) -> None:
        user_data.pop(_SESSION_KEY, None)
        user_data.pop("_rnr_complete_companions", None)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @property
    def current_companion(self) -> dict | None:
        if self.companion_index < len(self.companions):
            return self.companions[self.companion_index]
        return None

    @property
    def companions_done(self) -> bool:
        return self.companion_index >= len(self.companions)

    def finish_current_companion(
        self,
        new_expiry:       str,
        file_id:          str,
        skipped:          bool = False,
        residency_number: str  = "",
    ) -> None:
        c = self.current_companion
        if c is None:
            return
        self.completed_companions.append({
            "id":               c["id"],
            "name":             c["name"],
            "new_expiry":       new_expiry,
            "file_id":          file_id,
            "skipped":          skipped,
            "residency_number": residency_number,
        })
        self.companion_index += 1
