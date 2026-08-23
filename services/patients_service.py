# -*- coding: utf-8 -*-
"""
خدمة المرضى الموحدة
Unified Patients Service - Single Source of Truth (Database)
"""

import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def get_patients_from_database(limit: int = None) -> List[Dict]:
    """
    الحصول على المرضى من قاعدة البيانات
    """
    try:
        from db.session import SessionLocal
        from db.models import Patient
        
        with SessionLocal() as session:
            query = session.query(Patient).filter(
                Patient.full_name.isnot(None)
            ).order_by(Patient.created_at.desc())
            
            if limit:
                query = query.limit(limit)
            
            patients = query.all()
            
            result = []
            for p in patients:
                result.append({
                    'id': p.id,
                    'name': p.full_name,
                    'created_at': p.created_at
                })
            
            logger.info(f"Loaded {len(result)} patients from database")
            return result
            
    except Exception as e:
        logger.error(f"Error loading patients from database: {e}")
        return []


def get_patients_from_file() -> List[str]:
    """
    الحصول على المرضى من الملف (fallback)
    """
    possible_paths = [
        os.path.join(os.path.dirname(__file__), '..', 'data', 'patient_names.txt'),
        'data/patient_names.txt',
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    names = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                logger.info(f"Loaded {len(names)} patients from file")
                return names
            except Exception as e:
                logger.error(f"Error reading patient file: {e}")
    
    return []


def get_all_patient_names(prefer_database: bool = True) -> List[str]:
    """
    الحصول على أسماء جميع المرضى
    يحاول من قاعدة البيانات أولاً، ثم من الملف
    """
    if prefer_database:
        # Try database first
        patients = get_patients_from_database()
        
        if patients:
            return [p['name'] for p in patients]
    
    # Fallback to file
    return get_patients_from_file()


def get_all_patients() -> List[Dict]:
    """
    الحصول على جميع المرضى مع التفاصيل
    """
    patients = get_patients_from_database()
    
    if patients:
        return patients
    
    # Fallback: convert file names to dicts
    names = get_patients_from_file()
    return [{'id': i, 'name': name} for i, name in enumerate(names)]


def get_patient_by_name(name: str) -> Optional[Dict]:
    """
    البحث عن مريض بالاسم
    """
    try:
        from db.session import SessionLocal
        from db.models import Patient
        
        with SessionLocal() as session:
            patient = session.query(Patient).filter_by(full_name=name).first()
            if patient:
                return {
                    'id': patient.id,
                    'name': patient.full_name,
                    'created_at': patient.created_at
                }
    except Exception as e:
        logger.error(f"Error getting patient by name: {e}")
    
    return None


def get_patient_by_id(patient_id: int) -> Optional[Dict]:
    """
    البحث عن مريض بالID
    """
    try:
        from db.session import SessionLocal
        from db.models import Patient
        
        with SessionLocal() as session:
            patient = session.query(Patient).filter_by(id=patient_id).first()
            if patient:
                return {
                    'id': patient.id,
                    'name': patient.full_name,
                    'created_at': patient.created_at,
                    'patient_type': patient.patient_type,
                }
    except Exception as e:
        logger.error(f"Error getting patient by id: {e}")
    
    return None


def add_patient(
    name: str,
    patient_type: Optional[str] = None,
    companion_of_id: Optional[int] = None,
    pending_arrival: bool = False,
    skip_dedup: bool = False,
) -> Optional[int]:
    """
    إضافة مريض جديد
    patient_type: None/"general" = يظهر للجميع (الافتراضي)،
                  "pharmacy_only" = يظهر فقط في صرف الأدوية والمستلزمات الطبية.
    companion_of_id: معرّف المريض الذي يرافقه (للنوع "companion" فقط) —
                  يسمح لاحقاً بجلب "مرافقي هذا المريض" مباشرة بدل السؤال عنهم.
    pending_arrival: True لأسماء "مريض جديد مع مرافقين" — لم تُستخدَم بعد
                  في تقرير وصول فعلي، تظهر في شاشة "📋 الأسماء المعلّقة".
    skip_dedup: True لتخطّي فحص "الاسم موجود مسبقاً" كلياً وإنشاء صف جديد
                  دائماً — ضروري للمرافقين تحديداً (خلل حقيقي مكتشَف: اسم
                  مرافق يتطابق صدفة مع مريض عادي موجود من تقرير طبي كان
                  يجعل add_patient تُعيد id ذلك المريض بلا تحديث
                  patient_type/companion_of_id إطلاقاً — فلا يظهر المرافق
                  تحت مريضه في شاشة الحذف ولا يُحذَف معه). الافتراضي False
                  يحافظ على سلوك كل مستدعٍ آخر (لا تكرار لأسماء المرضى
                  العاديين).
    إن كان الاسم موجوداً مسبقاً (وskip_dedup=False) يُعاد id الموجود دون
    تغيير نوعه.
    Returns patient id or None
    """
    try:
        from db.session import SessionLocal
        from db.models import Patient

        with SessionLocal() as session:
            # Check if exists
            if not skip_dedup:
                existing = session.query(Patient).filter_by(full_name=name).first()
                if existing:
                    logger.info(f"Patient already exists: {name}")
                    return existing.id

            new_patient = Patient(
                full_name=name,
                patient_type=patient_type,
                companion_of_id=companion_of_id,
                pending_arrival=pending_arrival,
            )
            session.add(new_patient)
            session.commit()

            logger.info(
                f"Added new patient: {name}  type={patient_type or 'general'}"
                f"  companion_of={companion_of_id}"
            )
            return new_patient.id

    except Exception as e:
        logger.error(f"Error adding patient: {e}")
        return None


def clear_pending_arrival_by_names(names: List[str]) -> int:
    """
    يُلغي علم pending_arrival عن أسماء "مريض جديد مع مرافقين" فور استخدامها
    فعلياً في تقرير وصول مؤكَّد — تختفي بذلك من شاشة "📋 الأسماء المعلّقة".
    مطابقة بالاسم الكامل (نفس أسلوب فحص التكرار في add_patient نفسها) —
    session.completed_patients لا يحمل معرّف السجل، فقط الاسم المُختار.
    Returns عدد الصفوف التي تغيّرت فعلاً.
    """
    if not names:
        return 0
    try:
        from db.session import SessionLocal
        from db.models import Patient

        with SessionLocal() as session:
            rows = (
                session.query(Patient)
                .filter(
                    Patient.full_name.in_(names),
                    Patient.patient_type.in_(["companion_parent", "companion"]),
                    Patient.pending_arrival.is_(True),
                )
                .all()
            )
            for row in rows:
                row.pending_arrival = False
            session.commit()
            return len(rows)
    except Exception as e:
        logger.error(f"Error clearing pending_arrival: {e}")
        return 0


def get_pending_arrival_names() -> List[Dict]:
    """
    عائلات "مريض جديد مع مرافقين" لم يُسجَّل وصولها بعد (pending_arrival=True)
    — تُستخدَم في شاشة "📋 الأسماء المعلّقة" ببوت الخدمات العامة.
    Returns [{"id": int, "name": str, "companions": [str, ...]}, ...]
    مرتَّبة الأحدث أولاً، بدون أي عنصر لا يملك patient_type="companion_parent".
    """
    try:
        from db.session import SessionLocal
        from db.models import Patient

        with SessionLocal() as session:
            parents = (
                session.query(Patient)
                .filter(
                    Patient.patient_type == "companion_parent",
                    Patient.pending_arrival.is_(True),
                    # ✅ من أُرشِف كمسافر لا يُنتظَر وصوله — يختفي من "الأسماء
                    # المعلّقة" أيضاً كبقية قوائم الاختيار (يعود تلقائياً
                    # بمجرد إعادته عبر زر "↩️ عاد").
                    Patient.archived_at.is_(None),
                )
                .order_by(Patient.created_at.desc())
                .all()
            )
            result = []
            for parent in parents:
                companions = (
                    session.query(Patient)
                    .filter(
                        Patient.patient_type == "companion",
                        Patient.companion_of_id == parent.id,
                        Patient.pending_arrival.is_(True),
                    )
                    .all()
                )
                result.append({
                    "id": parent.id,
                    "name": parent.full_name,
                    "companions": [c.full_name for c in companions],
                })
            return result
    except Exception as e:
        logger.error(f"Error fetching pending arrival names: {e}")
        return []


def get_companions_for_patient(patient_id: int) -> List[Dict]:
    """
    مرافقو مريض معيّن — يُقرأون من الرابط الذي يُسجّله الأدمن عند إضافة
    "مريض جديد مع مرافقين". يُستخدم في تدفق الواصلين ليُكمل بيانات المرافقين
    تلقائياً بلا سؤال المستخدم عن وجودهم ولا اختيارهم يدوياً.

    Returns: [{"id": int, "name": str}, ...]  (فارغة إن لم يكن له مرافقون)
    """
    try:
        from db.session import SessionLocal
        from db.models import Patient

        with SessionLocal() as session:
            rows = (
                session.query(Patient)
                .filter(Patient.companion_of_id == patient_id)
                .order_by(Patient.id)
                .all()
            )
            return [{"id": r.id, "name": r.full_name or ""} for r in rows]
    except Exception as e:
        logger.error(f"Error fetching companions for patient {patient_id}: {e}")
        return []


def search_patients(query: str, limit: int = 20) -> List[Dict]:
    """
    البحث عن المرضى
    """
    try:
        from db.session import SessionLocal
        from db.models import Patient
        
        with SessionLocal() as session:
            patients = session.query(Patient).filter(
                Patient.full_name.ilike(f"%{query}%")
            ).limit(limit).all()
            
            return [{
                'id': p.id,
                'name': p.full_name
            } for p in patients]
            
    except Exception as e:
        logger.error(f"Error searching patients: {e}")
        return []


def update_patient(patient_id: int, new_name: str) -> bool:
    """
    تعديل اسم مريض
    """
    try:
        from db.session import SessionLocal
        from db.models import Patient
        
        with SessionLocal() as session:
            patient = session.query(Patient).filter_by(id=patient_id).first()
            if patient:
                old_name = patient.full_name
                patient.full_name = new_name
                session.commit()
                logger.info(f"Updated patient from '{old_name}' to '{new_name}'")
                return True
            else:
                logger.warning(f"Patient with id {patient_id} not found")
                return False
                
    except Exception as e:
        logger.error(f"Error updating patient: {e}")
        return False


def delete_patient(patient_id: int) -> bool:
    """
    حذف مريض. ✅ إن كان هذا المريض "companion_parent" (له مرافقون مرتبطون
    عبر companion_of_id)، يُحذَف مرافقوه معه تلقائياً — بدونها كانت صفوف
    المرافقين تبقى يتيمة في قاعدة البيانات إلى الأبد بعد حذف المريض
    (لا تظهر في أي شاشة إدارة، ولا طريقة للوصول إليها لحذفها لاحقاً).
    حذف مرافق واحد بمفرده (لا يملك مرافقين هو نفسه) لا يُحدِث أي تسلسل.

    ✅ إن كان لهذا المريض شخص إقامة لم يُستكمَل بعد (WAITING_ARRIVAL بلا
    صورة مرفوعة)، يُحذَف معه أيضاً عبر
    modules.residency.models.delete_stub_person_by_name — بدونها كان
    يبقى يتيماً في "🪪 الإقامة" للأبد بلا أي مريض يشير إليه. أشخاص لهم
    تقدّم حقيقي (صورة مرفوعة، أو أي حالة أخرى) لا يُمَسّون إطلاقاً.
    """
    try:
        from db.session import SessionLocal
        from db.models import Patient

        with SessionLocal() as session:
            patient = session.query(Patient).filter_by(id=patient_id).first()
            if patient:
                name = patient.full_name
                companions = session.query(Patient).filter_by(companion_of_id=patient_id).all()
                for comp in companions:
                    logger.info(f"Deleting companion of patient #{patient_id}: {comp.full_name}")
                    session.delete(comp)
                session.delete(patient)
                session.commit()

                try:
                    from modules.residency.models import delete_stub_person_by_name
                    deleted_profiles = delete_stub_person_by_name(name)
                except Exception:
                    logger.exception(f"Failed to clean up residency stub for: {name} (non-fatal)")
                    deleted_profiles = 0

                logger.info(
                    f"Deleted patient: {name}  (+{len(companions)} companion(s), "
                    f"+{deleted_profiles} orphaned pending residency person(s))"
                )
                return True
            else:
                logger.warning(f"Patient with id {patient_id} not found")
                return False

    except Exception as e:
        logger.error(f"Error deleting patient: {e}")
        return False


def get_patients_paginated(page: int = 0, per_page: int = 10) -> tuple:
    """
    الحصول على المرضى مع التصفح بالصفحات (شاشات إدارة أسماء المرضى في الادمن)
    Returns: (patients_list, total_count, total_pages)

    ✅ المرافقون (patient_type="companion") مستبعدون من هذه الشاشات —
    شاشة "أسماء المرضى" تعرض المريض الرئيسي فقط، أما المرافقون فيظهرون
    فقط أثناء الإدخال الفعلي في زر "الواصلين" (عبر get_companions_for_patient،
    استعلام مستقل تماماً لا علاقة له بهذه الدالة).
    """
    try:
        from db.session import SessionLocal
        from db.models import Patient
        from sqlalchemy import or_

        with SessionLocal() as session:
            # ⚠️ patient_type فارغ (NULL) للمرضى العاديين — "!=" وحدها في SQL
            # تستبعد صفوف NULL أيضاً (NULL != 'companion' ليست TRUE)، فلا بد
            # من or_(...is_(None)) صراحة وإلا اختفى كل المرضى العاديين من القائمة.
            base_query = session.query(Patient).filter(
                or_(Patient.patient_type != "companion", Patient.patient_type.is_(None)),
                # ✅ المسافرون (المؤرشفون) لهم شاشتهم الخاصة "🧳 أرشيف
                # المسافرين" — تبقى هذه الشاشة معروضةً للنشطين فقط حتى يرى
                # الأدمن ما يراه المستخدمون بالضبط.
                Patient.archived_at.is_(None),
            )
            total_count = base_query.count()
            total_pages = (total_count + per_page - 1) // per_page

            patients = base_query.order_by(
                Patient.created_at.desc()
            ).offset(page * per_page).limit(per_page).all()

            result = [{
                'id': p.id,
                'name': p.full_name,
                'patient_type': p.patient_type,
                'created_at': p.created_at
            } for p in patients]

            return result, total_count, total_pages
            
    except Exception as e:
        logger.error(f"Error getting paginated patients: {e}")
        return [], 0, 0


def sync_arrivals_to_patient_registry(patients: list) -> tuple:
    """
    Upsert arrival patient names into the Master Patient Registry (patients table).

    Each dict in `patients` must have at least a "name" key.
    Companions inside each patient's "companions" list are also upserted.

    Returns (added_count, skipped_count).
    add_patient() already handles upsert: it returns the existing id when the
    name already exists, so we count "added" only when the record is truly new.
    """
    added   = 0
    skipped = 0

    for p in patients:
        name = (p.get("name") or "").strip()
        if not name:
            continue
        try:
            # Check existence before inserting so we can count accurately.
            existing = get_patient_by_name(name)
            add_patient(name)
            if existing:
                skipped += 1
            else:
                added += 1
        except Exception as exc:
            logger.error(f"[patients_service] sync upsert failed for {name!r}: {exc}")

        # Companions — same upsert logic
        for c in p.get("companions", []):
            c_name = (c.get("name") or "").strip()
            if not c_name:
                continue
            try:
                existing_c = get_patient_by_name(c_name)
                add_patient(c_name)
                if existing_c:
                    skipped += 1
                else:
                    added += 1
            except Exception as exc:
                logger.error(f"[patients_service] sync upsert failed for companion {c_name!r}: {exc}")

    logger.info(
        f"[patients_service] sync_arrivals_to_patient_registry"
        f"  added={added}  skipped={skipped}"
    )
    return added, skipped


def sync_file_to_database() -> int:
    """
    مزامنة المرضى من الملف إلى قاعدة البيانات
    Returns number of patients synced
    """
    file_names = get_patients_from_file()
    
    count = 0
    for name in file_names:
        if add_patient(name):
            count += 1
    
    logger.info(f"Synced {count} patients from file to database")
    return count


def get_patients_count() -> int:
    """
    عدد المرضى **النشطين** (مستبعِداً المرافقين والمسافرين المؤرشفين —
    نفس فلتر get_patients_paginated بالضبط)
    """
    try:
        from db.session import SessionLocal
        from db.models import Patient
        from sqlalchemy import or_

        with SessionLocal() as session:
            return session.query(Patient).filter(
                or_(Patient.patient_type != "companion", Patient.patient_type.is_(None)),
                Patient.archived_at.is_(None),
            ).count()
    except Exception:
        return len(get_patients_from_file())


# =============================================================================
# أرشفة المرضى المسافرين (soft archive)
# =============================================================================
# ⚠️ المبدأ: لا حذف إطلاقاً. الصف وكل بياناته التاريخية تبقى كما هي — يُضبَط
# `archived_at` فقط، فيختفي الاسم من **قوائم اختيار المرضى** وحدها (عبر
# `report_flow_patient_visible`/`_type_visible` في patient_selector/_data.py،
# مصدرَي الحقيقة الوحيدين لظهور المريض). التقارير والإحصائيات تقرأ جدول
# `Report` و`get_patient_by_id/by_name` ولا تمرّ بهذا الفلتر إطلاقاً.

def set_patient_archived(patient_id: int, archived: bool) -> Optional[str]:
    """يؤرشف مريضاً (سافر) أو يُعيده للقائمة النشطة (عاد).

    Returns: اسم المريض عند النجاح، أو None إن لم يوجد/حدث خطأ.
    """
    try:
        from datetime import datetime as _dt
        from db.session import SessionLocal
        from db.models import Patient

        with SessionLocal() as session:
            patient = session.query(Patient).filter_by(id=patient_id).first()
            if not patient:
                logger.warning(f"[archive] لا يوجد مريض بالمعرّف {patient_id}")
                return None
            name = patient.full_name
            patient.archived_at = _dt.utcnow() if archived else None
            session.commit()
            logger.info(
                f"[archive] {'أُرشِف' if archived else 'أُعيد'} المريض "
                f"id={patient_id} name={name!r}"
            )
            return name
    except Exception as exc:
        logger.error(f"[archive] فشل تغيير حالة الأرشفة id={patient_id}: {exc}", exc_info=True)
        return None


def get_patients_paginated_by_archive(
    page: int = 0, per_page: int = 10, archived: bool = False,
) -> tuple:
    """نفس فلتر `get_patients_paginated` (استبعاد المرافقين) لكن مقسوماً حسب
    حالة الأرشفة — لشاشة "🧳 أرشيف المسافرين" في الأدمن.

    archived=False ⇒ المرضى النشطون (`archived_at IS NULL`).
    archived=True  ⇒ المسافرون المؤرشفون فقط.

    Returns: (patients_list, total_count, total_pages)
    """
    try:
        from db.session import SessionLocal
        from db.models import Patient
        from sqlalchemy import or_

        with SessionLocal() as session:
            base_query = session.query(Patient).filter(
                # ⚠️ patient_type فارغ (NULL) للمرضى العاديين — انظر شرح
                # or_(...is_(None)) في get_patients_paginated أعلاه.
                or_(Patient.patient_type != "companion", Patient.patient_type.is_(None)),
                Patient.full_name.isnot(None),
                Patient.full_name != "",
            )
            if archived:
                base_query = base_query.filter(Patient.archived_at.isnot(None))
            else:
                base_query = base_query.filter(Patient.archived_at.is_(None))

            total_count = base_query.count()
            total_pages = (total_count + per_page - 1) // per_page

            # المؤرشفون: الأحدث سفراً أولاً. النشطون: أبجدياً (قائمة طويلة
            # يبحث فيها الأدمن بالاسم، لا بترتيب الإضافة).
            order = (
                Patient.archived_at.desc() if archived else Patient.full_name.asc()
            )
            patients = (
                base_query.order_by(order)
                .offset(page * per_page).limit(per_page).all()
            )

            result = [{
                'id': p.id,
                'name': p.full_name,
                'patient_type': p.patient_type,
                'archived_at': p.archived_at,
            } for p in patients]

            return result, total_count, total_pages

    except Exception as exc:
        logger.error(f"[archive] فشل جلب قائمة (archived={archived}): {exc}", exc_info=True)
        return [], 0, 0


def get_archived_patients_count() -> int:
    """عدد المرضى المؤرشفين (المسافرين) — لعرضه على زر الأرشيف."""
    try:
        from db.session import SessionLocal
        from db.models import Patient
        from sqlalchemy import or_

        with SessionLocal() as session:
            return session.query(Patient).filter(
                or_(Patient.patient_type != "companion", Patient.patient_type.is_(None)),
                Patient.archived_at.isnot(None),
            ).count()
    except Exception:
        return 0


# Compatibility alias
def load_patient_names() -> List[str]:
    """
    Alias for get_all_patient_names
    """
    return get_all_patient_names()


__all__ = [
    'get_all_patient_names',
    'get_all_patients',
    'get_patient_by_name',
    'get_patient_by_id',
    'add_patient',
    'update_patient',
    'delete_patient',
    'search_patients',
    'sync_arrivals_to_patient_registry',
    'sync_file_to_database',
    'get_patients_count',
    'get_patients_paginated',
    'load_patient_names',
]



# =============================================================================
# 🗑️ حذف كامل لاسم أُضيف عبر "🤝 مريض جديد مع مرافقين"
# =============================================================================
# ⚠️ لماذا دالة منفصلة عن delete_patient العادية: تلك تحذف صفوف `Patient`
# وتنظّف **فقط** أشخاص الإقامة غير المُستكمَلين (WAITING_ARRIVAL بلا صورة).
# أما اسم أُضيف عبر زر المرافقين ومرّ بتدفق الوصول أو أُدخِل عبر
# "🏠 الحالات الموجودة" فله أيضاً:
#   • صفوف `ResidencyPerson` بأي حالة (تظهر في بوت الإقامة)
#   • صفوف `ArrivalPatient`/`ArrivalCompanion` (تظهر في 🛫 المغادرين)
# وكانت تبقى بعد الحذف فتظهر أسماء تجريبية في البوتين بلا أي مريض يشير
# إليها. هذه الدالة تحذف الاسم من **كل** الأنظمة دفعة واحدة.
#
# 🔒 حارس البيانات: يُمنَع الحذف نهائياً إن كان للاسم أي تقرير طبي — نفس
# مبدأ "لا نحذف من له بيانات" الذي بُني لأجله أرشيف المسافرين. الأسماء
# التجريبية بلا تقارير فلا يعوقها الحارس.

# ── حذف الأسماء التجريبية من الأنظمة الثلاثة ─────────────────────────────────
# ⚠️ لماذا "مفتاح" نصّي بدل `patient_id`:
# النسخة الأولى من هذه الشاشة كانت تُدرِج `patient_type == "companion_parent"`
# وحدها وتُعرّف كل شيء بـ`patient_id`، فبقيت أسماء **لا تصلها الأداة إطلاقاً**:
#   • مريض أُدخِل عبر "🏠 الحالات الموجودة" (نوعه `general` + علَم
#     `gs_onboarded_at`) ⇒ يظهر في 🔧 الخدمات العامة بلا أي طريق لحذفه.
#   • **شخص إقامة يتيم** — صف في `res_persons` بلا أي صف مريض مطابق بالاسم
#     ⇒ يظهر في "🔴 معلّق انتهاء الإقامة" وأخواتها، ولا وجود لـ`patient_id`
#     أصلاً ليُبنى عليه أي إجراء.
#
# لذلك صار المُعرِّف نصّاً يحمل مصدره: `p-<patient_id>` أو `r-<res_person_id>`.
# (شرطة لا نقطتان — `callback_data` مُقسَّمة بـ":" في كل هذا الملف.)
_SRC_COMPANION = "🤝 زر المرافقين"
_SRC_LEGACY = "🏠 حالة موجودة"
_SRC_RESIDENCY = "🪪 وحدة الإقامة"


def _resolve_family(session, key: str):
    """المفتاح ⇒ (اسم الجذر, أسماء المرافقين, patient_id أو None).

    None إن لم يعد الصف موجوداً (حُذِف في جلسة أخرى).
    """
    from db.models import Patient, ResidencyPerson

    kind, _, raw = str(key or "").partition("-")
    try:
        row_id = int(raw)
    except (TypeError, ValueError):
        return None

    if kind == "p":
        p = session.query(Patient).filter_by(id=row_id).first()
        if not p:
            return None
        comps = session.query(Patient).filter_by(companion_of_id=p.id).all()
        return p.full_name, [c.full_name for c in comps if c.full_name], p.id

    if kind == "r":
        rp = session.query(ResidencyPerson).filter_by(id=row_id).first()
        if not rp:
            return None
        # مرافقو الإقامة = الأبناء في العلاقة الذاتية (parent_id = الجذر)
        kids = session.query(ResidencyPerson).filter_by(parent_id=rp.id).all()
        comp_names = [k.name for k in kids if k.name]
        # قد يوجد صف مريض بنفس الاسم (مريض عادي) — يُحذَف معه إن وُجد
        p = session.query(Patient).filter_by(full_name=rp.name).first()
        return rp.name, comp_names, (p.id if p else None)

    return None


def get_deletable_families(page: int = 0, per_page: int = 8) -> tuple:
    """كل اسم يمكن حذفه من الأنظمة الثلاثة، أياً كان الزر الذي أنشأه.

    ثلاثة مصادر مُوحَّدة بلا تكرار: مرضى زر المرافقين، مرضى "الحالات
    الموجودة"، وجذور `res_persons` التي لا يغطّيها أيٌّ منهما — وهي بالذات
    ما كان يتعذّر حذفه. Returns: (list, total, pages)
    """
    try:
        from sqlalchemy import or_
        from db.session import SessionLocal
        from db.models import Patient, ResidencyPerson

        with SessionLocal() as session:
            cands: list = []
            seen_names: set = set()

            patients = (
                session.query(Patient)
                .filter(
                    Patient.full_name.isnot(None),
                    Patient.full_name != "",
                    or_(
                        Patient.patient_type == "companion_parent",
                        Patient.gs_onboarded_at.isnot(None),
                    ),
                )
                .order_by(Patient.created_at.desc())
                .all()
            )
            for p in patients:
                n_comp = session.query(Patient).filter_by(companion_of_id=p.id).count()
                cands.append({
                    "key": f"p-{p.id}",
                    "name": p.full_name,
                    "companions": n_comp,
                    "source": (_SRC_COMPANION if p.patient_type == "companion_parent"
                               else _SRC_LEGACY),
                })
                seen_names.add(p.full_name)

            # جذور الإقامة غير المُغطّاة أعلاه (تشمل الأيتام تماماً)
            roots = (
                session.query(ResidencyPerson)
                .filter(ResidencyPerson.parent_id.is_(None))
                .order_by(ResidencyPerson.id.desc())
                .all()
            )
            for rp in roots:
                if not rp.name or rp.name in seen_names:
                    continue
                n_comp = session.query(ResidencyPerson).filter_by(parent_id=rp.id).count()
                cands.append({
                    "key": f"r-{rp.id}",
                    "name": rp.name,
                    "companions": n_comp,
                    "source": _SRC_RESIDENCY,
                })
                seen_names.add(rp.name)

            total = len(cands)
            pages = max(1, (total + per_page - 1) // per_page)
            return cands[page * per_page: (page + 1) * per_page], total, pages
    except Exception as exc:
        logger.error(f"[pcdel] فشل جلب الأسماء القابلة للحذف: {exc}", exc_info=True)
        return [], 0, 0


def get_deletable_family_impact(key: str):
    """ما الذي سيُحذَف فعلاً لهذا المفتاح — يُعرَض للأدمن قبل التأكيد.

    يشمل عدد التقارير الطبية (حارس الحذف): أي رقم > 0 يمنع الحذف.
    """
    try:
        from db.session import SessionLocal
        from db.models import (
            Patient, Report, ResidencyPerson, ArrivalPatient, ArrivalCompanion,
        )

        with SessionLocal() as session:
            resolved = _resolve_family(session, key)
            if resolved is None:
                return None
            name, comp_names, patient_id = resolved
            all_names = [n for n in ([name] + comp_names) if n]

            # ⚠️ لا رابط FK بين سجلّ المرضى وجدولَي الإقامة/الوصول —
            # المطابقة بالاسم الحرفي، نفس النمط المُتَّبع في كل المشروع.
            res_ids = [
                p.id for p in session.query(ResidencyPerson)
                .filter(ResidencyPerson.name.in_(all_names)).all()
            ]
            arr = session.query(ArrivalPatient).filter(
                ArrivalPatient.name.in_(all_names)).all()
            arr_comp = 0
            for a in arr:
                arr_comp += session.query(ArrivalCompanion).filter_by(patient_id=a.id).count()
            if comp_names:
                arr_comp += session.query(ArrivalCompanion).filter(
                    ArrivalCompanion.name.in_(comp_names)).count()

            patients = session.query(Patient).filter(
                Patient.full_name.in_(all_names)).count()

            reports = session.query(Report).filter(
                Report.patient_name.in_(all_names)).count()
            if patient_id is not None:
                reports += session.query(Report).filter(
                    Report.patient_id == patient_id).count()

            return {
                "key": key,
                "id": patient_id,
                "name": name,
                "companions": comp_names,
                "patients": patients,
                "residency": len(res_ids),
                "arrivals": len(arr),
                "arrival_companions": arr_comp,
                "reports": reports,
            }
    except Exception as exc:
        logger.error(f"[pcdel] فشل حساب أثر الحذف key={key}: {exc}", exc_info=True)
        return None


def purge_deletable_family(key: str) -> tuple:
    """يحذف الاسم ومرافقيه من **كل** الأنظمة. Returns: (نجاح, رسالة/ملخص).

    🔒 يرفض الحذف إن وُجد أي تقرير طبي مرتبط (حماية بيانات التقارير).
    """
    impact = get_deletable_family_impact(key)
    if impact is None:
        return False, "لم يُعثر على الاسم."
    if impact["reports"]:
        return False, (
            f"لهذا الاسم {impact['reports']} تقرير طبي — الحذف ممنوع حفاظاً "
            f"على بيانات التقارير. استخدم 🧳 أرشيف المسافرين لإخفائه بدل حذفه."
        )

    try:
        from db.session import SessionLocal
        from db.models import (
            Patient, ResidencyPerson, ResidencyStatusLog, ResidencyDocument,
            ResidencyIssuance, ArrivalPatient, ArrivalCompanion,
        )

        all_names = [n for n in ([impact["name"]] + list(impact["companions"])) if n]
        patient_id = impact["id"]

        with SessionLocal() as session:
            # (1) أشخاص الإقامة + كل ما يتعلّق بهم
            res_people = session.query(ResidencyPerson).filter(
                ResidencyPerson.name.in_(all_names)).all()
            for rp in res_people:
                session.query(ResidencyStatusLog).filter_by(person_id=rp.id).delete()
                session.query(ResidencyDocument).filter_by(person_id=rp.id).delete()
                session.query(ResidencyIssuance).filter_by(person_id=rp.id).delete()
                session.delete(rp)

            # (2) صفوف الوصول (تُغذّي 🛫 المغادرين)
            arrivals = session.query(ArrivalPatient).filter(
                ArrivalPatient.name.in_(all_names)).all()
            for a in arrivals:
                session.query(ArrivalCompanion).filter_by(patient_id=a.id).delete()
                session.delete(a)
            if impact["companions"]:
                session.query(ArrivalCompanion).filter(
                    ArrivalCompanion.name.in_(impact["companions"])).delete(
                    synchronize_session=False)

            # (3) سجلّ المرضى — بالرابط (يلتقط مرافقاً سُمّي باسم مختلف)
            #     وبالاسم (يغطّي مفتاح `r-` الذي قد لا يملك patient_id أصلاً)
            if patient_id is not None:
                session.query(Patient).filter_by(companion_of_id=patient_id).delete(
                    synchronize_session=False)
            session.query(Patient).filter(
                Patient.full_name.in_(all_names)).delete(synchronize_session=False)

            session.commit()

        logger.info(
            "[pcdel] purged %r (key=%s): %d companion(s), %d residency person(s), "
            "%d arrival row(s)",
            impact["name"], key, len(impact["companions"]),
            impact["residency"], impact["arrivals"],
        )
        return True, impact["name"]
    except Exception as exc:
        logger.error(f"[pcdel] فشل الحذف key={key}: {exc}", exc_info=True)
        return False, str(exc)[:150]
