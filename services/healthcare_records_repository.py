# services/healthcare_records_repository.py
# يجمع سجلات وحدة الرعاية الصحية (المجارحة/المتابعة الطبية/الأدوية/
# المستلزمات/إجراءات أخرى) الخاصة بمريض محدَّد ضمن فترة زمنية — تُستخدَم
# لإضافة قسم "سجلات الرعاية الصحية" داخل تقرير المريض (services/patient_report_pdf.py).
#
# ✅ الجداول الخمسة (db/models.py) لا تحمل ForeignKey على patient_id (نفس نمط
# Report.patient_id في كل المشروع) — الربط بمريض محدَّد عبر القيمة فقط، وليس
# عبر قيد قاعدة بيانات.

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime
from typing import Optional

logger = logging.getLogger(__name__)

# نوع → (تسمية عربية للعرض، أيقونة)
# ✅ بلا إيموجي عمداً: تُستخدَم هذه التسميات داخل ملف PDF (services/patient_report_pdf.py)
# وخطوط PDF المستخدَمة هناك (Tahoma/Arial/الخط العربي المضمَّن) لا تحتوي
# غالب رموز الإيموجي الطبية، فتظهر كمربعات فارغة (tofu) بدل الرمز.
_TYPE_LABELS = {
    "woundcare": "المجارحة والعناية بالجرح",
    "followup":  "المتابعة الطبية والإجراءات العلاجية",
    "medication": "صرف الأدوية",
    "supplies":  "المستلزمات الطبية",
    "other":     "إجراءات صحية أخرى",
}


def _json_labels(raw: Optional[str]) -> str:
    """يحوّل حقل JSON (قائمة تسميات) إلى نص مفصول بفواصل للعرض. يتجاهل أي
    خطأ تحليل بصمت (بيانات تالفة/فارغة) ويعيد نصاً فارغاً بدلاً من رفع استثناء —
    هذا الحقل عرضي فقط في تقرير المريض، فلا يجوز أن يُسقط بناء التقرير كاملاً."""
    if not raw:
        return ""
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return "، ".join(str(x) for x in parsed if x)
    except Exception:
        pass
    return ""


async def get_healthcare_records_for_patient(
    patient_id: int, start: date, end: date
) -> list[dict]:
    """سجلات الرعاية الصحية الخمسة لمريض ضمن فترة، بشكل موحَّد جاهز للعرض:
    [{"type": str, "type_label": str, "date": date, "department": str,
      "description": str, "specialist_name": str, "notes": str}, ...]
    مُرتَّبة زمنياً تصاعدياً (نفس ترتيب تقارير المترجم في نفس التقرير)."""
    return await asyncio.to_thread(_get_healthcare_records_sync, patient_id, start, end)


