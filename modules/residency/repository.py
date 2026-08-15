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
