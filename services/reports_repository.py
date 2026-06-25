# services/reports_repository.py
# Shared database queries for comprehensive and patient reports.
#
# Functions:
#   - get_patients_by_name(query) → list[dict]
#   - get_reports(start, end, patient_id=None, depts=None, actions=None) → list[dict]
#   - aggregate_by_hospital(reports) → dict
#   - aggregate_by_department(reports) → dict
#   - aggregate_by_action(reports) → dict
#   - aggregate_by_date(reports) → dict
#   - get_all_departments() → list[str]
#   - get_all_actions() → list[str]

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)


# ── Async wrappers ────────────────────────────────────────────────────────────

async def get_patients_by_name(query_text: str) -> list[dict]:
    """Search patients by name. Returns {id, name, file_number}."""
    return await asyncio.to_thread(_get_patients_sync, query_text)


async def get_reports(
    start: date,
    end: date,
    patient_id: Optional[int] = None,
    depts: Optional[list[str]] = None,
    actions: Optional[list[str]] = None,
) -> list[dict]:
    """Fetch reports. Optional filtering by patient, departments, actions."""
    return await asyncio.to_thread(
        _get_reports_sync, start, end, patient_id, depts, actions
    )


# ── Sync implementations ──────────────────────────────────────────────────────

def _get_patients_sync(query_text: str) -> list[dict]:
    """Search patients by name fragment."""
    from db.session import SessionLocal
    from db.models import Patient
    from sqlalchemy import func

    results = []
    q = query_text.strip().lower() if query_text else ""

    try:
        with SessionLocal() as s:
            try:
                patients = (
                    s.query(Patient)
                    .filter(func.lower(Patient.full_name).contains(q) | func.lower(Patient.name).contains(q))
                    .order_by(Patient.full_name)
                    .limit(50)
                    .all()
                )
                for p in patients:
                    results.append({
                        "id": p.id,
                        "name": p.full_name or p.name or "—",
                        "file_number": getattr(p, "file_number", "") or "",
                    })
            except Exception:
                # Fallback: search in reports.patient_name
                from db.models import Report
                rows = (
                    s.query(Report.patient_id, Report.patient_name)
                    .filter(
                        (func.lower(Report.patient_name).contains(q)) &
                        (Report.patient_name.isnot(None)) &
                        (Report.patient_id.isnot(None))
                    )
                    .distinct()
                    .order_by(Report.patient_name)
                    .limit(50)
                    .all()
                )
                for row in rows:
                    results.append({
                        "id": row.patient_id or 0,
                        "name": row.patient_name or "—",
                        "file_number": "",
                    })
    except Exception as exc:
        logger.error(f"[reports_repo] get_patients_sync failed: {exc}", exc_info=True)

    return results


def _get_reports_sync(
    start: date,
    end: date,
    patient_id: Optional[int] = None,
    depts: Optional[list[str]] = None,
    actions: Optional[list[str]] = None,
) -> list[dict]:
    """Fetch reports with optional filtering."""
    from db.session import SessionLocal
    from db.models import Report

    results = []
    try:
        with SessionLocal() as s:
            q = s.query(Report).filter(
                Report.report_date >= start,
                Report.report_date <= end,
            )

            if patient_id:
                q = q.filter(Report.patient_id == patient_id)

            if depts:
                q = q.filter(Report.department.in_(depts))

            if actions:
                q = q.filter(Report.medical_action.in_(actions))

            rows = q.order_by(Report.report_date.asc()).all()

            for r in rows:
                results.append({
                    "id":              r.id,
                    "patient_id":      r.patient_id,
                    "patient_name":    r.patient_name or "",
                    "patient_file":    r.patient_file_number or "",
                    "hospital_id":     r.hospital_id,
                    "hospital_name":   r.hospital_name or "",
                    "department":      r.department or "",
                    "doctor_name":     r.doctor_name or "",
                    "medical_action":  r.medical_action or "",
                    "complaint_text":  r.complaint_text or "",
                    "doctor_decision": r.doctor_decision or "",
                    "translator_name": r.translator_name or "",
                    "report_date":     r.report_date.date() if r.report_date else None,
                    "visit_date":      r.visit_date.date() if r.visit_date else None,
                    "followup_date":   (r.followup_date.date() if r.followup_date else None),
                    "diagnosis":       r.diagnosis or "",
                    "treatment_plan":  r.treatment_plan or "",
                })
    except Exception as exc:
        logger.error(f"[reports_repo] get_reports_sync failed: {exc}", exc_info=True)

    return results


