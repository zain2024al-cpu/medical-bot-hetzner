# modules/residency/repository.py
# استعلامات القراءة على res_persons/res_status_log.

from dataclasses import dataclass, field

from modules.residency.constants import STATUS_ORDER


@dataclass(frozen=True)
class PersonRow:
    id: int
    parent_id: int | None
    name: str
    status: str
    photo_file_id: str
    reminder_date: str
    expiry_date: str
    residency_file_id: str
    # ✅ تاريخ آخر إصدار — يُملأ عند معالجة "🏠 معلّقات من الحالات السابقة"
    # فقط؛ فارغ لكل من جاء عبر تدفق الوصول الاعتيادي.
    last_issue_date: str = ""


@dataclass(frozen=True)
class FamilyRow:
    root: PersonRow
    companions: list[PersonRow] = field(default_factory=list)


@dataclass(frozen=True)
class LogEntry:
    person_name: str
    old_status: str
    new_status: str
    performed_by: int | None
    created_at: str


@dataclass(frozen=True)
class DocumentRow:
    id: int
    person_id: int
    doc_type: str
    doc_name: str
    file_id: str
    created_at: str


def _to_row(p) -> PersonRow:
    return PersonRow(
        id=p.id, parent_id=p.parent_id, name=p.name or "—", status=p.status,
        photo_file_id=p.photo_file_id or "", reminder_date=p.reminder_date or "",
        expiry_date=p.expiry_date or "", residency_file_id=p.residency_file_id or "",
        last_issue_date=getattr(p, "last_issue_date", "") or "",
    )


def get_status_counts() -> dict:
    """عدد الطلبات (لا الأشخاص) التي لها شخص واحد على الأقل بكل حالة."""
    from db.session import get_db
    from db.models import ResidencyPerson

    counts = {s: 0 for s in STATUS_ORDER}
    with get_db() as db:
        people = db.query(ResidencyPerson).all()
        by_status_roots: dict[str, set] = {s: set() for s in STATUS_ORDER}
        for p in people:
            root_id = p.parent_id if p.parent_id else p.id
            if p.status in by_status_roots:
                by_status_roots[p.status].add(root_id)
        for s in STATUS_ORDER:
            counts[s] = len(by_status_roots[s])
    return counts


def get_requests_by_status(status: str) -> list[FamilyRow]:
    """كل الطلبات (جذر + مرافقوه) التي لها شخص واحد على الأقل بهذه الحالة."""
    from db.session import get_db
    from db.models import ResidencyPerson

    rows: list[FamilyRow] = []
    with get_db() as db:
        matching = db.query(ResidencyPerson).filter_by(status=status).all()
        root_ids: list[int] = []
        seen = set()
        for p in matching:
            root_id = p.parent_id if p.parent_id else p.id
            if root_id not in seen:
                seen.add(root_id)
                root_ids.append(root_id)

        for root_id in root_ids:
            root = db.query(ResidencyPerson).filter_by(id=root_id).first()
            if not root:
                continue
            comps = (
                db.query(ResidencyPerson)
                .filter_by(parent_id=root_id)
                .order_by(ResidencyPerson.id.asc())
                .all()
            )
            rows.append(FamilyRow(root=_to_row(root), companions=[_to_row(c) for c in comps]))
    return rows


def get_family(root_id: int) -> FamilyRow | None:
    from db.session import get_db
    from db.models import ResidencyPerson

    with get_db() as db:
        root = db.query(ResidencyPerson).filter_by(id=root_id).first()
        if not root:
            return None
        comps = (
            db.query(ResidencyPerson)
            .filter_by(parent_id=root_id)
            .order_by(ResidencyPerson.id.asc())
            .all()
        )
        return FamilyRow(root=_to_row(root), companions=[_to_row(c) for c in comps])


def get_person(person_id: int) -> PersonRow | None:
    from db.session import get_db
    from db.models import ResidencyPerson

    with get_db() as db:
        p = db.query(ResidencyPerson).filter_by(id=person_id).first()
        return _to_row(p) if p else None


def get_root_id_for_person(person_id: int) -> int | None:
    from db.session import get_db
    from db.models import ResidencyPerson

    with get_db() as db:
        p = db.query(ResidencyPerson).filter_by(id=person_id).first()
        if not p:
            return None
        return p.parent_id if p.parent_id else p.id


def search_persons(query: str, limit: int = 20) -> list[PersonRow]:
    from db.session import get_db
    from db.models import ResidencyPerson

    with get_db() as db:
        matches = (
            db.query(ResidencyPerson)
            .filter(ResidencyPerson.name.ilike(f"%{query}%"))
            .order_by(ResidencyPerson.created_at.desc())
            .limit(limit)
            .all()
        )
        return [_to_row(p) for p in matches]


