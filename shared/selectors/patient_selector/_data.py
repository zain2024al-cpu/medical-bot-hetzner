# shared/selectors/patient_selector/_data.py
# Database access layer — the only file in this selector that touches the DB.
#
# All functions are synchronous (run in a thread pool via asyncio.to_thread
# if needed).  They return plain dataclass instances, never ORM objects.

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_DB_LIMIT = 500   # max rows fetched per query — covers any realistic patient list

# ✅ نوع ظهور المريض: مرضى "pharmacy_only" يظهرون فقط عندما يطلب المستدعي
# ذلك صراحةً (include_pharmacy=True — زرّا صرف الأدوية والمستلزمات الطبية).
# كل المستدعين الآخرين يحصلون على الافتراضي False فيرون مرضى general فقط
# (NULL أو "general") — وهذا يحفظ سلوك كل المرضى الحاليين (NULL) كما هو.
#
# ✅ "companion" (مرافق) يتبع نفس المبدأ تماماً: مخفي افتراضياً، ويظهر فقط
# عندما يطلبه المستدعي صراحةً (include_companions=True — الخدمات العامة
# والإقامة). لا علاقة له بـ include_pharmacy — كل نوع له علمه المستقل.
#
# ✅ "companion_parent" — المريض الرئيسي المُضاف عبر زر "مريض جديد مع
# مرافقين" (منفصل عن المرافقين أنفسهم). يبقى ظاهراً بشكل طبيعي كأي مريض
# "general" في كل الشاشات الأخرى (تقارير طبية...) — نفس القاعدة "أي نوع
# غير معروف صراحةً هنا = ظاهر افتراضياً" تشمله تلقائياً. يُستخدَم فقط
# لتمييزه عند طلب only_companion_flow (انظر أدناه).
_PHARMACY_ONLY = "pharmacy_only"
_COMPANION = "companion"
_COMPANION_PARENT = "companion_parent"


def _type_visible(
    patient_type,
    include_pharmacy: bool,
    include_companions: bool = False,
    only_companion_flow: bool = False,
) -> bool:
    pt = patient_type or "general"

    # ✅ فلتر مقيِّد حصراً: يُظهر فقط المرضى/المرافقين المُضافين عبر زر
    # "مريض جديد مع مرافقين" — يتجاوز include_pharmacy/include_companions
    # تماماً (يُستخدَم في "🔧 الخدمات العامة" و"🪪 الإقامة" حصراً).
    if only_companion_flow:
        return pt in (_COMPANION_PARENT, _COMPANION)

    if pt == _PHARMACY_ONLY:
        return include_pharmacy
    if pt == _COMPANION:
        return include_companions
    return True  # "general"، "companion_parent"، أو أي نوع آخر — ظاهر افتراضياً


@dataclass(frozen=True, slots=True)
class PatientRecord:
    """Immutable patient value object passed between layers."""
    id: int | None
    name: str


@dataclass(frozen=True)
class PatientSelectionResult:
    """
    Delivered to callers that need the shared selector result contract.

    selected  - tuple with the chosen PatientRecord, or empty when cancelled.
    cancelled - True when the user pressed Back/Cancel.
    """
    selected: tuple
    cancelled: bool

    @property
    def patient(self) -> PatientRecord | None:
        return self.selected[0] if self.selected else None

    @property
    def id(self) -> int | None:
        patient = self.patient
        return patient.id if patient else None

    @property
    def name(self) -> str:
        patient = self.patient
        return patient.name if patient else ""

    def is_empty(self) -> bool:
        return len(self.selected) == 0

    @staticmethod
    def cancelled_result() -> "PatientSelectionResult":
        return PatientSelectionResult(selected=(), cancelled=True)

    @staticmethod
    def confirmed(patient: PatientRecord) -> "PatientSelectionResult":
        return PatientSelectionResult(selected=(patient,), cancelled=False)


