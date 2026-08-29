# modules/residency/models.py
# عمليات الكتابة على res_persons/res_status_log — نظام دورة الحياة الكامل.

import logging

from modules.residency.constants import (
    STATUS_WAITING_ARRIVAL, STATUS_ACTIVE, STATUS_EXPIRY_PENDING,
    STATUS_SUBMITTED, STATUS_ISSUED, STATUS_LEGACY_PENDING,
)

logger = logging.getLogger(__name__)


def _log_transition(db, person_id: int, old_status: str, new_status: str, performed_by: int | None) -> None:
    from db.models import ResidencyStatusLog
    db.add(ResidencyStatusLog(
        person_id=person_id, old_status=old_status, new_status=new_status,
        performed_by=performed_by,
    ))


def create_profiles_from_arrival(patients: list[dict], created_by: int | None = None) -> int:
    """
    ينشئ ResidencyPerson لكل مريض في دفعة وصول مؤكَّدة + ResidencyPerson
    تابع (parent_id) لكل مرافق — نقطة الإنشاء الوحيدة لأشخاص الإقامة،
    عند تأكيد "🛬 الوصول" فقط. `patients` بنفس شكل
    `ArrivalSession.completed_patients` (كل عنصر: name + companions).

    Fire-and-forget من arrivals/flow.py — فشلها لا يوقف نشر دفعة الوصول.
    """
    from db.session import get_db
    from db.models import ResidencyPerson

    count = 0
    with get_db() as db:
        for p in patients:
            name = (p.get("name") or "").strip()
            if not name:
                continue
            patient = ResidencyPerson(name=name, status=STATUS_WAITING_ARRIVAL, created_by=created_by)
            db.add(patient)
            db.flush()
            _log_transition(db, patient.id, "", STATUS_WAITING_ARRIVAL, created_by)
            count += 1

            for c in p.get("companions", []):
                cname = (c.get("name") or "").strip()
                if not cname:
                    continue
                companion = ResidencyPerson(
                    name=cname, parent_id=patient.id,
                    status=STATUS_WAITING_ARRIVAL, created_by=created_by,
                )
                db.add(companion)
                db.flush()
                _log_transition(db, companion.id, "", STATUS_WAITING_ARRIVAL, created_by)
                count += 1

    logger.info(f"[residency] create_profiles_from_arrival: {count} person(s) created")
    return count


def sync_companions_from_arrival(root_id: int, performed_by: int | None = None) -> tuple:
    """يُنشئ في الإقامة كل مرافق مسجَّل في الوصول وغائب هنا.

    Returns: (عدد المُضاف, أسماء المُضافين).

    🔒 **إضافة فقط** — لا يحذف ولا يعدّل أحداً. المرافق الموجود مسبقاً
    (بأي حالة) يُترَك كما هو، فلا تُفقَد تواريخه ولا وثائقه.
    الحالة الابتدائية = حالة الجذر نفسها، لا `WAITING_ARRIVAL` دائماً:
    مريض وصل فعلاً ونُقِل لحالة نشطة، مرافقه المتأخّر يجب أن يبدأ معه لا
    خلفه بمرحلة.
    """
    from db.session import get_db
    from db.models import ResidencyPerson
    from modules.residency.repository import get_arrival_companion_names

    with get_db() as db:
        root = db.query(ResidencyPerson).filter_by(id=root_id).first()
        if not root or root.parent_id is not None:
            return 0, []

        existing = {
            (c.name or "").strip()
            for c in db.query(ResidencyPerson).filter_by(parent_id=root_id).all()
        }
        added = []
        for cname in get_arrival_companion_names(root.name):
            if cname in existing:
                continue
            comp = ResidencyPerson(
                name=cname, parent_id=root_id,
                status=root.status, created_by=performed_by,
            )
            db.add(comp)
            db.flush()
            _log_transition(db, comp.id, "", root.status, performed_by)
            added.append(cname)

    if added:
        logger.info(
            f"[residency] sync_companions_from_arrival root={root_id} "
            f"added={len(added)} {added}"
        )
    return len(added), added