def get_all_departments() -> list[str]:
    """Get all unique departments from reports."""
    from db.session import SessionLocal
    from db.models import Report

    try:
        with SessionLocal() as s:
            depts = (
                s.query(Report.department)
                .filter(Report.department.isnot(None), Report.department != "")
                .distinct()
                .order_by(Report.department)
                .all()
            )
            return [d[0] for d in depts if d[0]]
    except Exception as exc:
        logger.error(f"[reports_repo] get_all_departments failed: {exc}", exc_info=True)
        return []


def get_all_actions() -> list[str]:
    """Get all unique action types from reports."""
    from db.session import SessionLocal
    from db.models import Report

    try:
        with SessionLocal() as s:
            actions = (
                s.query(Report.medical_action)
                .filter(Report.medical_action.isnot(None), Report.medical_action != "")
                .distinct()
                .order_by(Report.medical_action)
                .all()
            )
            return [a[0] for a in actions if a[0]]
    except Exception as exc:
        logger.error(f"[reports_repo] get_all_actions failed: {exc}", exc_info=True)
        return []


# ── Aggregation functions ─────────────────────────────────────────────────────

def aggregate_by_hospital(reports: list[dict]) -> dict[str, int]:
    """Returns {hospital_name: count}."""
    agg: dict[str, int] = defaultdict(int)
    for r in reports:
        h = (r.get("hospital_name") or "—").strip()
        if h:
            agg[h] += 1
    return dict(sorted(agg.items(), key=lambda x: -x[1]))


def aggregate_by_department(reports: list[dict]) -> dict[str, int]:
    """Returns {department: count}."""
    agg: dict[str, int] = defaultdict(int)
    for r in reports:
        d = (r.get("department") or "—").strip()
        if d:
            agg[d] += 1
    return dict(sorted(agg.items(), key=lambda x: -x[1]))


def aggregate_by_action(reports: list[dict]) -> dict[str, int]:
    """Returns {action: count}."""
    agg: dict[str, int] = defaultdict(int)
    for r in reports:
        a = (r.get("medical_action") or "غير محدد").strip()
        agg[a] += 1
    return dict(sorted(agg.items(), key=lambda x: -x[1]))


def aggregate_by_date(reports: list[dict]) -> dict[date, int]:
    """Returns {date: count}."""
    agg: dict[date, int] = defaultdict(int)
    for r in reports:
        d = r.get("report_date")
        if d:
            agg[d] += 1
    return dict(sorted(agg.items()))


def aggregate_by_translator(reports: list[dict]) -> dict[str, int]:
    """Returns {translator_name: count}."""
    agg: dict[str, int] = defaultdict(int)
    for r in reports:
        t = (r.get("translator_name") or "—").strip()
        if t:
            agg[t] += 1
    return dict(sorted(agg.items(), key=lambda x: -x[1]))


# ── Statistics ────────────────────────────────────────────────────────────────

def compute_stats(reports: list[dict]) -> dict:
    """Compute summary statistics."""
    if not reports:
        return {
            "total": 0,
            "unique_patients": 0,
            "unique_hospitals": 0,
            "unique_depts": 0,
            "unique_actions": 0,
            "unique_translators": 0,
        }

    patients = {r.get("patient_id") for r in reports if r.get("patient_id")}
    hospitals = {r.get("hospital_name") for r in reports if r.get("hospital_name")}
    depts = {r.get("department") for r in reports if r.get("department")}
    actions = {r.get("medical_action") for r in reports if r.get("medical_action")}
    translators = {r.get("translator_name") for r in reports if r.get("translator_name")}

    dates = [r.get("report_date") for r in reports if r.get("report_date")]
    first_dt = min(dates) if dates else None
    last_dt = max(dates) if dates else None

    return {
        "total": len(reports),
        "unique_patients": len(patients),
        "unique_hospitals": len(hospitals),
        "unique_depts": len(depts),
        "unique_actions": len(actions),
        "unique_translators": len(translators),
        "first_date": first_dt,
        "last_date": last_dt,
    }
