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


def _format_dispense_statement(item_count, kind: str) -> str:
    """
    "عدد الأصناف" أصبح نصاً حراً (رقم أو وصف كل صنف)، وليس رقماً فقط.
    - قيمة رقمية بحتة (بيانات قديمة أو إدخال رقم بسيط) → نفس الصياغة السابقة تماماً.
    - نص حر (وصف الأصناف) → يُعرَض كما هو في البيان مباشرة.
    """
    val = str(item_count if item_count is not None else "").strip()
    if val.isdigit():
        return (
            f"تم صرف {val} أصناف."
            if kind == "medication"
            else f"تم صرف {val} مستلزمات طبية."
        )
    if val:
        return f"الأصناف المصروفة: {val}."
    return "تم صرف 0 أصناف." if kind == "medication" else "تم صرف 0 مستلزمات طبية."


async def get_evacuation_ledger_rows(
    start_date: date, end_date: date, manifest_type: str | None = None,
) -> list[dict]:
    """manifest_type: "A" | "B" | "C" لتقييد المسير على تصنيف واحد فقط،
    أو None لعدم الفلترة (كل التصنيفات معاً — السلوك القديم بلا تغيير).

    ⚠️ start_date/end_date يُطبَّقان دائماً على تاريخ سجل الصرف الأصلي
    (MedicationRecord/SuppliesRecord.created_at) — وليس على تاريخ إدخال
    البيانات المالية (PharmacyFinancialRecord). حالة صُرِفت يوم 10 وأُدخلت
    بياناتها المالية يوم 15 تظهر دائماً في مسير يوم 10، وتبقى غائبة تماماً
    عن أي مسير يُطبَع لنطاق يوم 15 فقط."""
    return await asyncio.to_thread(_get_evacuation_ledger_rows_sync, start_date, end_date, manifest_type)


def _get_evacuation_ledger_rows_sync(
    start_date: date, end_date: date, manifest_type: str | None = None,
) -> list[dict]:
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
            financial_query = s.query(PharmacyFinancialRecord).filter(
                PharmacyFinancialRecord.source_type.in_({k[0] for k in keys}),
                PharmacyFinancialRecord.source_record_id.in_({k[1] for k in keys}),
            )
            if manifest_type:
                # ✅ السجلات القديمة (قبل إضافة هذا التصنيف) لها manifest_type
                # فارغ في القاعدة — تُعامَل كـ"A" في كل مكان آخر بالكود، لذا
                # فلترة A تشمل أيضاً NULL حتى تبقى ظاهرة في المسير كسابقاً.
                if manifest_type == "A":
                    financial_query = financial_query.filter(
                        (PharmacyFinancialRecord.manifest_type == "A")
                        | (PharmacyFinancialRecord.manifest_type.is_(None))
                    )
                else:
                    financial_query = financial_query.filter(PharmacyFinancialRecord.manifest_type == manifest_type)
            financial_rows = financial_query.all()
            financial_by_key = {(f.source_type, f.source_record_id): f for f in financial_rows}

            for source_type, r in source_records:
                fin = financial_by_key.get((source_type, r.id))
                if fin is None:
                    # لا بيانات مالية مكتملة (أو لا تطابق فلتر نوع المسير) -> استبعاد تام من المسير
                    continue
                statement = _format_dispense_statement(r.item_count, source_type)
                rows.append({
                    "amount": fin.net_amount or 0.0,
                    "name": r.patient_name or "—",
                    "invoice_number": fin.invoice_number or "—",
                    "expense_item": fin.expense_item or "—",
                    "statement": statement,
                    # ⚠️ مصدر الحقيقة الوحيد للتاريخ هو سجل الصرف الأصلي (r =
                    # MedicationRecord/SuppliesRecord.created_at) — أبداً
                    # fin.created_at/fin.updated_at (التقرير المالي) ولا
                    # datetime.now()/utcnow(). التقرير المالي يُثري سجل الصرف
                    # ببيانات مالية فقط (فاتورة/مبلغ) ولا يُنشئ حدثاً طبياً
                    # جديداً ولا يُغيّر تاريخه أبداً، حتى لو أُدخل أو عُدِّل
                    # بعد يوم الصرف الفعلي بأيام. لا تُغيّر هذا السطر لاستخدام fin.*.
                    "date": r.created_at.date() if r.created_at else start_date,
                    "manifest_type": fin.manifest_type or "A",
                    "_sort_dt": r.created_at or start_dt,
                })

        rows.sort(key=lambda r: r["_sort_dt"])
        for r in rows:
            r.pop("_sort_dt", None)

    except Exception as exc:
        logger.error(f"[pharmacy_evacuation] ledger query failed: {exc}", exc_info=True)
        return []

    return rows