def save_photo(person_id: int, file_id: str) -> bool:
    from db.session import get_db
    from db.models import ResidencyPerson

    with get_db() as db:
        person = db.query(ResidencyPerson).filter_by(id=person_id).first()
        if not person:
            return False
        person.photo_file_id = file_id
    logger.info(f"[residency] photo saved  person_id={person_id}")
    return True


def set_reminder_date(person_id: int, date_iso: str) -> bool:
    """يضبط تاريخ التنبيه اليدوي لهذا الشخص وحده."""
    from db.session import get_db
    from db.models import ResidencyPerson

    with get_db() as db:
        person = db.query(ResidencyPerson).filter_by(id=person_id).first()
        if not person:
            return False
        person.reminder_date = date_iso
    logger.info(f"[residency] reminder_date set  person_id={person_id}  date={date_iso}")
    return True


def bulk_activate_request(root_id: int, performed_by: int | None = None) -> int:
    """
    "✅ حفظ الإقامة" — يحوّل المريض (root_id) وكل مرافقيه دفعة واحدة من
    WAITING_ARRIVAL إلى ACTIVE، سجلّ منفصل لكل شخص.
    """
    from db.session import get_db
    from db.models import ResidencyPerson

    count = 0
    with get_db() as db:
        people = (
            db.query(ResidencyPerson)
            .filter((ResidencyPerson.id == root_id) | (ResidencyPerson.parent_id == root_id))
            .all()
        )
        for person in people:
            if person.status != STATUS_WAITING_ARRIVAL:
                continue
            old = person.status
            person.status = STATUS_ACTIVE
            _log_transition(db, person.id, old, STATUS_ACTIVE, performed_by)
            count += 1

    logger.info(f"[residency] bulk_activate_request root_id={root_id}: {count} person(s) → ACTIVE")
    return count


def mark_submitted(person_id: int, performed_by: int | None = None) -> bool:
    """🔵 تم التقديم — EXPIRY_PENDING → SUBMITTED لهذا الشخص وحده."""
    from db.session import get_db
    from db.models import ResidencyPerson

    with get_db() as db:
        person = db.query(ResidencyPerson).filter_by(id=person_id).first()
        if not person or person.status != STATUS_EXPIRY_PENDING:
            return False
        old = person.status
        person.status = STATUS_SUBMITTED
        _log_transition(db, person.id, old, STATUS_SUBMITTED, performed_by)
    logger.info(f"[residency] marked submitted  person_id={person_id}")
    return True


def start_issuance(person_id: int, performed_by: int | None = None) -> bool:
    """🟣 تم الإصدار — SUBMITTED → ISSUED (يبدأ جمع تاريخ الانتهاء + الملف)."""
    from db.session import get_db
    from db.models import ResidencyPerson

    with get_db() as db:
        person = db.query(ResidencyPerson).filter_by(id=person_id).first()
        if not person or person.status != STATUS_SUBMITTED:
            return False
        old = person.status
        person.status = STATUS_ISSUED
        _log_transition(db, person.id, old, STATUS_ISSUED, performed_by)
    logger.info(f"[residency] issuance started  person_id={person_id}")
    return True


def set_issuance_expiry(person_id: int, date_iso: str) -> bool:
    from db.session import get_db
    from db.models import ResidencyPerson

    with get_db() as db:
        person = db.query(ResidencyPerson).filter_by(id=person_id).first()
        if not person:
            return False
        person.expiry_date = date_iso
    return True


def save_issuance_file(person_id: int, file_id: str) -> bool:
    from db.session import get_db
    from db.models import ResidencyPerson

    with get_db() as db:
        person = db.query(ResidencyPerson).filter_by(id=person_id).first()
        if not person:
            return False
        person.residency_file_id = file_id
    return True


