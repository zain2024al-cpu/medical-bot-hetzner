# modules/healthcare/evaluation/repository.py
# Data access layer: fetch all records for a specialist within a date range.

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, date

logger = logging.getLogger(__name__)


# ── Value objects ─────────────────────────────────────────────────────────────

@dataclass
class CaseRow:
    """Unified row across all healthcare sub-modules."""
    record_id:    int
    service_type: str          # "woundcare" | "followup" | "medications" | "supplies"
    service_label: str         # Arabic label
    patient_name: str
    departments:  list[str]    # parsed from medical_departments_json
    detail:       str          # operation / procedure / dispense_source / etc.
    image_count:  int
    created_at:   datetime
    specialist_name: str = ""  # ✅ يُملأ دائماً — يُستخدم لتوزيع "حسب الصحي" في التقرير الشامل


@dataclass
class EvaluationData:
    """All data required to render the PDF report."""
    specialist_name: str
    period_start:    date
    period_end:      date
    generated_at:    datetime

    # Summary counts
    total_cases:      int = 0
    woundcare_count:  int = 0
    followup_count:   int = 0
    medication_count: int = 0
    supplies_count:   int = 0

    # Documentation
    cases_with_images:    int = 0
    cases_without_images: int = 0
    total_images:         int = 0

    # Departments: {label: count}
    department_counts: dict[str, int] = field(default_factory=dict)

    # Activity
    active_days:    int = 0
    first_case_dt:  datetime | None = None
    last_case_dt:   datetime | None = None
    cases_by_date:  dict[str, int] = field(default_factory=dict)   # "YYYY-MM-DD": count
    cases_by_weekday: dict[str, int] = field(default_factory=dict) # "الأحد": count

    # Unique patients
    unique_patients: int = 0
    repeat_patients: int = 0

    # Woundcare phase distribution
    phase_counts: dict[str, int] = field(default_factory=dict)

    # Medication dispense source
    dispense_source_counts: dict[str, int] = field(default_factory=dict)

    # ✅ توزيع الحالات حسب الصحي — يُملأ ذا معنى فقط في التقرير الشامل
    # (عندما specialist_name=None عند الاستدعاء). في تقرير صحي فردي يحتوي
    # دائماً على عنصر واحد فقط، فتُخفى هذه الفقرة في الـ PDF تلقائياً.
    specialist_counts: dict[str, int] = field(default_factory=dict)

    # Full case rows for detail table
    cases: list[CaseRow] = field(default_factory=list)


# ── Constants ─────────────────────────────────────────────────────────────────

_WEEKDAYS_AR = {
    0: "الاثنين", 1: "الثلاثاء", 2: "الأربعاء",
    3: "الخميس",  4: "الجمعة",   5: "السبت", 6: "الأحد",
}

_SERVICE_LABELS = {
    "woundcare":   "مجارحة",
    "followup":    "معاينة",
    "medications": "صيدلية",
    "supplies":    "مستلزمات",
}


# ── Public API ────────────────────────────────────────────────────────────────

_ALL_SPECIALISTS_LABEL = "جميع الصحيين"


