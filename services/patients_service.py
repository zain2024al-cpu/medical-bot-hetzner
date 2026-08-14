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

    ✅ إن كان لهذا المريض ملف إقامة (ResidencyProfile.name مطابق) ما زال
    "pending_documents" (لا صورة ولا فورم C — مجرد ملف فارغ لم يُستكمَل
    بعد)، يُحذَف معه أيضاً — بدونها كان يبقى ملفاً يتيماً في "📋 الملفات
    المعلّقة" للأبد بلا أي مريض يشير إليه. ملفات ذات تقدّم حقيقي (وثائق/
    حالة أخرى) لا تُمَسّ إطلاقاً — الحذف يقتصر على الملفات الفارغة تماماً.
    """
    try:
        from db.session import SessionLocal
        from db.models import Patient, ResidencyProfile, ResidencyCompanion, ResidencyUpdate

        with SessionLocal() as session:
            patient = session.query(Patient).filter_by(id=patient_id).first()
            if patient:
                name = patient.full_name
                companions = session.query(Patient).filter_by(companion_of_id=patient_id).all()
                for comp in companions:
                    logger.info(f"Deleting companion of patient #{patient_id}: {comp.full_name}")
                    session.delete(comp)
                session.delete(patient)

                stale_profiles = (
                    session.query(ResidencyProfile)
                    .filter_by(name=name, status="pending_documents")
                    .filter(
                        (ResidencyProfile.photo_file_id == "") | (ResidencyProfile.photo_file_id.is_(None)),
                        (ResidencyProfile.form_c_file_id == "") | (ResidencyProfile.form_c_file_id.is_(None)),
                    )
                    .all()
                )
                for pr in stale_profiles:
                    session.query(ResidencyUpdate).filter_by(profile_id=pr.id).delete()
                    session.query(ResidencyCompanion).filter_by(profile_id=pr.id).delete()
                    session.delete(pr)
                    logger.info(f"Deleted orphaned pending residency profile #{pr.id} for: {name}")

                session.commit()
                logger.info(
                    f"Deleted patient: {name}  (+{len(companions)} companion(s), "
                    f"+{len(stale_profiles)} orphaned pending residency profile(s))"
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
                or_(Patient.patient_type != "companion", Patient.patient_type.is_(None))
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
    عدد المرضى (مستبعِداً المرافقين — نفس فلتر get_patients_paginated)
    """
    try:
        from db.session import SessionLocal
        from db.models import Patient
        from sqlalchemy import or_

        with SessionLocal() as session:
            return session.query(Patient).filter(
                or_(Patient.patient_type != "companion", Patient.patient_type.is_(None))
            ).count()
    except Exception:
        return len(get_patients_from_file())


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

