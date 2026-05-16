# -*- coding: utf-8 -*-
"""
خدمة المستشفيات الموحدة
Unified Hospitals Service - Single Source of Truth
"""

import json
import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Cache
_HOSPITALS_DATA = None
_HOSPITALS_LIST = []

# Names that are UI buttons (not real hospitals) and must never appear in lists.
_INVALID_HOSPITAL_NAMES = {
    "📅 إدارة الجدول",
    "👥 إدارة المستخدمين",
    "📊 تقييم المترجمين",
}

def _get_custom_order_path() -> str:
    # ملف ترتيب بسيط: كل سطر اسم مستشفى (بالضبط كما يظهر)
    return os.path.join(os.path.dirname(__file__), "..", "data", "hospitals_order.txt")


def _apply_custom_order(names: List[str]) -> List[str]:
    """
    Apply a user-defined priority order.
    - Hospitals listed in hospitals_order.txt come first in that exact order.
    - Remaining hospitals keep their current order.
    """
    try:
        path = _get_custom_order_path()
        if not os.path.exists(path):
            return names
        with open(path, "r", encoding="utf-8") as f:
            wanted = [ln.strip() for ln in f.read().splitlines() if ln.strip() and not ln.strip().startswith("#")]
        if not wanted:
            return names

        index = {n.strip(): i for i, n in enumerate(wanted)}

        # stable: keep original relative order for non-specified hospitals
        def key(n: str):
            return (0, index.get(n.strip(), 10**9)) if n.strip() in index else (1, 10**9)

        # But we must keep stable order for those not in index; Python sort is stable.
        return sorted(names, key=key)
    except Exception as e:
        logger.warning(f"⚠️ Could not apply custom hospital order: {e}")
        return names


