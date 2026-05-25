# modules/general_services/arrivals/repository.py
# Read/write queries for the arrivals archive.
# Used by the departure selector to list active arrivals and mark departures.

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ActiveArrivalEntry:
    patient_id:      int
    patient_name:    str
    companion_count: int
    companion_names: list[str] = field(default_factory=list)

    @property
    def display_label(self) -> str:
        if self.companion_count == 0:
            return self.patient_name
        return f"{self.patient_name} (+ {self.companion_count} مرافق)"


def get_active_arrivals() -> list[ActiveArrivalEntry]:
    """Return all patients with arrival_status='active' (or NULL) plus their companions."""
    from db.session import get_db
    from db.models import ArrivalPatient, ArrivalCompanion
    from sqlalchemy import or_

    with get_db() as db:
        patients = (
            db.query(ArrivalPatient)
            .filter(
                or_(
                    ArrivalPatient.arrival_status == "active",
                    ArrivalPatient.arrival_status.is_(None),
                )
            )
            .order_by(ArrivalPatient.id.asc())
            .all()
        )

        result = []
        for p in patients:
            companions = (
                db.query(ArrivalCompanion)
                .filter(ArrivalCompanion.patient_id == p.id)
                .order_by(ArrivalCompanion.id.asc())
                .all()
            )
            result.append(ActiveArrivalEntry(
                patient_id=      p.id,
                patient_name=    p.name or "—",
                companion_count= len(companions),
                companion_names= [c.name or "—" for c in companions],
            ))

    logger.debug(f"[arrivals.repository] get_active_arrivals → {len(result)} entries")
    return result


def expand_patient_ids_to_names(patient_ids: list[int]) -> list[str]:
    """
    For each patient_id return the patient name followed by all companion names.
    Result is a flat ordered list:
      [patient_A, companion_A1, companion_A2, patient_B, companion_B1, ...]
    """
    if not patient_ids:
        return []

    from db.session import get_db
    from db.models import ArrivalPatient, ArrivalCompanion

    names: list[str] = []
    with get_db() as db:
        for pid in patient_ids:
            patient = db.query(ArrivalPatient).filter(ArrivalPatient.id == pid).first()
            if patient is None:
                continue
            names.append(patient.name or "—")
            companions = (
                db.query(ArrivalCompanion)
                .filter(ArrivalCompanion.patient_id == pid)
                .order_by(ArrivalCompanion.id.asc())
                .all()
            )
            names.extend(c.name or "—" for c in companions)

    return names


def mark_patients_departed(patient_ids: list[int], departure_record_id: int) -> None:
    """Mark arrival patients as departed and store the departure record link."""
    if not patient_ids:
        return

    from db.session import get_db
    from db.models import ArrivalPatient

    with get_db() as db:
        db.query(ArrivalPatient).filter(
            ArrivalPatient.id.in_(patient_ids)
        ).update(
            {
                "arrival_status":      "departed",
                "departure_record_id": departure_record_id,
            },
            synchronize_session=False,
        )

    logger.info(
        f"[arrivals.repository] marked departed"
        f"  patient_ids={patient_ids}  departure_record_id={departure_record_id}"
    )