def get_recent_log(limit: int = 30) -> list[LogEntry]:
    from db.session import get_db
    from db.models import ResidencyStatusLog, ResidencyPerson

    with get_db() as db:
        entries = (
            db.query(ResidencyStatusLog)
            .order_by(ResidencyStatusLog.created_at.desc())
            .limit(limit)
            .all()
        )
        rows: list[LogEntry] = []
        for e in entries:
            person = db.query(ResidencyPerson).filter_by(id=e.person_id).first()
            rows.append(LogEntry(
                person_name=person.name if person else f"#{e.person_id}",
                old_status=e.old_status or "",
                new_status=e.new_status or "",
                performed_by=e.performed_by,
                created_at=e.created_at.strftime("%Y-%m-%d %H:%M") if e.created_at else "",
            ))
        return rows


@dataclass(frozen=True)
class IssuanceRow:
    person_id: int
    expiry_date: str
    file_id: str
    issued_at: str


def get_latest_issuance(person_id: int) -> IssuanceRow | None:
    """آخر سطر أرشفة لهذا الشخص في res_issuance_history — للحصول على
    تاريخ الإصدار (issued_at) الذي لا يُخزَّن في الحقول الحيّة."""
    from db.session import get_db
    from db.models import ResidencyIssuance

    with get_db() as db:
        row = (
            db.query(ResidencyIssuance)
            .filter_by(person_id=person_id)
            .order_by(ResidencyIssuance.issued_at.desc())
            .first()
        )
        if not row:
            return None
        return IssuanceRow(
            person_id=row.person_id, expiry_date=row.expiry_date or "",
            file_id=row.file_id or "", issued_at=row.issued_at.strftime("%Y-%m-%d") if row.issued_at else "",
        )


def get_documents_for_person(person_id: int) -> list[DocumentRow]:
    """Form C أولاً إن وُجدت، ثم بقية الوثائق بترتيب الإضافة."""
    from db.session import get_db
    from db.models import ResidencyDocument

    with get_db() as db:
        docs = (
            db.query(ResidencyDocument)
            .filter_by(person_id=person_id)
            .order_by(ResidencyDocument.created_at.asc())
            .all()
        )
        rows = [DocumentRow(
            id=d.id, person_id=d.person_id, doc_type=d.doc_type, doc_name=d.doc_name or "",
            file_id=d.file_id, created_at=d.created_at.strftime("%Y-%m-%d") if d.created_at else "",
        ) for d in docs]
        rows.sort(key=lambda r: 0 if r.doc_type == "form_c" else 1)
        return rows


def get_status_since(person_ids: list[int]) -> dict[int, str]:
    """{person_id: تاريخ آخر تحوّل حالة} — أي متى دخل حالته الحالية.

    كل انتقال يُسجَّل في `res_status_log`، فآخر صفٍّ لكل شخص هو لحظة دخوله
    حالته الراهنة. من لا سجلّ له (بيانات سابقة للتسجيل) يغيب من القاموس
    فتظهر شاشته بلا شارة "منذ" بدل رقم مُختلَق.

    استعلام واحد لكل الأشخاص — لا استعلام داخل حلقة العرض.
    """
    import logging
    from sqlalchemy import func
    from db.session import get_db
    from db.models import ResidencyStatusLog

    if not person_ids:
        return {}
    try:
        with get_db() as db:
            rows = (
                db.query(ResidencyStatusLog.person_id,
                         func.max(ResidencyStatusLog.created_at))
                .filter(ResidencyStatusLog.person_id.in_(person_ids))
                .group_by(ResidencyStatusLog.person_id)
                .all()
            )
            return {pid: (str(ts)[:10] if ts else "") for pid, ts in rows if ts}
    except Exception as exc:
        logging.getLogger(__name__).warning(
            f"[residency] get_status_since failed: {exc}")
        return {}


def get_document_owner(doc_id: int) -> int | None:
    """صاحب الوثيقة — لإعادة عرض شاشته بعد الحذف."""
    from db.session import get_db
    from db.models import ResidencyDocument

    with get_db() as db:
        d = db.query(ResidencyDocument).filter_by(id=doc_id).first()
        return d.person_id if d else None


def get_document_counts(person_ids: list[int]) -> dict[int, int]:
    from db.session import get_db
    from db.models import ResidencyDocument

    counts = {pid: 0 for pid in person_ids}
    if not person_ids:
        return counts
    with get_db() as db:
        docs = db.query(ResidencyDocument).filter(ResidencyDocument.person_id.in_(person_ids)).all()
        for d in docs:
            counts[d.person_id] = counts.get(d.person_id, 0) + 1
    return counts


