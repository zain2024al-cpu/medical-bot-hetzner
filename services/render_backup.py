# ================================================
# services/render_backup.py
# 🔹 نظام النسخ الاحتياطي لـ Render
# ================================================

import os
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ================================================
# إعدادات النسخ الاحتياطي
# ================================================

# استخدام نفس المسار من db/session.py أو المسار الافتراضي لـ Render
try:
    from db.session import DATABASE_PATH as DB_PATH
    # في Render، استخدم /app/db/medical_reports.db، محلياً استخدم db/medical_reports.db
    if os.path.exists("/app/db/medical_reports.db"):
        DATABASE_PATH = "/app/db/medical_reports.db"
        BACKUP_DIR = "/app/db/backups"
    else:
        DATABASE_PATH = DB_PATH
        BACKUP_DIR = os.path.join(os.path.dirname(DATABASE_PATH), "backups")
except:
    # Fallback
    DATABASE_PATH = os.getenv("DATABASE_PATH", "/app/db/medical_reports.db")
    BACKUP_DIR = os.getenv("BACKUP_DIR", "/app/db/backups")

MAX_LOCAL_BACKUPS = int(os.getenv("MAX_LOCAL_BACKUPS", "10"))  # عدد النسخ المحلية


# ================================================
# نظام النسخ الاحتياطي المحلي
# ================================================

def create_local_backup() -> Optional[str]:
    """
    إنشاء نسخة احتياطية محلية لقاعدة البيانات
    
    Returns:
        مسار النسخة الاحتياطية أو None إذا فشل
    """
    try:
        if not os.path.exists(DATABASE_PATH):
            logger.warning(f"⚠️ قاعدة البيانات غير موجودة: {DATABASE_PATH}")
            return None
        
        # إنشاء مجلد النسخ الاحتياطية
        os.makedirs(BACKUP_DIR, exist_ok=True)
        
        # إنشاء اسم النسخة الاحتياطية
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{timestamp}.db"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)
        
        # نسخ قاعدة البيانات
        shutil.copy2(DATABASE_PATH, backup_path)
        
        db_size = os.path.getsize(DATABASE_PATH) / 1024
        backup_size = os.path.getsize(backup_path) / 1024
        
        logger.info(f"✅ تم إنشاء نسخة احتياطية محلية")
        logger.info(f"   📁 المسار: {backup_path}")
        logger.info(f"   💾 الحجم: {backup_size:.2f} KB (الأصل: {db_size:.2f} KB)")
        
        # تنظيف النسخ القديمة
        cleanup_old_backups()
        
        return backup_path
        
    except Exception as e:
        logger.error(f"❌ خطأ في إنشاء النسخة الاحتياطية: {e}")
        import traceback
        traceback.print_exc()
        return None


def cleanup_old_backups():
    """حذف النسخ الاحتياطية القديمة (الاحتفاظ بآخر N نسخة)"""
    try:
        if not os.path.exists(BACKUP_DIR):
            return
        
        # الحصول على جميع النسخ الاحتياطية
        backups = []
        for file in os.listdir(BACKUP_DIR):
            if file.startswith("backup_") and file.endswith(".db"):
                file_path = os.path.join(BACKUP_DIR, file)
                mtime = os.path.getmtime(file_path)
                backups.append((mtime, file_path))
        
        # ترتيب حسب تاريخ التعديل (الأحدث أولاً)
        backups.sort(reverse=True)
        
        # حذف النسخ الزائدة
        if len(backups) > MAX_LOCAL_BACKUPS:
            for mtime, file_path in backups[MAX_LOCAL_BACKUPS:]:
                try:
                    os.remove(file_path)
                    logger.info(f"🗑️ تم حذف نسخة احتياطية قديمة: {os.path.basename(file_path)}")
                except Exception as e:
                    logger.warning(f"⚠️ فشل حذف نسخة احتياطية: {e}")
        
    except Exception as e:
        logger.error(f"❌ خطأ في تنظيف النسخ الاحتياطية: {e}")


def restore_from_local_backup(backup_filename: str) -> bool:
    """
    استعادة قاعدة البيانات من نسخة احتياطية محلية
    
    Args:
        backup_filename: اسم ملف النسخة الاحتياطية
    
    Returns:
        True إذا نجحت العملية
    """
    try:
        backup_path = os.path.join(BACKUP_DIR, backup_filename)
        
        if not os.path.exists(backup_path):
            logger.error(f"❌ النسخة الاحتياطية غير موجودة: {backup_path}")
            return False
        
        # إنشاء نسخة احتياطية من قاعدة البيانات الحالية
        if os.path.exists(DATABASE_PATH):
            current_backup = f"{DATABASE_PATH}.before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(DATABASE_PATH, current_backup)
            logger.info(f"💾 تم حفظ نسخة احتياطية من قاعدة البيانات الحالية: {current_backup}")
        
        # استعادة من النسخة الاحتياطية
        shutil.copy2(backup_path, DATABASE_PATH)
        
        logger.info(f"✅ تم استعادة قاعدة البيانات من: {backup_filename}")
        return True
        
    except Exception as e:
        logger.error(f"❌ خطأ في استعادة قاعدة البيانات: {e}")
        return False


def list_local_backups() -> list:
    """
    قائمة بالنسخ الاحتياطية المحلية
    
    Returns:
        قائمة بمعلومات النسخ الاحتياطية
    """
    backups = []
    
    try:
        if not os.path.exists(BACKUP_DIR):
            return backups
        
        for file in os.listdir(BACKUP_DIR):
            if file.startswith("backup_") and file.endswith(".db"):
                file_path = os.path.join(BACKUP_DIR, file)
                mtime = os.path.getmtime(file_path)
                size = os.path.getsize(file_path) / 1024
                
                backups.append({
                    "filename": file,
                    "path": file_path,
                    "size_kb": size,
                    "modified": datetime.fromtimestamp(mtime)
                })
        
        # ترتيب حسب التاريخ (الأحدث أولاً)
        backups.sort(key=lambda x: x["modified"], reverse=True)
        
    except Exception as e:
        logger.error(f"❌ خطأ في قائمة النسخ الاحتياطية: {e}")
    
    return backups


def get_latest_backup() -> Optional[str]:
    """الحصول على أحدث نسخة احتياطية"""
    backups = list_local_backups()
    if backups:
        return backups[0]["path"]
    return None


# ================================================
# دالة النسخ الاحتياطي التلقائي
# ================================================

def auto_backup_job():
    """مهمة النسخ الاحتياطي التلقائي (تُستدعى من scheduler)"""
    try:
        backup_path = create_local_backup()
        if backup_path:
            logger.info(f"✅ النسخ الاحتياطي التلقائي نجح: {backup_path}")
            return True
        else:
            logger.warning("⚠️ فشل النسخ الاحتياطي التلقائي")
            return False
    except Exception as e:
        logger.error(f"❌ خطأ في النسخ الاحتياطي التلقائي: {e}")
        return False


# ================================================
# تصدير
# ================================================

__all__ = [
    'create_local_backup',
    'restore_from_local_backup',
    'list_local_backups',
    'get_latest_backup',
    'cleanup_old_backups',
    'auto_backup_job',
]