def get_evaluation_data(
    specialist_name: str | None,
    period_start:    date,
    period_end:      date,
) -> EvaluationData:
    """
    Query records within [period_start, period_end].

    ✅ specialist_name=None → التقرير الشامل: يجمع سجلات كل الصحيين معاً
    (بدون فلترة بالاسم) ويملأ data.specialist_counts بتوزيع الحالات حسب
    كل صحي. specialist_name="اسم" → السلوك الأصلي (تقرير فردي).

    Returns a fully-populated EvaluationData ready for PDF rendering.
    """
    from db.session import get_db
    from db.models import (
        WoundRecord, MedicationRecord,
        MedicalFollowupRecord, SuppliesRecord,
        OtherHealthcareRecord,
    )

    is_comprehensive = specialist_name is None

    data = EvaluationData(
        specialist_name=_ALL_SPECIALISTS_LABEL if is_comprehensive else specialist_name,
        period_start=period_start,
        period_end=period_end,
        generated_at=datetime.utcnow(),
    )

    dt_start = datetime.combine(period_start, datetime.min.time())
    dt_end   = datetime.combine(period_end,   datetime.max.time())

    rows: list[CaseRow] = []

    def _spec_filter(Model):
        """شرط الفلترة بالصحي — فارغ (بدون فلترة) في وضع التقرير الشامل."""
        if is_comprehensive:
            return []
        return [Model.specialist_name == specialist_name]

    with get_db() as db:
        # ── WoundRecord ───────────────────────────────────────────────────────
        wound_qs = (
            db.query(WoundRecord)
            .filter(
                *_spec_filter(WoundRecord),
                WoundRecord.created_at >= dt_start,
                WoundRecord.created_at <= dt_end,
            )
            .order_by(WoundRecord.created_at.asc())
            .all()
        )
        for r in wound_qs:
            rows.append(CaseRow(
                record_id=    r.id,
                service_type= "woundcare",
                service_label="مجارحة",
                patient_name= r.patient_name or "—",
                departments=  _parse_json_list(r.medical_departments_json),
                detail=       r.phase_label or "—",
                image_count=  r.image_count or 0,
                created_at=   r.created_at,
                specialist_name= r.specialist_name or "—",
            ))
            # Phase distribution
            if r.phase_label:
                data.phase_counts[r.phase_label] = data.phase_counts.get(r.phase_label, 0) + 1

        # ── MedicationRecord ──────────────────────────────────────────────────
        med_qs = (
            db.query(MedicationRecord)
            .filter(
                *_spec_filter(MedicationRecord),
                MedicationRecord.created_at >= dt_start,
                MedicationRecord.created_at <= dt_end,
            )
            .order_by(MedicationRecord.created_at.asc())
            .all()
        )
        for r in med_qs:
            rows.append(CaseRow(
                record_id=    r.id,
                service_type= "medications",
                service_label="صيدلية",
                patient_name= r.patient_name or "—",
                departments=  _parse_json_list(r.medical_departments_json),
                detail=       r.dispense_source or "—",
                image_count=  r.image_count or 0,
                created_at=   r.created_at,
                specialist_name= r.specialist_name or "—",
            ))
            if r.dispense_source:
                src = r.dispense_source
                data.dispense_source_counts[src] = data.dispense_source_counts.get(src, 0) + 1

        # ── MedicalFollowupRecord (medical followup) ──────────────────────────────
        try:
            exam_qs = (
                db.query(MedicalFollowupRecord)
                .filter(
                    *_spec_filter(MedicalFollowupRecord),
                    MedicalFollowupRecord.created_at >= dt_start,
                    MedicalFollowupRecord.created_at <= dt_end,
                )
                .order_by(MedicalFollowupRecord.created_at.asc())
                .all()
            )
            for r in exam_qs:
                rows.append(CaseRow(
                    record_id=    r.id,
                    service_type= "followup",
                    service_label="معاينة",
                    patient_name= r.patient_name or "—",
                    departments=  _parse_json_list(r.medical_departments_json),
                    detail=       _parse_json_list(r.procedure_type_json, limit=1),
                    image_count=  r.image_count or 0,
                    created_at=   r.created_at,
                    specialist_name= r.specialist_name or "—",
                ))
        except Exception as exc:
            logger.warning(f"[evaluation.repo] MedicalFollowupRecord query failed: {exc}")

        # ── SuppliesRecord ────────────────────────────────────────────────────
        sup_qs = (
            db.query(SuppliesRecord)
            .filter(
                *_spec_filter(SuppliesRecord),
                SuppliesRecord.created_at >= dt_start,
                SuppliesRecord.created_at <= dt_end,
            )
            .order_by(SuppliesRecord.created_at.asc())
            .all()
        )
        for r in sup_qs:
            rows.append(CaseRow(
                record_id=    r.id,
                service_type= "supplies",
                service_label="مستلزمات",
                patient_name= r.patient_name or "—",
                departments=  _parse_json_list(r.medical_departments_json),
                detail=       _item_count_detail(r.item_count),
                image_count=  r.image_count or 0,
                created_at=   r.created_at,
                specialist_name= r.specialist_name or "—",
            ))

        # ── OtherHealthcareRecord ─────────────────────────────────────────────
        try:
            other_qs = (
                db.query(OtherHealthcareRecord)
                .filter(
                    *_spec_filter(OtherHealthcareRecord),
                    OtherHealthcareRecord.created_at >= dt_start,
                    OtherHealthcareRecord.created_at <= dt_end,
                )
                .order_by(OtherHealthcareRecord.created_at.asc())
                .all()
            )
            for r in other_qs:
                rows.append(CaseRow(
                    record_id=    r.id,
                    service_type= "other",
                    service_label="إجراء صحي",
                    patient_name= r.patient_name or "—",
                    departments=  _parse_json_list(getattr(r, "medical_departments_json", None)),
                    detail=       "—",
                    image_count=  r.image_count or 0,
                    created_at=   r.created_at,
                    specialist_name= r.specialist_name or "—",
                ))
        except Exception as exc:
            logger.warning(f"[evaluation.repo] OtherHealthcareRecord query failed: {exc}")

    # Sort all rows chronologically
    rows.sort(key=lambda r: r.created_at)
    data.cases = rows

    # ── Aggregate ─────────────────────────────────────────────────────────────
    _aggregate(data, rows)
    return data


