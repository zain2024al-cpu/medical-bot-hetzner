# modules/healthcare/pharmacy_finance/models.py
# استعلامات وحفظ البيانات المالية المرتبطة بعمليات صرف "الصيدلية" فقط.

import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

_PHARMACY_SOURCE = "الصيدلية"


@dataclass
class SourceRecordInfo:
    source_type:      str    # "medication" | "supplies"
    source_record_id: int
    patient_name:     str
    department_labels: list[str]
    item_count:       int
    created_at:       "datetime | None"
    has_financial:    bool


def list_pharmacy_source_records(page: int = 0, page_size: int = 10) -> tuple[list[SourceRecordInfo], int]:
    """
    يعيد قائمة مُرقَّمة صفحات من MedicationRecord + SuppliesRecord حيث
    dispense_source == 'الصيدلية' فقط، مرتبة الأحدث أولاً، مع علامة
    has_financial (استعلام دفعة واحدة، ليس N+1).
    """
    import json
    from db.session import get_db
    from db.models import MedicationRecord, SuppliesRecord, PharmacyFinancialRecord

    with get_db() as db:
        med_rows = (
            db.query(MedicationRecord)
            .filter(MedicationRecord.dispense_source == _PHARMACY_SOURCE)
            .all()
        )
        sup_rows = (
            db.query(SuppliesRecord)
            .filter(SuppliesRecord.dispense_source == _PHARMACY_SOURCE)
            .all()
        )

        combined: list[SourceRecordInfo] = []
        for r in med_rows:
            depts = json.loads(r.medical_departments_json) if r.medical_departments_json else []
            combined.append(SourceRecordInfo(
                source_type="medication", source_record_id=r.id,
                patient_name=r.patient_name or "—", department_labels=depts,
                item_count=r.item_count or 0, created_at=r.created_at, has_financial=False,
            ))
        for r in sup_rows:
            depts = json.loads(r.medical_departments_json) if r.medical_departments_json else []
            combined.append(SourceRecordInfo(
                source_type="supplies", source_record_id=r.id,
                patient_name=r.patient_name or "—", department_labels=depts,
                item_count=r.item_count or 0, created_at=r.created_at, has_financial=False,
            ))

        # علامة has_financial بدفعة واحدة (بدون N+1)
        if combined:
            financial_keys = {(row.source_type, row.source_record_id) for row in combined}
            existing = (
                db.query(PharmacyFinancialRecord.source_type, PharmacyFinancialRecord.source_record_id)
                .filter(
                    PharmacyFinancialRecord.source_type.in_({k[0] for k in financial_keys}),
                    PharmacyFinancialRecord.source_record_id.in_({k[1] for k in financial_keys}),
                )
                .all()
            )
            existing_set = set(existing)
            for row in combined:
                row.has_financial = (row.source_type, row.source_record_id) in existing_set

        combined.sort(key=lambda r: r.created_at or datetime.min, reverse=True)

    total = len(combined)
    start = page * page_size
    page_rows = combined[start:start + page_size]
    return page_rows, total


def get_source_record(source_type: str, source_record_id: int) -> "SourceRecordInfo | None":
    """يجلب بيانات العرض الأساسية لتقرير مصدر واحد (صيدلية أو مستلزمات)."""
    import json
    from db.session import get_db
    from db.models import MedicationRecord, SuppliesRecord

    model = MedicationRecord if source_type == "medication" else SuppliesRecord
    with get_db() as db:
        r = db.query(model).filter_by(id=source_record_id).first()
        if not r:
            return None
        depts = json.loads(r.medical_departments_json) if r.medical_departments_json else []
        return SourceRecordInfo(
            source_type=source_type, source_record_id=r.id,
            patient_name=r.patient_name or "—", department_labels=depts,
            item_count=r.item_count or 0, created_at=r.created_at, has_financial=False,
        )


def get_financial_record(source_type: str, source_record_id: int) -> dict | None:
    """يجلب سجل البيانات المالية الموجود لهذا المصدر إن وُجد، كـ dict بسيط."""
    from db.session import get_db
    from db.models import PharmacyFinancialRecord

    with get_db() as db:
        r = (
            db.query(PharmacyFinancialRecord)
            .filter_by(source_type=source_type, source_record_id=source_record_id)
            .first()
        )
        if not r:
            return None
        return {
            "id": r.id,
            "invoice_number": r.invoice_number or "",
            "expense_item": r.expense_item or "",
            "invoice_total": r.invoice_total or 0.0,
            "discount_percent": r.discount_percent or 0.0,
            "discount_amount": r.discount_amount or 0.0,
            "net_amount": r.net_amount or 0.0,
        }


def save_financial_record(
    *,
    source_type: str,
    source_record_id: int,
    invoice_number: str,
    expense_item: str,
    invoice_total: float,
    discount_percent: float,
    created_by: int | None,
    existing_financial_id: int | None = None,
) -> dict:
    """
    ينشئ سجلاً جديداً أو يُحدِّث سجلاً موجوداً (existing_financial_id).
    يُعيد حساب discount_amount/net_amount من الصفر دائماً عند الحفظ.
    """
    from db.session import get_db
    from db.models import PharmacyFinancialRecord

    discount_amount = round(invoice_total * discount_percent / 100, 2)
    net_amount = round(invoice_total - discount_amount, 2)

    with get_db() as db:
        if existing_financial_id:
            record = db.query(PharmacyFinancialRecord).filter_by(id=existing_financial_id).first()
            if record is None:
                raise ValueError(f"PharmacyFinancialRecord {existing_financial_id} not found for update")
        else:
            record = PharmacyFinancialRecord(
                source_type=source_type,
                source_record_id=source_record_id,
                created_by=created_by,
            )
            db.add(record)

        record.invoice_number = invoice_number
        record.expense_item = expense_item
        record.invoice_total = invoice_total
        record.discount_percent = discount_percent
        record.discount_amount = discount_amount
        record.net_amount = net_amount
        db.flush()
        record_id = record.id

    logger.info(
        f"[pharmacy_finance] saved financial record id={record_id} "
        f"source={source_type}#{source_record_id} net={net_amount}"
    )
    return {
        "id": record_id,
        "invoice_number": invoice_number,
        "expense_item": expense_item,
        "invoice_total": invoice_total,
        "discount_percent": discount_percent,
        "discount_amount": discount_amount,
        "net_amount": net_amount,
    }
