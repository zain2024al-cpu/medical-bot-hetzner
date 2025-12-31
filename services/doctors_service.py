# -*- coding: utf-8 -*-
"""
خدمة الأطباء - فلترة دقيقة وسريعة
Doctors Service - Fast and Accurate Filtering
"""

import json
import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# كاش للبيانات
_DOCTORS_DATA = None
_HOSPITALS_INDEX = {}  # hospital_id -> hospital
_DOCTORS_BY_HOSPITAL = {}  # hospital_id -> [doctors]
_DOCTORS_BY_HOSPITAL_DEPT = {}  # (hospital_id, dept_ar) -> [doctors]


def _get_data_path():
    """الحصول على مسار ملف البيانات"""
    possible_paths = [
        os.path.join(os.path.dirname(__file__), '..', 'data', 'doctors_unified.json'),
        'data/doctors_unified.json',
        '../data/doctors_unified.json',
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None


def _load_data():
    """تحميل البيانات وبناء الفهارس"""
    global _DOCTORS_DATA, _HOSPITALS_INDEX, _DOCTORS_BY_HOSPITAL, _DOCTORS_BY_HOSPITAL_DEPT
    
    if _DOCTORS_DATA is not None:
        return _DOCTORS_DATA
    
    data_path = _get_data_path()
    if not data_path:
        logger.error("لم يتم العثور على ملف doctors_unified.json")
        return None
    
    try:
        with open(data_path, 'r', encoding='utf-8') as f:
            _DOCTORS_DATA = json.load(f)
        
        # بناء فهرس المستشفيات
        for hospital in _DOCTORS_DATA.get('hospitals', []):
            _HOSPITALS_INDEX[hospital['id']] = hospital
            _HOSPITALS_INDEX[hospital['name'].lower()] = hospital
            # أيضاً بالاسم الأصلي
            _HOSPITALS_INDEX[hospital['name']] = hospital
        
        # Build doctor index
        for doctor in _DOCTORS_DATA.get('doctors', []):
            hospital_id = doctor['hospital_id']
            dept = doctor.get('department', '').lower()
            
            # Index by hospital
            if hospital_id not in _DOCTORS_BY_HOSPITAL:
                _DOCTORS_BY_HOSPITAL[hospital_id] = []
            _DOCTORS_BY_HOSPITAL[hospital_id].append(doctor)
            
            # Index by hospital and department
            key = (hospital_id, dept)
            if key not in _DOCTORS_BY_HOSPITAL_DEPT:
                _DOCTORS_BY_HOSPITAL_DEPT[key] = []
            _DOCTORS_BY_HOSPITAL_DEPT[key].append(doctor)
        
        logger.info(f"Loaded {len(_DOCTORS_DATA.get('doctors', []))} doctors from unified database")
        
    except Exception as e:
        logger.error(f"خطأ في تحميل بيانات الأطباء: {e}")
        _DOCTORS_DATA = {"hospitals": [], "doctors": []}
    
    return _DOCTORS_DATA


def get_all_hospitals() -> List[Dict]:
    """الحصول على جميع المستشفيات"""
    data = _load_data()
    return data.get('hospitals', []) if data else []


def get_hospital_by_name(hospital_name: str) -> Optional[Dict]:
    """البحث عن مستشفى بالاسم"""
    _load_data()
    
    # بحث مباشر
    if hospital_name in _HOSPITALS_INDEX:
        return _HOSPITALS_INDEX[hospital_name]
    
    # بحث بالاسم المصغر
    hospital_lower = hospital_name.lower().strip()
    if hospital_lower in _HOSPITALS_INDEX:
        return _HOSPITALS_INDEX[hospital_lower]
    
    # بحث بالتطابق الجزئي
    for key, hospital in _HOSPITALS_INDEX.items():
        if isinstance(key, str):
            if hospital_lower in key.lower() or key.lower() in hospital_lower:
                return hospital
    
    return None


def get_doctors_by_hospital(hospital_name: str) -> List[Dict]:
    """
    الحصول على الأطباء بالمستشفى فقط
    """
    _load_data()
    
    hospital = get_hospital_by_name(hospital_name)
    if not hospital:
        logger.warning(f"لم يتم العثور على المستشفى: {hospital_name}")
        return []
    
    hospital_id = hospital['id']
    doctors = _DOCTORS_BY_HOSPITAL.get(hospital_id, [])
    
    logger.info(f"تم العثور على {len(doctors)} طبيب في المستشفى: {hospital_name}")
    return doctors


def get_doctors_by_hospital_and_department(
    hospital_name: str, 
    department_name: str
) -> List[Dict]:
    """
    Get doctors by hospital and department - precise filtering
    Supports both Arabic and English department names
    """
    _load_data()
    
    hospital = get_hospital_by_name(hospital_name)
    if not hospital:
        logger.warning(f"Hospital not found: {hospital_name}")
        return []
    
    hospital_id = hospital['id']
    
    # استخراج الاسم الإنجليزي من الاختيار (إذا كان بصيغة "عربي | إنجليزي")
    dept_search_terms = []
    if '|' in department_name:
        parts = department_name.split('|')
        for part in parts:
            dept_search_terms.append(part.strip().lower())
    else:
        dept_search_terms.append(department_name.lower().strip())
    
    logger.info(f"Searching doctors with terms: {dept_search_terms}")
    
    # دائماً نستخدم البحث بالكلمات المفتاحية للعثور على جميع الأقسام المتعلقة
    # مثل: "ENT" يجب أن يجد "ENT" و "ENT & Skull Base Surgery"
    all_hospital_doctors = _DOCTORS_BY_HOSPITAL.get(hospital_id, [])
    filtered = []
    
    # تعريف كلمات مفتاحية للمطابقة - موسع ليشمل جميع الأقسام
    keyword_mapping = {
        # ENT
        'ent': ['ent', 'ear', 'nose', 'throat', 'hearing', 'implantology'],
        # Cardiology & Cardiac Surgery
        'cardiology': ['cardiology', 'cardiac', 'heart', 'cardiovascular', 'electrophysiology'],
        'cardiac surgery': ['cardiac surgery', 'ctvs', 'cardiothoracic'],
        # Orthopedics
        'orthopedic': ['orthopedic', 'orthopaedic', 'bone', 'joint', 'spine', 'arthroplasty', 'arthroscopy'],
        # Surgery
        'surgery': ['surgery', 'surgical'],
        'general surgery': ['general surgery', 'laparoscopic'],
        # Gastroenterology
        'gastro': ['gastro', 'gastroenterology', 'hepatology', 'liver', 'gi'],
        # Neurology & Neurosurgery
        'neuro': ['neuro', 'neurology', 'neurosurgery', 'brain', 'spine'],
        # Oncology
        'oncology': ['oncology', 'cancer', 'tumor', 'tumour'],
        # Pediatrics
        'pediatric': ['pediatric', 'paediatric', 'child', 'neonatal', 'neonatology'],
        # Ophthalmology
        'ophthalmology': ['ophthalmology', 'eye', 'retina', 'cataract', 'glaucoma', 'cornea', 'vitreo'],
        # Urology
        'urology': ['urology', 'urological', 'kidney transplant'],
        # Dermatology
        'dermatology': ['dermatology', 'skin', 'cosmetology'],
        # Psychiatry
        'psychiatry': ['psychiatry', 'mental', 'psychology', 'behavioral'],
        # Pulmonology
        'pulmonology': ['pulmonology', 'lung', 'respiratory', 'pulmonary'],
        # Nephrology
        'nephrology': ['nephrology', 'kidney', 'renal'],
        # Endocrinology
        'endocrinology': ['endocrinology', 'diabetes', 'hormone', 'diabetology'],
        # Rheumatology
        'rheumatology': ['rheumatology', 'arthritis', 'immunology'],
        # Radiology
        'radiology': ['radiology', 'imaging', 'x-ray', 'radiodiagnosis', 'nuclear'],
        # OB/GYN
        'obstetrics': ['obstetrics', 'gynecology', 'gynaecology', 'obg', 'fertility', 'ivf'],
        # Emergency
        'emergency': ['emergency', 'trauma', 'accident'],
        # Anesthesia
        'anesthesia': ['anesthesia', 'anaesthesia', 'anesthesiology', 'anaesthesiology'],
        # Critical Care
        'critical care': ['critical care', 'icu', 'intensive care'],
        # Physical Therapy
        'physical therapy': ['physical therapy', 'rehabilitation', 'physiotherapy', 'rehab'],
        # Pain Management
        'pain management': ['pain', 'palliative'],
        # Plastic Surgery
        'plastic surgery': ['plastic', 'reconstructive', 'cosmetic', 'aesthetic'],
        # Vascular
        'vascular': ['vascular', 'endovascular'],
        # Hepatology & Liver
        'hepatology': ['hepatology', 'liver', 'hepato'],
        # Hematology
        'hematology': ['hematology', 'haematology', 'bmt', 'bone marrow'],
        # Infectious Disease
        'infectious': ['infectious', 'infection'],
        # Internal Medicine
        'internal medicine': ['internal medicine', 'general medicine', 'physician'],
        # Dentistry
        'dentistry': ['dental', 'dentistry'],
        # Oral & Maxillofacial Surgery (جراحة الوجه والفكين)
        'maxillofacial': ['maxillofacial', 'oral surgery', 'maxillofacial surgery', 'oral maxillofacial'],
    }
    
    import re
    
    def word_match(search: str, target: str) -> bool:
        """مطابقة الكلمات كاملة فقط - لا جزئية"""
        # تنظيف وتقسيم الكلمات
        search_words = re.findall(r'\b\w+\b', search.lower())
        target_words = re.findall(r'\b\w+\b', target.lower())
        
        for sw in search_words:
            if len(sw) < 2:
                continue
            for tw in target_words:
                # مطابقة كلمات كاملة فقط
                if sw == tw:
                    return True
                # السماح بمطابقة بداية الكلمة للكلمات الطويلة (> 4 أحرف)
                if len(sw) > 4 and tw.startswith(sw):
                    return True
        return False
    
    def has_word(word: str, text: str) -> bool:
        """تحقق من وجود كلمة كاملة في النص"""
        pattern = r'\b' + re.escape(word) + r'\b'
        return bool(re.search(pattern, text, re.IGNORECASE))
    
    for doctor in all_hospital_doctors:
        doc_dept = doctor.get('department', '').lower()
        matched = False
        
        for search_term in dept_search_terms:
            # مطابقة كلمات كاملة
            if word_match(search_term, doc_dept):
                matched = True
                break
            
            # Keyword match - مطابقة كلمات كاملة فقط
            for key, synonyms in keyword_mapping.items():
                # تحقق من وجود أي مرادف في البحث ككلمة كاملة
                search_has_keyword = any(has_word(syn, search_term) for syn in synonyms)
                if search_has_keyword:
                    # تحقق من وجود أي مرادف في القسم ككلمة كاملة
                    dept_has_keyword = any(has_word(syn, doc_dept) for syn in synonyms)
                    if dept_has_keyword:
                        matched = True
                        break
            
            if matched:
                break
        
        if matched:
            filtered.append(doctor)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_filtered = []
    for doc in filtered:
        if doc['name'] not in seen:
            seen.add(doc['name'])
            unique_filtered.append(doc)
    
    logger.info(f"Found {len(unique_filtered)} doctors in {hospital_name} / {department_name}")
    return unique_filtered


def search_doctors(query: str, hospital_name: str = "", department_name: str = "") -> List[Dict]:
    """
    بحث متقدم عن الأطباء
    """
    _load_data()
    
    query_lower = query.lower().strip()
    
    # تحديد مجموعة البحث
    if hospital_name and department_name:
        doctors = get_doctors_by_hospital_and_department(hospital_name, department_name)
    elif hospital_name:
        doctors = get_doctors_by_hospital(hospital_name)
    else:
        doctors = _DOCTORS_DATA.get('doctors', []) if _DOCTORS_DATA else []
    
    # فلترة بالاسم
    if not query_lower:
        return doctors
    
    results = []
    for doctor in doctors:
        search_text = doctor.get('search_text', doctor.get('name', '').lower())
        if query_lower in search_text or query_lower in doctor.get('name', '').lower():
            results.append(doctor)
    
    return results


def get_statistics() -> Dict:
    """الحصول على إحصائيات قاعدة البيانات"""
    data = _load_data()
    if not data:
        return {"hospitals": 0, "doctors": 0, "departments": 0}
    
    return data.get('statistics', {
        "total_hospitals": len(data.get('hospitals', [])),
        "total_doctors": len(data.get('doctors', [])),
    })


# دالة للتوافق مع الكود القديم
def get_doctors_for_selection(hospital_name: str, department_name: str) -> List[Dict]:
    """
    دالة متوافقة مع الكود القديم
    تُرجع قائمة الأطباء بتنسيق مناسب للعرض
    """
    if department_name:
        doctors = get_doctors_by_hospital_and_department(hospital_name, department_name)
    else:
        doctors = get_doctors_by_hospital(hospital_name)
    
    # تنسيق للعرض
    result = []
    for doc in doctors:
        result.append({
            'name': doc['name'],
            'hospital': doc['hospital_name'],
            'department': doc.get('department', '')
        })
    
    return sorted(result, key=lambda x: x['name'])


def add_doctor(doctor_name: str, hospital_name: str, department_name: str) -> bool:
    """
    إضافة طبيب جديد لقاعدة البيانات
    Add new doctor to database
    """
    global _DOCTORS_DATA, _DOCTORS_BY_HOSPITAL, _DOCTORS_BY_HOSPITAL_DEPT
    
    _load_data()
    
    if not _DOCTORS_DATA:
        logger.error("Cannot add doctor - database not loaded")
        return False
    
    # Check if doctor already exists
    doctor_name_lower = doctor_name.lower().strip()
    for doc in _DOCTORS_DATA.get('doctors', []):
        if doc.get('name_normalized') == doctor_name_lower:
            if doc.get('hospital_name', '').lower() == hospital_name.lower():
                logger.info(f"Doctor already exists: {doctor_name}")
                return True  # Already exists
    
    # Find hospital
    hospital = get_hospital_by_name(hospital_name)
    hospital_id = hospital['id'] if hospital else 0
    
    # Create new doctor record
    new_id = max((d.get('id', 0) for d in _DOCTORS_DATA.get('doctors', [])), default=0) + 1
    
    new_doctor = {
        "id": new_id,
        "name": doctor_name,
        "name_normalized": doctor_name_lower,
        "hospital_id": hospital_id,
        "hospital_name": hospital_name,
        "department": department_name,
        "search_text": f"{doctor_name} {hospital_name} {department_name}".lower(),
        "added_manually": True
    }
    
    # Add to memory
    _DOCTORS_DATA['doctors'].append(new_doctor)
    
    # Update indexes
    if hospital_id not in _DOCTORS_BY_HOSPITAL:
        _DOCTORS_BY_HOSPITAL[hospital_id] = []
    _DOCTORS_BY_HOSPITAL[hospital_id].append(new_doctor)
    
    dept_lower = department_name.lower().strip()
    key = (hospital_id, dept_lower)
    if key not in _DOCTORS_BY_HOSPITAL_DEPT:
        _DOCTORS_BY_HOSPITAL_DEPT[key] = []
    _DOCTORS_BY_HOSPITAL_DEPT[key].append(new_doctor)
    
    # Update statistics
    _DOCTORS_DATA['statistics']['total_doctors'] = len(_DOCTORS_DATA['doctors'])
    
    # Save to file
    try:
        data_path = _get_data_path()
        if data_path:
            with open(data_path, 'w', encoding='utf-8') as f:
                json.dump(_DOCTORS_DATA, f, ensure_ascii=False, indent=2)
            logger.info(f"Added new doctor: {doctor_name} at {hospital_name}/{department_name}")
            return True
    except Exception as e:
        logger.error(f"Failed to save new doctor: {e}")
        return False
    
    return False


def reload_database():
    """
    إعادة تحميل قاعدة البيانات
    Reload database from file
    """
    global _DOCTORS_DATA, _HOSPITALS_INDEX, _DOCTORS_BY_HOSPITAL, _DOCTORS_BY_HOSPITAL_DEPT
    
    _DOCTORS_DATA = None
    _HOSPITALS_INDEX = {}
    _DOCTORS_BY_HOSPITAL = {}
    _DOCTORS_BY_HOSPITAL_DEPT = {}
    
    _load_data()
    logger.info("Database reloaded")


def load_unified_database() -> Dict:
    """
    تحميل قاعدة البيانات الموحدة
    Load unified database (alias for _load_data)
    """
    return _load_data()


def add_doctor_to_database(doctor_name: str, hospital_name: str = "", department_name: str = "") -> bool:
    """
    Alias for add_doctor for compatibility
    """
    return add_doctor(doctor_name, hospital_name, department_name)

