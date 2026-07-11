# modules/healthcare/pharmacy_finance/session.py

from dataclasses import dataclass

_KEY = "_hcphfin_add"

# ── Step identifiers ───────────────────────────────────────────────────────────
STEP_LIST              = "list"               # قائمة الحالات (صيدلية فقط)
STEP_ITEM_COUNT        = "item_count_edit"     # تعديل عدد/تفاصيل الأصناف (من شاشة المراجعة فقط)
STEP_INVOICE_NUMBER    = "invoice_number"      # رقم الفاتورة
STEP_EXPENSE_ITEM      = "expense_item"        # بند الصرف
STEP_INVOICE_TOTAL     = "invoice_total"       # المبلغ النهائي
STEP_MANIFEST_TYPE     = "manifest_type"       # نوع المسير (A/B/C) — لأغراض الطباعة فقط
STEP_REVIEW            = "review"              # مراجعة نهائية

_DEFAULT_MANIFEST_TYPE = "A"


@dataclass
class PharmacyFinanceSession:
    step:                 str
    source_type:          str          # "medication" | "supplies"
    source_record_id:     int
    patient_name:         str          # للعرض فقط (denormalized من التقرير المصدر)
    item_count:           int          # للعرض فقط (denormalized من التقرير المصدر)
    invoice_number:       str
    expense_item:         str
    invoice_total:        float
    discount_percent:     float
    discount_amount:      float        # محسوب
    net_amount:           float        # محسوب
    manifest_type:        str          # "A" | "B" | "C" — تصنيف طباعة فقط
    is_edit:              bool
    existing_financial_id: int | None
    edit_from_review:     bool

    def save(self, user_data: dict) -> None:
        user_data[_KEY] = {
            "step":                  self.step,
            "source_type":           self.source_type,
            "source_record_id":      self.source_record_id,
            "patient_name":          self.patient_name,
            "item_count":            self.item_count,
            "invoice_number":        self.invoice_number,
            "expense_item":          self.expense_item,
            "invoice_total":         self.invoice_total,
            "discount_percent":      self.discount_percent,
            "discount_amount":       self.discount_amount,
            "net_amount":            self.net_amount,
            "manifest_type":         self.manifest_type,
            "is_edit":               self.is_edit,
            "existing_financial_id": self.existing_financial_id,
            "edit_from_review":      self.edit_from_review,
        }

    @classmethod
    def create(cls, user_data: dict, *, source_type: str, source_record_id: int,
                patient_name: str, item_count: int) -> "PharmacyFinanceSession":
        session = cls(
            step=                 STEP_INVOICE_NUMBER,
            source_type=          source_type,
            source_record_id=     source_record_id,
            patient_name=         patient_name,
            item_count=           item_count,
            invoice_number=       "",
            expense_item=         "",
            invoice_total=        0.0,
            discount_percent=     0.0,
            discount_amount=      0.0,
            net_amount=           0.0,
            manifest_type=        _DEFAULT_MANIFEST_TYPE,
            is_edit=              False,
            existing_financial_id=None,
            edit_from_review=     False,
        )
        session.save(user_data)
        return session

    @classmethod
    def load(cls, user_data: dict) -> "PharmacyFinanceSession | None":
        raw = user_data.get(_KEY)
        if not raw:
            return None
        return cls(
            step=                 raw.get("step",                 STEP_INVOICE_NUMBER),
            source_type=          raw.get("source_type",          ""),
            source_record_id=     raw.get("source_record_id",     0),
            patient_name=         raw.get("patient_name",         ""),
            item_count=           raw.get("item_count",           0),
            invoice_number=       raw.get("invoice_number",       ""),
            expense_item=         raw.get("expense_item",         ""),
            invoice_total=        raw.get("invoice_total",        0.0),
            discount_percent=     raw.get("discount_percent",     0.0),
            discount_amount=      raw.get("discount_amount",      0.0),
            net_amount=           raw.get("net_amount",           0.0),
            manifest_type=        raw.get("manifest_type",        _DEFAULT_MANIFEST_TYPE),
            is_edit=              raw.get("is_edit",              False),
            existing_financial_id=raw.get("existing_financial_id",None),
            edit_from_review=     raw.get("edit_from_review",     False),
        )

    @classmethod
    def clear(cls, user_data: dict) -> None:
        user_data.pop(_KEY, None)