def _get_healthcare_records_sync(patient_id: int, start: date, end: date) -> list[dict]:
    from db.session import SessionLocal
    from db.models import (
        WoundRecord, MedicalFollowupRecord, MedicationRecord,
        SuppliesRecord, OtherHealthcareRecord,
    )

    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())

    results: list[dict] = []
    try:
        with SessionLocal() as s:
            # ── المجارحة والعناية بالجرح ──────────────────────────────────
            for r in (
                s.query(WoundRecord)
                .filter(
                    WoundRecord.patient_id == patient_id,
                    WoundRecord.created_at >= start_dt,
                    WoundRecord.created_at <= end_dt,
                )
                .all()
            ):
                desc_parts = []
                if r.operation_name:
                    desc_parts.append(f"العملية: {r.operation_name}")
                if r.phase_label:
                    desc_parts.append(f"المرحلة: {r.phase_label}")
                if r.condition_description:
                    desc_parts.append(r.condition_description)
                results.append({
                    "type": "woundcare",
                    "type_label": _TYPE_LABELS["woundcare"],
                    "date": r.created_at.date() if r.created_at else None,
                    "department": _json_labels(r.medical_departments_json),
                    "description": "\n".join(desc_parts) or "—",
                    "specialist_name": r.specialist_name or "—",
                    "notes": r.notes or "",
                })

            # ── المتابعة الطبية والإجراءات العلاجية ──────────────────────
            for r in (
                s.query(MedicalFollowupRecord)
                .filter(
                    MedicalFollowupRecord.patient_id == patient_id,
                    MedicalFollowupRecord.created_at >= start_dt,
                    MedicalFollowupRecord.created_at <= end_dt,
                )
                .all()
            ):
                desc_parts = []
                proc = _json_labels(r.procedure_type_json)
                if proc:
                    desc_parts.append(f"نوع الإجراء: {proc}")
                complaint = _json_labels(r.complaint_labels_json)
                if complaint:
                    desc_parts.append(f"الشكوى: {complaint}")
                vitals = []
                if r.vitals_temp:
                    vitals.append(f"حرارة {r.vitals_temp}")
                if r.vitals_bp:
                    vitals.append(f"ضغط {r.vitals_bp}")
                if r.vitals_pulse:
                    vitals.append(f"نبض {r.vitals_pulse}")
                if r.vitals_spo2:
                    vitals.append(f"SpO2 {r.vitals_spo2}")
                if vitals:
                    desc_parts.append("العلامات الحيوية: " + "، ".join(vitals))
                results.append({
                    "type": "followup",
                    "type_label": _TYPE_LABELS["followup"],
                    "date": r.created_at.date() if r.created_at else None,
                    "department": _json_labels(r.medical_departments_json),
                    "description": "\n".join(desc_parts) or "—",
                    "specialist_name": r.specialist_name or "—",
                    "notes": r.notes or "",
                })

            # ── صرف الأدوية ───────────────────────────────────────────────
            for r in (
                s.query(MedicationRecord)
                .filter(
                    MedicationRecord.patient_id == patient_id,
                    MedicationRecord.created_at >= start_dt,
                    MedicationRecord.created_at <= end_dt,
                )
                .all()
            ):
                desc_parts = []
                if r.item_count:
                    desc_parts.append(f"الأصناف: {r.item_count}")
                if r.dispense_source:
                    desc_parts.append(f"جهة الصرف: {r.dispense_source}")
                results.append({
                    "type": "medication",
                    "type_label": _TYPE_LABELS["medication"],
                    "date": r.created_at.date() if r.created_at else None,
                    "department": _json_labels(r.medical_departments_json),
                    "description": "\n".join(desc_parts) or "—",
                    "specialist_name": r.specialist_name or "—",
                    "notes": r.notes or "",
                })

            # ── المستلزمات الطبية ─────────────────────────────────────────
            for r in (
                s.query(SuppliesRecord)
                .filter(
                    SuppliesRecord.patient_id == patient_id,
                    SuppliesRecord.created_at >= start_dt,
                    SuppliesRecord.created_at <= end_dt,
                )
                .all()
            ):
                desc_parts = []
                if r.item_count:
                    desc_parts.append(f"الأصناف: {r.item_count}")
                if r.dispense_source:
                    desc_parts.append(f"جهة الصرف: {r.dispense_source}")
                results.append({
                    "type": "supplies",
                    "type_label": _TYPE_LABELS["supplies"],
                    "date": r.created_at.date() if r.created_at else None,
                    "department": _json_labels(r.medical_departments_json),
                    "description": "\n".join(desc_parts) or "—",
                    "specialist_name": r.specialist_name or "—",
                    "notes": r.notes or "",
                })

            # ── إجراءات صحية أخرى ─────────────────────────────────────────
            for r in (
                s.query(OtherHealthcareRecord)
                .filter(
                    OtherHealthcareRecord.patient_id == patient_id,
                    OtherHealthcareRecord.created_at >= start_dt,
                    OtherHealthcareRecord.created_at <= end_dt,
                )
                .all()
            ):
                results.append({
                    "type": "other",
                    "type_label": _TYPE_LABELS["other"],
                    "date": r.created_at.date() if r.created_at else None,
                    "department": "",
                    "description": _json_labels(r.action_labels) or "—",
                    "specialist_name": r.specialist_name or "—",
                    "notes": r.notes or "",
                })
    except Exception as exc:
        logger.error(f"[healthcare_records_repo] get_healthcare_records_for_patient failed: {exc}", exc_info=True)
        return []

    results.sort(key=lambda x: x["date"] or date.min)
    return results