def get_onboarding_queue(root_id: int) -> list[PersonRow]:
    """المريض (root_id) ثم كل مرافقيه بترتيب الإضافة — لتسلسل 🟡."""
    from db.session import get_db
    from db.models import ResidencyPerson

    with get_db() as db:
        root = db.query(ResidencyPerson).filter_by(id=root_id).first()
        if not root:
            return []
        comps = (
            db.query(ResidencyPerson)
            .filter_by(parent_id=root_id)
            .order_by(ResidencyPerson.id.asc())
            .all()
        )
        return [_to_row(root)] + [_to_row(c) for c in comps]


# ── ربط اختياري ببيانات "🛬 الوصول" (طباعة ملف الحالة + ملخّص "🟡 معلّق
# من الوصول") ─────────────────────────────────────────────────────────────
# ✅ لا رابط حقيقي (FK) بين res_persons وجداول الوصول — مطابقة بالاسم
# الحرفي وقت الاستخدام فقط، نفس دقّة services/patients_service.py::
# get_patient_by_name() (filter_by مطابقة تامة، بلا تطبيع). عدم وجود
# تطابق ⇒ None، يُتجاهَل بصمت من قِبَل المستدعي.

@dataclass(frozen=True)
class ArrivalDocsRow:
    passport_file_id: str
    visa_file_id: str
    residence_file_id: str
    tickets_file_id: str
    uploaded_at: str   # "%Y-%m-%d" من created_at صف الوصول
    arrival_date: str
    passport_expiry: str
    visa_expiry: str
    residence_expiry: str


def get_arrival_patient_docs_by_name(name: str) -> ArrivalDocsRow | None:
    from db.session import get_db
    from db.models import ArrivalPatient

    with get_db() as db:
        row = (
            db.query(ArrivalPatient)
            .filter_by(name=name)
            .order_by(ArrivalPatient.created_at.desc())
            .first()
        )
        if not row:
            return None
        return ArrivalDocsRow(
            passport_file_id=row.passport_file_id or "",
            visa_file_id=row.visa_file_id or "",
            residence_file_id=row.residence_file_id or "",
            tickets_file_id=row.tickets_file_id or "",
            uploaded_at=row.created_at.strftime("%Y-%m-%d") if row.created_at else "",
            arrival_date=row.arrival_date or "",
            passport_expiry=row.passport_expiry or "",
            visa_expiry=row.visa_expiry or "",
            residence_expiry=row.residence_expiry or "",
        )


def get_arrival_companion_names(patient_name: str) -> list[str]:
    """أسماء مرافقي **الوصول** المسجَّلين لهذا المريض.

    ⚠️ مصدر مستقل تماماً عن `res_persons`: أشخاص الإقامة يُنشَؤون مرة
    واحدة عند تأكيد الوصول عبر `create_profiles_from_arrival`، وهو نداء
    **fire-and-forget** داخل `try/except`. فإن فشل، أو أُضيف مرافق لصف
    الوصول بعد ذلك، يبقى المرافق مسجَّلاً في الوصول و**غائباً عن الإقامة
    للأبد** — بلا أي شاشة تكشف الفجوة.

    المطابقة بالاسم الحرفي (لا FK بين الجدولين — نمط المشروع كلّه).
    """
    from db.session import get_db
    from db.models import ArrivalPatient, ArrivalCompanion

    name = (patient_name or "").strip()
    if not name:
        return []
    out: list[str] = []
    seen: set[str] = set()
    with get_db() as db:
        rows = (
            db.query(ArrivalPatient)
            .filter(ArrivalPatient.name == name)
            .order_by(ArrivalPatient.created_at.desc())
            .all()
        )
        for ap in rows:
            for c in db.query(ArrivalCompanion).filter_by(patient_id=ap.id).all():
                cname = (c.name or "").strip()
                if cname and cname not in seen:
                    seen.add(cname)
                    out.append(cname)
    return out


def get_arrival_companion_docs_by_name(name: str) -> ArrivalDocsRow | None:
    from db.session import get_db
    from db.models import ArrivalCompanion

    with get_db() as db:
        row = (
            db.query(ArrivalCompanion)
            .filter_by(name=name)
            .order_by(ArrivalCompanion.created_at.desc())
            .first()
        )
        if not row:
            return None
        return ArrivalDocsRow(
            passport_file_id=row.passport_file_id or "",
            visa_file_id=row.visa_file_id or "",
            residence_file_id=row.residence_file_id or "",
            tickets_file_id=row.tickets_file_id or "",
            uploaded_at=row.created_at.strftime("%Y-%m-%d") if row.created_at else "",
            arrival_date=row.arrival_date or "",
            passport_expiry=row.passport_expiry or "",
            visa_expiry=row.visa_expiry or "",
            residence_expiry=row.residence_expiry or "",
        )
