# ================================================
# db/doctors_importer.py
# 🔹 استيراد الأطباء من الملفات إلى قاعدة البيانات
# ================================================

import os
import json
import logging
from typing import List, Dict
from db.session import get_db
from db.models import Doctor, Hospital, Department

logger = logging.getLogger(__name__)


def import_doctors_from_organized_json(file_path: str = "data/doctors_organized.json") -> int:
    """
    استيراد الأطباء من الملف المنظم إلى قاعدة البيانات
    
    Args:
        file_path: مسار الملف JSON المنظم
    
    Returns:
        عدد الأطباء المستوردين
    """
    try:
        if not os.path.exists(file_path):
            logger.warning(f"⚠️ الملف غير موجود: {file_path}")
            return 0
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        hospitals_data = data.get('hospitals', {})
        
        if not hospitals_data:
            logger.warning("⚠️ لا توجد بيانات مستشفيات في الملف")
            return 0
        
        imported_count = 0
        
        with get_db() as db:
            for hospital_name, departments in hospitals_data.items():
                # إنشاء أو الحصول على المستشفى
                hospital = db.query(Hospital).filter_by(name=hospital_name).first()
                if not hospital:
                    hospital = Hospital(name=hospital_name)
                    db.add(hospital)
                    db.flush()  # للحصول على ID
                
                for dept_key, dept_data in departments.items():
                    dept_ar = dept_data.get('department_ar', '')
                    dept_en = dept_data.get('department_en', '')
                    doctors = dept_data.get('doctors', [])
                    
                    # إنشاء أو الحصول على القسم
                    department = db.query(Department).filter_by(
                        name=dept_ar,
                        hospital_id=hospital.id
                    ).first()
                    
                    if not department:
                        department = Department(
                            name=dept_ar,
                            hospital_id=hospital.id,
                            hospital_name=hospital_name
                        )
                        db.add(department)
                        db.flush()  # للحصول على ID
                    
                    # إضافة الأطباء
                    for doctor_name in doctors:
                        if doctor_name and doctor_name.strip():
                            # التحقق من وجود الطبيب
                            existing = db.query(Doctor).filter_by(
                                name=doctor_name.strip(),
                                hospital_id=hospital.id,
                                department_id=department.id
                            ).first()
                            
                            if not existing:
                                doctor = Doctor(
                                    name=doctor_name.strip(),
                                    full_name=doctor_name.strip(),
                                    specialty=dept_ar,
                                    department_id=department.id,
                                    hospital_id=hospital.id
                                )
                                db.add(doctor)
                                imported_count += 1
            
            db.commit()
        
        logger.info(f"✅ تم استيراد {imported_count} طبيب إلى قاعدة البيانات")
        return imported_count
        
    except Exception as e:
        logger.error(f"❌ خطأ في استيراد الأطباء: {e}")
        import traceback
        traceback.print_exc()
        return 0


def import_doctors_from_database_json(file_path: str = "data/doctors_database.json") -> int:
    """
    استيراد الأطباء من الملف القديم إلى قاعدة البيانات
    
    Args:
        file_path: مسار الملف JSON
    
    Returns:
        عدد الأطباء المستوردين
    """
    try:
        if not os.path.exists(file_path):
            logger.warning(f"⚠️ الملف غير موجود: {file_path}")
            return 0
        
        with open(file_path, 'r', encoding='utf-8') as f:
            doctors_data = json.load(f)
        
        if not doctors_data:
            logger.warning("⚠️ لا توجد بيانات أطباء في الملف")
            return 0
        
        imported_count = 0
        
        with get_db() as db:
            for doctor_info in doctors_data:
                name = doctor_info.get('name', '').strip()
                hospital_name = doctor_info.get('hospital', '').strip()
                dept_ar = doctor_info.get('department_ar', '').strip()
                dept_en = doctor_info.get('department_en', '').strip()
                
                if not name:
                    continue
                
                # إنشاء أو الحصول على المستشفى
                hospital = db.query(Hospital).filter_by(name=hospital_name).first()
                if not hospital and hospital_name:
                    hospital = Hospital(name=hospital_name)
                    db.add(hospital)
                    db.flush()
                
                # إنشاء أو الحصول على القسم
                department = None
                if hospital and dept_ar:
                    department = db.query(Department).filter_by(
                        name=dept_ar,
                        hospital_id=hospital.id
                    ).first()
                    
                    if not department:
                        department = Department(
                            name=dept_ar,
                            hospital_id=hospital.id,
                            hospital_name=hospital_name
                        )
                        db.add(department)
                        db.flush()
                
                # التحقق من وجود الطبيب
                existing = db.query(Doctor).filter_by(name=name).first()
                if not existing:
                    doctor = Doctor(
                        name=name,
                        full_name=name,
                        specialty=dept_ar or dept_en,
                        department_id=department.id if department else None,
                        hospital_id=hospital.id if hospital else None
                    )
                    db.add(doctor)
                    imported_count += 1
            
            db.commit()
        
        logger.info(f"✅ تم استيراد {imported_count} طبيب من الملف القديم")
        return imported_count
        
    except Exception as e:
        logger.error(f"❌ خطأ في استيراد الأطباء من الملف القديم: {e}")
        import traceback
        traceback.print_exc()
        return 0


def ensure_doctors_in_database() -> bool:
    """
    التأكد من وجود الأطباء في قاعدة البيانات
    - يحاول استيراد من الملف المنظم أولاً
    - إذا فشل، يحاول من الملف القديم
    
    Returns:
        True إذا كانت هناك أطباء في قاعدة البيانات
    """
    try:
        with get_db() as db:
            doctor_count = db.query(Doctor).count()
            
            if doctor_count == 0:
                logger.warning("⚠️ قاعدة البيانات فارغة من الأطباء، محاولة الاستيراد...")
                
                # محاولة الاستيراد من الملف المنظم أولاً
                imported = import_doctors_from_organized_json()
                
                if imported == 0:
                    # إذا فشل، جرب الملف القديم
                    logger.info("محاولة الاستيراد من الملف القديم...")
                    imported = import_doctors_from_database_json()
                
                if imported > 0:
                    logger.info(f"✅ تم استيراد {imported} طبيب إلى قاعدة البيانات")
                    return True
                else:
                    logger.warning("⚠️ فشل استيراد الأطباء من الملفات")
                    return False
            else:
                logger.info(f"✅ قاعدة البيانات تحتوي على {doctor_count} طبيب")
                return True
                
    except Exception as e:
        logger.error(f"❌ خطأ في التحقق من قاعدة البيانات: {e}")
        return False


__all__ = [
    'import_doctors_from_organized_json',
    'import_doctors_from_database_json',
    'ensure_doctors_in_database',
]