def fetch_all(
    include_pharmacy: bool = False,
    include_companions: bool = False,
    only_companion_flow: bool = False,
) -> list[PatientRecord]:
    """
    Fetch every patient from the database, sorted alphabetically.
    Duplicates (same full_name) are removed; the first occurrence wins.

    include_pharmacy — False (الافتراضي): مرضى general فقط (كل الشاشات).
                       True: يشمل أيضاً مرضى "pharmacy_only" (زرّا صرف
                       الأدوية والمستلزمات الطبية فقط).
    include_companions — False (الافتراضي): يخفي مرضى "companion".
                       True: يشمل أيضاً المرافقين (الخدمات العامة/الإقامة فقط).
    only_companion_flow — False (الافتراضي). True: يقتصر الظهور فقط على
                       المرضى/المرافقين المُضافين عبر زر "مريض جديد مع
                       مرافقين" (يتجاوز include_pharmacy/include_companions).

    Returns an empty list on any error (caller must handle gracefully).
    """
    try:
        from db.session import SessionLocal
        from db.models import Patient as _Patient

        with SessionLocal() as s:
            rows = (
                s.query(_Patient)
                .filter(_Patient.full_name.isnot(None), _Patient.full_name != "")
                .order_by(_Patient.full_name)
                .limit(_DB_LIMIT)
                .all()
            )
            seen: set[str] = set()
            records: list[PatientRecord] = []
            for p in rows:
                if not _type_visible(p.patient_type, include_pharmacy, include_companions, only_companion_flow):
                    continue
                name = (p.full_name or "").strip()
                if name and name not in seen:
                    seen.add(name)
                    records.append(PatientRecord(id=p.id, name=name))

            records.sort(key=lambda r: r.name)
            logger.debug(f"[patient_selector._data] fetch_all → {len(records)} records")
            return records

    except Exception as exc:
        logger.error(f"[patient_selector._data] fetch_all error: {exc}", exc_info=True)
        return []


def search(
    query: str,
    include_pharmacy: bool = False,
    include_companions: bool = False,
    only_companion_flow: bool = False,
) -> list[PatientRecord]:
    """
    Search for patients whose full_name contains query (case-insensitive).
    Falls back to fetch_all() when query is blank.

    include_pharmacy / include_companions / only_companion_flow — نفس دلالة fetch_all().

    Returns an empty list on any error.
    """
    query = query.strip()
    if not query:
        return fetch_all(
            include_pharmacy=include_pharmacy,
            include_companions=include_companions,
            only_companion_flow=only_companion_flow,
        )

    try:
        from db.session import SessionLocal
        from db.models import Patient as _Patient

        with SessionLocal() as s:
            rows = (
                s.query(_Patient)
                .filter(
                    _Patient.full_name.isnot(None),
                    _Patient.full_name != "",
                    _Patient.full_name.ilike(f"%{query}%"),
                )
                .order_by(_Patient.full_name)
                .limit(_DB_LIMIT)
                .all()
            )
            records = [
                PatientRecord(id=p.id, name=(p.full_name or "").strip())
                for p in rows
                if (p.full_name or "").strip()
                and _type_visible(p.patient_type, include_pharmacy, include_companions, only_companion_flow)
            ]
            logger.debug(
                f"[patient_selector._data] search({query!r}) → {len(records)} records"
            )
            return records

    except Exception as exc:
        logger.error(f"[patient_selector._data] search error: {exc}", exc_info=True)
        return []


def lookup_by_name(name: str) -> PatientRecord | None:
    """
    Exact-match lookup by full_name.
    Used to resolve a name chosen from the snapshot back to a DB id.
    Returns None if not found or on error.
    """
    name = name.strip()
    if not name:
        return None

    try:
        from db.session import SessionLocal
        from db.models import Patient as _Patient

        with SessionLocal() as s:
            p = s.query(_Patient).filter_by(full_name=name).first()
            if p:
                return PatientRecord(id=p.id, name=name)
            return None

    except Exception as exc:
        logger.error(f"[patient_selector._data] lookup_by_name error: {exc}", exc_info=True)
        return None