# ── Internal helpers ──────────────────────────────────────────────────────────

def _parse_json_list(raw: str | None, limit: int = 0) -> list[str] | str:
    """Parse a JSON-encoded list field. Returns list (or first element if limit=1)."""
    if not raw:
        return [] if limit != 1 else "—"
    try:
        lst = json.loads(raw)
        if not isinstance(lst, list):
            return [] if limit != 1 else str(lst)
        if limit == 1:
            return lst[0] if lst else "—"
        return lst
    except Exception:
        return [] if limit != 1 else raw


def _item_count_detail(item_count) -> str:
    """
    عرض "عدد الأصناف" في جدول تفاصيل الحالات. الحقل أصبح نصاً حراً (رقم أو وصف)،
    فقيمة رقمية بحتة تُعرض بنفس الصياغة القديمة، والنص الحر يُعرض كما هو.
    """
    val = str(item_count if item_count is not None else "").strip()
    if val.isdigit():
        return f"{val} صنف"
    return val or "—"


def _aggregate(data: EvaluationData, rows: list[CaseRow]) -> None:
    """Populate all aggregate fields from the case rows."""
    if not rows:
        return

    date_set: set[str]         = set()
    patient_map: dict[str, int] = {}

    for row in rows:
        # Service counts
        if row.service_type == "woundcare":
            data.woundcare_count += 1
        elif row.service_type == "followup":
            data.followup_count += 1
        elif row.service_type == "medications":
            data.medication_count += 1
        elif row.service_type == "supplies":
            data.supplies_count += 1

        # Documentation
        if row.image_count > 0:
            data.cases_with_images += 1
        else:
            data.cases_without_images += 1
        data.total_images += row.image_count

        # Departments
        for dept in row.departments:
            if dept:
                data.department_counts[dept] = data.department_counts.get(dept, 0) + 1

        # ✅ توزيع حسب الصحي (ذو معنى فقط في التقرير الشامل — سيحتوي على
        # عنصر واحد فقط في تقرير فردي، وتُخفى هذه الفقرة عندها في الـ PDF)
        if row.specialist_name and row.specialist_name != "—":
            data.specialist_counts[row.specialist_name] = data.specialist_counts.get(row.specialist_name, 0) + 1

        # Activity
        if row.created_at:
            day_str = row.created_at.strftime("%Y-%m-%d")
            date_set.add(day_str)
            data.cases_by_date[day_str] = data.cases_by_date.get(day_str, 0) + 1
            wd = _WEEKDAYS_AR.get(row.created_at.weekday(), "")
            if wd:
                data.cases_by_weekday[wd] = data.cases_by_weekday.get(wd, 0) + 1

        # Unique patients
        pname = (row.patient_name or "").strip()
        if pname and pname != "—":
            patient_map[pname] = patient_map.get(pname, 0) + 1

    data.total_cases    = len(rows)
    data.active_days    = len(date_set)
    data.first_case_dt  = rows[0].created_at  if rows else None
    data.last_case_dt   = rows[-1].created_at if rows else None
    data.unique_patients = len(patient_map)
    data.repeat_patients = sum(1 for c in patient_map.values() if c > 1)

    # Sort department_counts descending
    data.department_counts = dict(
        sorted(data.department_counts.items(), key=lambda x: x[1], reverse=True)
    )

    # Sort specialist_counts descending
    data.specialist_counts = dict(
        sorted(data.specialist_counts.items(), key=lambda x: x[1], reverse=True)
    )


def list_specialist_names() -> list[str]:
    """Return all distinct specialist names found across ALL five healthcare tables."""
    from db.session import get_db
    from db.models import (
        WoundRecord, MedicationRecord, SuppliesRecord,
        MedicalFollowupRecord, OtherHealthcareRecord,
    )

    names: set[str] = set()
    with get_db() as db:
        for Model in (
            WoundRecord, MedicationRecord, SuppliesRecord,
            MedicalFollowupRecord, OtherHealthcareRecord,
        ):
            try:
                rows = (
                    db.query(Model.specialist_name)
                    .filter(
                        Model.specialist_name.isnot(None),
                        Model.specialist_name != "",
                    )
                    .distinct()
                    .all()
                )
                for (name,) in rows:
                    if name and name.strip():
                        names.add(name.strip())
            except Exception as exc:
                logger.debug(
                    f"[evaluation.repo] list_specialist_names"
                    f"  skip {getattr(Model, '__tablename__', str(Model))}: {exc}"
                )

    return sorted(names)
