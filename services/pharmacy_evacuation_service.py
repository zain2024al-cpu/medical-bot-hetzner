# services/pharmacy_evacuation_service.py
"""
طبقة استعلام "مسير إخلاء الأدوية والمستلزمات الطبية".

يجلب فقط الحالات التي:
  - جهة الصرف = "الصيدلية" (المخزن مستبعد تماماً — لا يحتاج بيانات مالية).
  - لها سجل بيانات مالية مكتمل (PharmacyFinancialRecord) — وإلا تُستبعد
    تماماً من المسير (وليس عرضاً جزئياً).

نفس نمط asyncio.to_thread + SessionLocal المُثبت في reports_repository.py.
"""

import asyncio
import json
import logging
from datetime import date, datetime, time

logger = logging.getLogger(__name__)

_PHARMACY_SOURCE = "الصيدلية"


async def get_evacuation_ledger_rows(start_date: date, end_date: date) -> list[dict]:
    return await asyncio.to_thread(_get_evacuation_ledger_rows_sync, start_date, end_date)


def _get_evacuation_ledger_rows_sync(start_date: date, end_date: date) -> list[dict]:
    from db.session import SessionLocal
    from db.models import MedicationRecord, SuppliesRecord, PharmacyFinancialRecord

    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date, time.max)

    rows: list[dict] = []
    try:
        with SessionLocal() as s:
            med_rows = (
                s.query(MedicationRecord)
                .filter(
                    MedicationRecord.dispense_source == _PHARMACY_SOURCE,
                    MedicationRecord.created_at >= start_dt,
                    MedicationRecord.created_at <= end_dt,
                )
                .all()
            )
            sup_rows = (
                s.query(SuppliesRecord)
                .filter(
                    SuppliesRecord.dispense_source == _PHARMACY_SOURCE,
                    SuppliesRecord.created_at >= start_dt,
                    SuppliesRecord.created_at <= end_dt,
                )
                .all()
            )

            source_records = [("medication", r) for r in med_rows] + [("supplies", r) for r in sup_rows]
            if not source_records:
                return []

            keys = {(stype, r.id) for stype, r in source_records}
            financial_rows = (
                s.query(PharmacyFinancialRecord)
                .filter(
                    PharmacyFinancialRecord.source_type.in_({k[0] for k in keys}),
                    PharmacyFinancialRecord.source_record_id.in_({k[1] for k in keys}),
                )
                .all()
            )
            financial_by_key = {(f.source_type, f.source_record_id): f for f in financial_rows}

            for source_type, r in source_records:
                fin = financial_by_key.get((source_type, r.id))
                if fin is None:
                    # لا بيانات مالية مكتملة -> استبعاد تام من المسير
                    continue
                statement = (
                    f"تم صرف {r.item_count or 0} أصناف."
                    if source_type == "medication"
                    else f"تم صرف {r.item_count or 0} مستلزمات طبية."
                )
                rows.append({
                    "amount": fin.net_amount or 0.0,
                    "name": r.patient_name or "—",
                    "invoice_number": fin.invoice_number or "—",
                    "expense_item": fin.expense_item or "—",
                    "statement": statement,
                    "date": r.created_at.date() if r.created_at else start_date,
                    "_sort_dt": r.created_at or start_dt,
                })

        rows.sort(key=lambda r: r["_sort_dt"])
        for r in rows:
            r.pop("_sort_dt", None)

    except Exception as exc:
        logger.error(f"[pharmacy_evacuation] ledger query failed: {exc}", exc_info=True)
        return []

    return rows