def confirm_issuance(person_id: int, performed_by: int | None = None) -> bool:
    """
    "✅ تأكيد الإصدار" — يتطلَّب expiry_date وresidency_file_id مكتملَين
    مسبقاً (عبر set_issuance_expiry/save_issuance_file). ISSUED → ACTIVE،
    وreminder_date يُصفَّر لبدء دورة تنبيه جديدة يدوياً (لا حساب تلقائي).

    ✅ يُضاف أيضاً سطر أرشفة في ResidencyIssuance (بجانب تحديث الحقول
    الحيّة على الشخص كالمعتاد) — حفاظاً على الإصدار السابق قبل أن
    تُستبدَل قيمه الحيّة، بلا أي تغيير على السلوك الظاهر لهذه الدالة.
    """
    from db.session import get_db
    from db.models import ResidencyPerson, ResidencyIssuance

    with get_db() as db:
        person = db.query(ResidencyPerson).filter_by(id=person_id).first()
        if not person or person.status != STATUS_ISSUED:
            return False
        if not person.expiry_date or not person.residency_file_id:
            return False
        old = person.status
        db.add(ResidencyIssuance(
            person_id=person.id, expiry_date=person.expiry_date,
            file_id=person.residency_file_id,
        ))
        person.status = STATUS_ACTIVE
        person.reminder_date = ""
        _log_transition(db, person.id, old, STATUS_ACTIVE, performed_by)
    logger.info(f"[residency] issuance confirmed  person_id={person_id} → ACTIVE")
    return True


def add_document(person_id: int, doc_type: str, doc_name: str, file_id: str, created_by: int | None = None) -> bool:
    """يضيف وثيقة مستقلة لشخص واحد — لا ترتبط بحالة الإقامة، لا تُمَسّ
    عند أي انتقال حالة."""
    from db.session import get_db
    from db.models import ResidencyPerson, ResidencyDocument

    with get_db() as db:
        person = db.query(ResidencyPerson).filter_by(id=person_id).first()
        if not person:
            return False
        db.add(ResidencyDocument(
            person_id=person_id, doc_type=doc_type, doc_name=doc_name,
            file_id=file_id, created_by=created_by,
        ))
    logger.info(f"[residency] document added  person_id={person_id}  type={doc_type}  name={doc_name!r}")
    return True


# ── 🏠 معالجة "معلّقات من الحالات السابقة" (المرضى القدامى) ──────────────────
# هؤلاء أُدخِلوا عبر شاشة الأدمن "🏠 الحالات الموجودة" بحالة LEGACY_PENDING.
# بياناتهم الأساسية (جواز/تأشيرة/سكن) مكتملة، لكن بيانات **الإقامة** نفسها
# لم تُدخَل بعد — تُدخَل هنا ثم يُنقَلون لحالتهم الطبيعية ضمن الحالات الخمس.

def set_last_issue_date(person_id: int, date_iso: str) -> bool:
    """تاريخ آخر إصدار للإقامة (إقامة أُصدرت قبل تفعيل الوحدة، فلا سجلّ لها)."""
    from db.session import get_db
    from db.models import ResidencyPerson

    with get_db() as db:
        person = db.query(ResidencyPerson).filter_by(id=person_id).first()
        if not person:
            return False
        person.last_issue_date = date_iso
    return True


def set_expiry_date(person_id: int, date_iso: str) -> bool:
    """تاريخ انتهاء الإقامة — يُستخدَم في مسارَي "يوجد تمديد" و"لا يوجد"."""
    from db.session import get_db
    from db.models import ResidencyPerson

    with get_db() as db:
        person = db.query(ResidencyPerson).filter_by(id=person_id).first()
        if not person:
            return False
        person.expiry_date = date_iso
    return True


def save_residency_file(person_id: int, file_id: str) -> bool:
    """صورة آخر إقامة (مستند رسمي — بلا ضبط مقاس)."""
    from db.session import get_db
    from db.models import ResidencyPerson

    with get_db() as db:
        person = db.query(ResidencyPerson).filter_by(id=person_id).first()
        if not person:
            return False
        person.residency_file_id = file_id
    return True


