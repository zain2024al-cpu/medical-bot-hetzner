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
                    'created_at': patient.created_at
                }
    except Exception as e:
        logger.error(f"Error getting patient by id: {e}")
    
    return None


def add_patient(name: str) -> Optional[int]:
    """
    إضافة مريض جديد
    Returns patient id or None
    """
    try:
        from db.session import SessionLocal
        from db.models import Patient
        
        with SessionLocal() as session:
            # Check if exists
            existing = session.query(Patient).filter_by(full_name=name).first()
            if existing:
                logger.info(f"Patient already exists: {name}")
                return existing.id
            
            new_patient = Patient(full_name=name)
            session.add(new_patient)
            session.commit()
            
            logger.info(f"Added new patient: {name}")
            return new_patient.id
            
    except Exception as e:
        logger.error(f"Error adding patient: {e}")
        return None


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
    حذف مريض
    """
    try:
        from db.session import SessionLocal
        from db.models import Patient
        
        with SessionLocal() as session:
            patient = session.query(Patient).filter_by(id=patient_id).first()
            if patient:
                name = patient.full_name
                session.delete(patient)
                session.commit()
                logger.info(f"Deleted patient: {name}")
                return True
            else:
                logger.warning(f"Patient with id {patient_id} not found")
                return False
                
    except Exception as e:
        logger.error(f"Error deleting patient: {e}")
        return False


def get_patients_paginated(page: int = 0, per_page: int = 10) -> tuple:
    """
    الحصول على المرضى مع التصفح بالصفحات
    Returns: (patients_list, total_count, total_pages)
    """
    try:
        from db.session import SessionLocal
        from db.models import Patient
        
        with SessionLocal() as session:
            total_count = session.query(Patient).count()
            total_pages = (total_count + per_page - 1) // per_page
            
            patients = session.query(Patient).order_by(
                Patient.created_at.desc()
            ).offset(page * per_page).limit(per_page).all()
            
            result = [{
                'id': p.id,
                'name': p.full_name,
                'created_at': p.created_at
            } for p in patients]
            
            return result, total_count, total_pages
            
    except Exception as e:
        logger.error(f"Error getting paginated patients: {e}")
        return [], 0, 0


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
    عدد المرضى
    """
    try:
        from db.session import SessionLocal
        from db.models import Patient
        
        with SessionLocal() as session:
            return session.query(Patient).count()
    except:
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
    'sync_file_to_database',
    'get_patients_count',
    'get_patients_paginated',
    'load_patient_names',
]

