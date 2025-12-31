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
    _load_data()
    return _HOSPITALS_LIST.copy()


def get_hospitals_with_details() -> List[Dict]:
    """
    الحصول على المستشفيات مع التفاصيل
    Returns list of hospital dicts with id, name, departments, doctor_count
    """
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
    """
    إضافة مستشفى جديد
    """
    global _HOSPITALS_DATA, _HOSPITALS_LIST
    
    _load_data()
    
    if not _HOSPITALS_DATA:
        return False
    
    # Check if already exists
    if hospital_name in _HOSPITALS_LIST:
        return True
    
    # Add new hospital
    new_id = max((h.get('id', 0) for h in _HOSPITALS_DATA.get('hospitals', [])), default=0) + 1
    
    new_hospital = {
        "id": new_id,
        "name": hospital_name,
        "name_normalized": hospital_name.lower().strip(),
        "departments": [],
        "doctor_count": 0
    }
    
    _HOSPITALS_DATA['hospitals'].append(new_hospital)
    _HOSPITALS_LIST.append(hospital_name)
    _HOSPITALS_DATA['statistics']['total_hospitals'] = len(_HOSPITALS_DATA['hospitals'])
    
    # Save to file
    try:
        data_path = _get_data_path()
        if data_path:
            with open(data_path, 'w', encoding='utf-8') as f:
                json.dump(_HOSPITALS_DATA, f, ensure_ascii=False, indent=2)
            logger.info(f"Added new hospital: {hospital_name}")
            return True
    except Exception as e:
        logger.error(f"Failed to save new hospital: {e}")
        return False
    
    return False


def delete_hospital(hospital_name: str) -> bool:
    """
    حذف مستشفى
    """
    global _HOSPITALS_DATA, _HOSPITALS_LIST
    
    _load_data()
    
    if not _HOSPITALS_DATA:
        return False
    
    # Find and remove hospital
    hospital_name_lower = hospital_name.lower().strip()
    
    for i, hospital in enumerate(_HOSPITALS_DATA.get('hospitals', [])):
        if hospital['name'].lower().strip() == hospital_name_lower:
            # Remove from data
            _HOSPITALS_DATA['hospitals'].pop(i)
            
            # Remove from cache
            if hospital['name'] in _HOSPITALS_LIST:
                _HOSPITALS_LIST.remove(hospital['name'])
            
            # Update statistics
            _HOSPITALS_DATA['statistics']['total_hospitals'] = len(_HOSPITALS_DATA['hospitals'])
            
            # Save to file
            try:
                data_path = _get_data_path()
                if data_path:
                    with open(data_path, 'w', encoding='utf-8') as f:
                        json.dump(_HOSPITALS_DATA, f, ensure_ascii=False, indent=2)
                    logger.info(f"Deleted hospital: {hospital_name}")
                    return True
            except Exception as e:
                logger.error(f"Failed to save after deleting hospital: {e}")
                return False
    
    return False


def update_hospital(old_name: str, new_name: str) -> bool:
    """
    تعديل اسم مستشفى
    """
    global _HOSPITALS_DATA, _HOSPITALS_LIST
    
    _load_data()
    
    if not _HOSPITALS_DATA:
        return False
    
    old_name_lower = old_name.lower().strip()
    
    for hospital in _HOSPITALS_DATA.get('hospitals', []):
        if hospital['name'].lower().strip() == old_name_lower:
            # Update hospital name
            old_hospital_name = hospital['name']
            hospital['name'] = new_name
            hospital['name_normalized'] = new_name.lower().strip()
            
            # Update doctors that belong to this hospital
            for doctor in _HOSPITALS_DATA.get('doctors', []):
                if doctor.get('hospital_name', '').lower().strip() == old_name_lower:
                    doctor['hospital_name'] = new_name
            
            # Update cache
            if old_hospital_name in _HOSPITALS_LIST:
                idx = _HOSPITALS_LIST.index(old_hospital_name)
                _HOSPITALS_LIST[idx] = new_name
            
            # Save to file
            try:
                data_path = _get_data_path()
                if data_path:
                    with open(data_path, 'w', encoding='utf-8') as f:
                        json.dump(_HOSPITALS_DATA, f, ensure_ascii=False, indent=2)
                    logger.info(f"Updated hospital: {old_name} -> {new_name}")
                    return True
            except Exception as e:
                logger.error(f"Failed to save after updating hospital: {e}")
                return False
    
    return False


def reload_hospitals():
    """
    إعادة تحميل البيانات
    """
    global _HOSPITALS_DATA, _HOSPITALS_LIST
    _HOSPITALS_DATA = None
    _HOSPITALS_LIST = []
    _load_data()


def get_hospitals_count() -> int:
    """
    عدد المستشفيات
    """
    _load_data()
    return len(_HOSPITALS_LIST)


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