def move_family_to_status(root_id: int, new_status: str, performed_by: int | None = None) -> int:
    """ينقل المريض وكل مرافقيه من LEGACY_PENDING إلى الحالة التي يختارها
    المستخدم، بسجلّ انتقال منفصل لكل شخص.

    ⚠️ يقتصر على من هو في LEGACY_PENDING فعلاً — فلو كان أحد المرافقين قد
    نُقِل سابقاً بشكل مستقل لا يُعاد تحريكه (نفس حارس `bulk_activate_request`).

    ✅ يُؤرشَف الإصدار في ResidencyIssuance لمن يملك تاريخ انتهاء وملف إقامة
    معاً — حتى يظهر ضمن "🖨️ طباعة ملف الحالة" وسجلّ الإصدارات كأي إصدار
    رسمي، بلا حاجة لإعادة إدخاله لاحقاً.
    """
    from db.session import get_db
    from db.models import ResidencyPerson, ResidencyIssuance

    count = 0
    with get_db() as db:
        people = (
            db.query(ResidencyPerson)
            .filter((ResidencyPerson.id == root_id) | (ResidencyPerson.parent_id == root_id))
            .all()
        )
        for person in people:
            if person.status != STATUS_LEGACY_PENDING:
                continue
            if person.expiry_date and person.residency_file_id:
                db.add(ResidencyIssuance(
                    person_id=person.id, expiry_date=person.expiry_date,
                    file_id=person.residency_file_id,
                ))
            old = person.status
            person.status = new_status
            _log_transition(db, person.id, old, new_status, performed_by)
            count += 1

    logger.info(
        f"[residency] move_family_to_status root_id={root_id} → {new_status}: {count} person(s)"
    )
    return count


# ── الحذف ────────────────────────────────────────────────────────────────────
# ⚠️ لم تكن ثمة **أي** وسيلة لحذف ملف أو وثيقة: الوثائق تُضاف فقط
# (`build_documents_list` بها زر إضافة وحده)، وصورة الإقامة/الشخصية
# تُستبدَل ولا تُحذَف. فوثيقة رُفِعت لشخص خطأً — أو نوع خاطئ — تبقى في
# ملف الحالة وتُطبَع معه إلى الأبد.
#
# 🔒 الحذف هنا يمسّ **مرجع الملف في قاعدة البيانات فقط**؛ الملف نفسه يبقى
# في تيليجرام. ولا تُحذف أي بيانات أخرى للشخص.

def delete_document(doc_id: int) -> tuple[bool, str]:
    """يحذف وثيقة واحدة. Returns: (نجاح, اسمها للعرض)."""
    from db.session import get_db
    from db.models import ResidencyDocument

    with get_db() as db:
        d = db.query(ResidencyDocument).filter_by(id=doc_id).first()
        if not d:
            return False, ""
        label = "Form C" if d.doc_type == "form_c" else (d.doc_name or "وثيقة")
        db.delete(d)
    logger.info(f"[residency] document deleted id={doc_id} label={label!r}")
    return True, label


def clear_residency_file(person_id: int) -> bool:
    """يمسح مرجع صورة الإقامة (لا يمسّ تاريخ الانتهاء ولا غيره)."""
    from db.session import get_db
    from db.models import ResidencyPerson

    with get_db() as db:
        p = db.query(ResidencyPerson).filter_by(id=person_id).first()
        if not p:
            return False
        p.residency_file_id = ""
    logger.info(f"[residency] residency_file cleared person_id={person_id}")
    return True


def clear_photo(person_id: int) -> bool:
    """يمسح مرجع الصورة الشخصية."""
    from db.session import get_db
    from db.models import ResidencyPerson

    with get_db() as db:
        p = db.query(ResidencyPerson).filter_by(id=person_id).first()
        if not p:
            return False
        p.photo_file_id = ""
    logger.info(f"[residency] photo cleared person_id={person_id}")
    return True


def delete_stub_person_by_name(name: str) -> int:
    """
    ✅ تُستدعى من services/patients_service.py::delete_patient() — تحذف
    أي شخص إقامة لم يُستكمَل بعد (WAITING_ARRIVAL بلا صورة) مطابق للاسم
    عند حذف المريض المرتبط به. أشخاص لهم تقدّم حقيقي (صورة مرفوعة، أو
    أي حالة أخرى) لا يُمَسّون إطلاقاً.
    """
    from db.session import get_db
    from db.models import ResidencyPerson

    deleted = 0
    with get_db() as db:
        stale = (
            db.query(ResidencyPerson)
            .filter_by(name=name, status=STATUS_WAITING_ARRIVAL)
            .filter(
                (ResidencyPerson.photo_file_id == "") | (ResidencyPerson.photo_file_id.is_(None))
            )
            .all()
        )
        for person in stale:
            db.query(ResidencyPerson).filter_by(parent_id=person.id).delete()
            db.delete(person)
            deleted += 1
            logger.info(f"[residency] deleted orphaned waiting-arrival person #{person.id} for: {name}")

    return deleted