def _get_data_path():
    """الحصول على مسار ملف البيانات"""
    possible_paths = [
        os.path.join(os.path.dirname(__file__), '..', 'data', 'doctors_unified.json'),
        'data/doctors_unified.json',
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None


def _load_data():
    """تحميل البيانات"""
    global _HOSPITALS_DATA, _HOSPITALS_LIST
    
    if _HOSPITALS_DATA is not None:
        return _HOSPITALS_DATA
    
    data_path = _get_data_path()
    if not data_path:
        logger.error("لم يتم العثور على ملف doctors_unified.json")
        return None
    
    try:
        with open(data_path, 'r', encoding='utf-8') as f:
            _HOSPITALS_DATA = json.load(f)
        
        # Build hospitals list
        _HOSPITALS_LIST = [h['name'] for h in _HOSPITALS_DATA.get('hospitals', [])]
        
        logger.info(f"Loaded {len(_HOSPITALS_LIST)} hospitals")
        
    except Exception as e:
        logger.error(f"خطأ في تحميل بيانات المستشفيات: {e}")
        _HOSPITALS_DATA = {"hospitals": [], "doctors": []}
        _HOSPITALS_LIST = []
    
    return _HOSPITALS_DATA


def get_all_hospitals() -> List[str]:
    """
    الحصول على جميع أسماء المستشفيات
    Returns list of hospital names
    """
    # ✅ مصدر الحقيقة: قاعدة البيانات (Hospital table)
    try:
        from db.session import SessionLocal
        from db.models import Hospital
        with SessionLocal() as s:
            rows = s.query(Hospital).order_by(Hospital.name).all()
            if rows:
                names = [r.name for r in rows if r.name and r.name.strip() and r.name.strip() not in _INVALID_HOSPITAL_NAMES]
                # dedupe while preserving DB order
                seen = set()
                out = []
                for n in names:
                    k = n.strip().lower()
                    if k in seen:
                        continue
                    seen.add(k)
                    out.append(n)
                return _apply_custom_order(out)
    except Exception as e:
        logger.warning(f"⚠️ Could not load hospitals from DB in hospitals_service: {e}")

    # fallback قديم: JSON
    _load_data()
    return _apply_custom_order(_HOSPITALS_LIST.copy())


def get_hospitals_with_details() -> List[Dict]:
    """
    الحصول على المستشفيات مع التفاصيل
    Returns list of hospital dicts with id, name, departments, doctor_count.
    DB is authoritative for name; JSON provides supplementary fields (departments, doctor_count).
    """
    # DB-first: build a name-keyed index from Hospital table
    db_names = []
    try:
        from db.session import SessionLocal
        from db.models import Hospital
        with SessionLocal() as s:
            rows = s.query(Hospital).order_by(Hospital.name).all()
            db_names = [
                r.name for r in rows
                if r.name and r.name.strip() and r.name.strip() not in _INVALID_HOSPITAL_NAMES
            ]
    except Exception as e:
        logger.warning("get_hospitals_with_details: DB read failed, falling back to JSON: %s", e)

    if db_names:
        # Merge with JSON supplementary data (departments, doctor_count) where available
        json_data = _load_data()
        json_index = {}
        if json_data:
            for h in json_data.get('hospitals', []):
                key = (h.get('name') or '').strip().lower()
                if key:
                    json_index[key] = h

        result = []
        for name in db_names:
            key = name.strip().lower()
            json_entry = json_index.get(key, {})
            result.append({
                'id': json_entry.get('id'),
                'name': name,
                'name_normalized': name.lower().strip(),
                'departments': json_entry.get('departments', []),
                'doctor_count': json_entry.get('doctor_count', 0),
            })
        return result

    # fallback: JSON only (no DB rows or DB unavailable)
    data = _load_data()
    return data.get('hospitals', []) if data else []


def get_hospital_by_name(hospital_name: str) -> Optional[Dict]:
    """
    البحث عن مستشفى بالاسم
    """
    data = _load_data()
    if not data:
        return None
    
    hospital_lower = hospital_name.lower().strip()
    
    for hospital in data.get('hospitals', []):
        if hospital['name'].lower() == hospital_lower:
            return hospital
        # Partial match
        if hospital_lower in hospital['name'].lower() or hospital['name'].lower() in hospital_lower:
            return hospital
    
    return None


def get_hospital_departments(hospital_name: str) -> List[str]:
    """
    الحصول على أقسام مستشفى معين
    """
    hospital = get_hospital_by_name(hospital_name)
    if not hospital:
        return []
    
    return [d['name'] for d in hospital.get('departments', [])]


def add_hospital(hospital_name: str) -> bool:
    """إضافة مستشفى جديد — DB هي المصدر الوحيد."""
    name_clean = (hospital_name or "").strip()
    if not name_clean:
        return False
    if name_clean in _INVALID_HOSPITAL_NAMES:
        logger.warning("Rejected invalid hospital name: %r", name_clean)
        return False
    try:
        from db.session import SessionLocal
        from db.models import Hospital
        with SessionLocal() as s:
            if not s.query(Hospital).filter(Hospital.name == name_clean).first():
                s.add(Hospital(name=name_clean))
                s.commit()
                logger.info("Added hospital to DB: %s", name_clean)
        return True
    except Exception as e:
        logger.error("Failed to add hospital to DB: %s", e)
        return False


def delete_hospital(hospital_name: str) -> bool:
    """حذف مستشفى — DB هي المصدر الوحيد."""
    name_clean = (hospital_name or "").strip()
    if not name_clean:
        return False
    try:
        from db.session import SessionLocal
        from db.models import Hospital
        with SessionLocal() as s:
            row = s.query(Hospital).filter(Hospital.name == name_clean).first()
            if not row:
                row = s.query(Hospital).filter(Hospital.name.ilike(name_clean)).first()
            if row:
                s.delete(row)
                s.commit()
                logger.info("Deleted hospital from DB: %s", name_clean)
                return True
            logger.warning("Hospital not found for delete: %s", name_clean)
            return False
    except Exception as e:
        logger.error("Failed to delete hospital from DB: %s", e)
        return False


def update_hospital(old_name: str, new_name: str) -> bool:
    """تعديل اسم مستشفى — DB هي المصدر الوحيد."""
    old_clean = (old_name or "").strip()
    new_clean = (new_name or "").strip()
    if not old_clean or not new_clean:
        return False
    try:
        from db.session import SessionLocal
        from db.models import Hospital
        with SessionLocal() as s:
            row = s.query(Hospital).filter(Hospital.name == old_clean).first()
            if not row:
                row = s.query(Hospital).filter(Hospital.name.ilike(old_clean)).first()
            if row:
                row.name = new_clean
                s.commit()
                logger.info("Updated hospital in DB: %s -> %s", old_clean, new_clean)
                return True
            logger.warning("Hospital not found for update: %s", old_clean)
            return False
    except Exception as e:
        logger.error("Failed to update hospital in DB: %s", e)
        return False


def reload_hospitals():
    """إعادة تحميل البيانات — لا يوجد cache مستقل، DB تُقرأ مباشرة دائماً."""
    global _HOSPITALS_DATA, _HOSPITALS_LIST
    _HOSPITALS_DATA = None
    _HOSPITALS_LIST = []


def get_hospitals_count() -> int:
    """عدد المستشفيات من DB."""
    try:
        from db.session import SessionLocal
        from db.models import Hospital
        with SessionLocal() as s:
            return s.query(Hospital).count()
    except Exception:
        return 0


# Alias for compatibility
PREDEFINED_HOSPITALS = property(lambda self: get_all_hospitals())


__all__ = [
    'get_all_hospitals',
    'get_hospitals_with_details', 
    'get_hospital_by_name',
    'get_hospital_departments',
    'add_hospital',
    'delete_hospital',
    'update_hospital',
    'reload_hospitals',
    'get_hospitals_count',
]

