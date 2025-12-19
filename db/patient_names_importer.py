# ================================================
# db/patient_names_importer.py
# 🔹 استيراد أسماء المرضى من الملف إلى قاعدة البيانات
# ================================================

import os
import logging
from typing import List
from db.session import get_db
from db.models import Patient

logger = logging.getLogger(__name__)


def import_patient_names_from_file(file_path: str = "data/patient_names.txt") -> int:
    """
    استيراد أسماء المرضى من الملف إلى قاعدة البيانات
    
    Args:
        file_path: مسار الملف
    
    Returns:
        عدد الأسماء المستوردة
    """
    try:
        if not os.path.exists(file_path):
            logger.warning(f"⚠️ الملف غير موجود: {file_path}")
            return 0
        
        # قراءة الأسماء من الملف
        names = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # تجاهل التعليقات والسطور الفارغة
                if line and not line.startswith('#'):
                    names.append(line)
        
        if not names:
            logger.warning("⚠️ لا توجد أسماء في الملف")
            return 0
        
        logger.info(f"📋 تم قراءة {len(names)} اسم من الملف")
        
        # استيراد الأسماء إلى قاعدة البيانات
        imported_count = 0
        with get_db() as db:
            for name in names:
                # التحقق من وجود المريض
                existing = db.query(Patient).filter_by(full_name=name).first()
                if not existing:
                    # إنشاء مريض جديد
                    patient = Patient(full_name=name)
                    db.add(patient)
                    imported_count += 1
            
            db.commit()
        
        logger.info(f"✅ تم استيراد {imported_count} اسم مريض جديد إلى قاعدة البيانات")
        return imported_count
        
    except Exception as e:
        logger.error(f"❌ خطأ في استيراد أسماء المرضى: {e}")
        import traceback
        traceback.print_exc()
        return 0


def ensure_patients_in_database() -> bool:
    """
    التأكد من وجود أسماء المرضى في قاعدة البيانات
    - إذا كانت قاعدة البيانات فارغة، يستورد من الملف
    - إذا كانت موجودة، لا يفعل شيئاً
    
    Returns:
        True إذا كانت هناك أسماء مرضى في قاعدة البيانات
    """
    try:
        with get_db() as db:
            patient_count = db.query(Patient).count()
            
            if patient_count == 0:
                logger.warning("⚠️ قاعدة البيانات فارغة من المرضى، محاولة الاستيراد من الملف...")
                imported = import_patient_names_from_file()
                
                if imported > 0:
                    logger.info(f"✅ تم استيراد {imported} اسم مريض من الملف")
                    return True
                else:
                    logger.warning("⚠️ فشل استيراد أسماء المرضى من الملف")
                    return False
            else:
                logger.info(f"✅ قاعدة البيانات تحتوي على {patient_count} مريض")
                return True
                
    except Exception as e:
        logger.error(f"❌ خطأ في التحقق من قاعدة البيانات: {e}")
        return False


__all__ = [
    'import_patient_names_from_file',
    'ensure_patients_in_database',
]

