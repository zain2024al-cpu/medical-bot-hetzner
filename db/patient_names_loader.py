# ================================================
# db/patient_names_loader.py
# 🔹 تحميل أسماء المرضى من قاعدة البيانات
# ================================================

import os
import logging
from typing import List, Optional
from db.session import get_db
from db.models import Patient

logger = logging.getLogger(__name__)


# ================================================
# تحميل أسماء المرضى من قاعدة البيانات
# ================================================

def load_patient_names_from_database(limit: Optional[int] = None) -> List[str]:
    """
    تحميل أسماء المرضى من قاعدة البيانات
    
    Args:
        limit: الحد الأقصى لعدد الأسماء (None = جميع الأسماء)
    
    Returns:
        قائمة بأسماء المرضى
    """
    try:
        with get_db() as db:
            query = db.query(Patient).filter(Patient.full_name.isnot(None))
            
            if limit:
                query = query.limit(limit)
            
            patients = query.order_by(Patient.created_at.desc()).all()
            
            names = [patient.full_name for patient in patients if patient.full_name]
            
            logger.info(f"✅ تم تحميل {len(names)} اسم مريض من قاعدة البيانات")
            return names
            
    except Exception as e:
        logger.error(f"❌ خطأ في تحميل أسماء المرضى من قاعدة البيانات: {e}")
        return []


def sync_patient_names_to_file(file_path: str = "data/patient_names.txt") -> bool:
    """
    مزامنة أسماء المرضى من قاعدة البيانات إلى الملف
    
    Args:
        file_path: مسار الملف
    
    Returns:
        True إذا نجحت العملية
    """
    try:
        # تحميل الأسماء من قاعدة البيانات
        names = load_patient_names_from_database()
        
        if not names:
            logger.warning("⚠️ لا توجد أسماء مرضى في قاعدة البيانات")
            return False
        
        # إنشاء مجلد الملف إذا لم يكن موجوداً
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # كتابة الأسماء في الملف
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("# قائمة أسماء المرضى - يتم التحديث تلقائياً من قاعدة البيانات\n")
            f.write(f"# آخر تحديث: {len(names)} مريضاً\n")
            f.write("# ملاحظة: لا تحذف هذا الملف\n\n")
            
            for name in sorted(set(names)):  # إزالة التكرار وترتيب
                f.write(f"{name}\n")
        
        logger.info(f"✅ تم مزامنة {len(names)} اسم مريض إلى الملف: {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"❌ خطأ في مزامنة أسماء المرضى إلى الملف: {e}")
        return False


def get_patient_names_from_database_or_file(
    file_path: str = "data/patient_names.txt",
    prefer_database: bool = True
) -> List[str]:
    """
    الحصول على أسماء المرضى من قاعدة البيانات أو الملف
    
    Args:
        file_path: مسار الملف
        prefer_database: إذا كان True، يفضل قاعدة البيانات، وإلا يفضل الملف
    
    Returns:
        قائمة بأسماء المرضى
    """
    names = []
    
    if prefer_database:
        # محاولة التحميل من قاعدة البيانات أولاً
        names = load_patient_names_from_database()
        
        if names:
            logger.info(f"✅ تم تحميل {len(names)} اسم مريض من قاعدة البيانات")
            return names
        
        # إذا فشل، محاولة التحميل من الملف
        logger.warning("⚠️ فشل تحميل أسماء المرضى من قاعدة البيانات، محاولة التحميل من الملف")
    
    # محاولة التحميل من الملف
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # استخراج الأسماء (تجاهل التعليقات)
            names = []
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    names.append(line)
            
            logger.info(f"✅ تم تحميل {len(names)} اسم مريض من الملف: {file_path}")
            return names
        else:
            logger.warning(f"⚠️ الملف غير موجود: {file_path}")
            return []
            
    except Exception as e:
        logger.error(f"❌ خطأ في تحميل أسماء المرضى من الملف: {e}")
        return []


def ensure_patient_names_available() -> bool:
    """
    التأكد من توفر أسماء المرضى (من قاعدة البيانات أو الملف)
    
    Returns:
        True إذا كانت الأسماء متوفرة
    """
    # محاولة التحميل من قاعدة البيانات
    names = load_patient_names_from_database(limit=1)
    
    if names:
        logger.info("✅ أسماء المرضى متوفرة في قاعدة البيانات")
        return True
    
    # محاولة التحميل من الملف
    names = get_patient_names_from_database_or_file(prefer_database=False)
    
    if names:
        logger.info("✅ أسماء المرضى متوفرة في الملف")
        return True
    
    logger.warning("⚠️ لا توجد أسماء مرضى متوفرة (لا في قاعدة البيانات ولا في الملف)")
    return False


# ================================================
# دالة التهيئة (للاستدعاء عند بدء البوت)
# ================================================

def init_patient_names():
    """
    تهيئة أسماء المرضى عند بدء البوت
    - التأكد من وجود أسماء في قاعدة البيانات
    - استيراد من الملف إذا كانت قاعدة البيانات فارغة
    - مزامنة مع الملف (إذا لزم الأمر)
    """
    logger.info("🔧 تهيئة أسماء المرضى...")
    
    # التأكد من وجود أسماء في قاعدة البيانات (يستورد من الملف إذا لزم الأمر)
    try:
        from db.patient_names_importer import ensure_patients_in_database
        if not ensure_patients_in_database():
            logger.warning("⚠️ لا توجد أسماء مرضى في قاعدة البيانات أو الملف")
            return False
    except Exception as e:
        logger.warning(f"⚠️ خطأ في استيراد أسماء المرضى: {e}")
        # محاولة التحقق من قاعدة البيانات فقط
        if not ensure_patient_names_available():
            logger.warning("⚠️ لا توجد أسماء مرضى متوفرة")
            return False
    
    # محاولة المزامنة مع الملف (للتوافق مع الكود القديم)
    try:
        sync_patient_names_to_file()
    except Exception as e:
        logger.warning(f"⚠️ فشل مزامنة أسماء المرضى مع الملف: {e}")
        # لا نوقف العملية - قاعدة البيانات كافية
    
    logger.info("✅ تم تهيئة أسماء المرضى بنجاح")
    return True


# ================================================
# تصدير
# ================================================

__all__ = [
    'load_patient_names_from_database',
    'sync_patient_names_to_file',
    'get_patient_names_from_database_or_file',
    'ensure_patient_names_available',
    'init_patient_names',
]

