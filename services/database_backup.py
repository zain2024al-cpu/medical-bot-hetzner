# ================================================
# services/database_backup.py
# نظام النسخ الاحتياطي التلقائي لقاعدة البيانات
# ================================================

import os
import shutil
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# مسارات الملفات
DB_PATH = Path("db/medical_reports.db")
BACKUP_DIR = Path("db/backups")


def ensure_backup_dir():
    """التأكد من وجود مجلد النسخ الاحتياطية"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def create_backup(prefix: str = "auto") -> str:
    """
    إنشاء نسخة احتياطية من قاعدة البيانات
    
    Args:
        prefix: بادئة اسم الملف (auto, manual, daily, etc.)
    
    Returns:
        مسار ملف النسخة الاحتياطية
    """
    ensure_backup_dir()
    
    if not DB_PATH.exists():
        logger.warning(f"⚠️ قاعدة البيانات غير موجودة: {DB_PATH}")
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_{prefix}_{timestamp}.db"
    backup_path = BACKUP_DIR / backup_name
    
    try:
        shutil.copy2(DB_PATH, backup_path)
        logger.info(f"✅ تم إنشاء نسخة احتياطية: {backup_path}")
        return str(backup_path)
    except Exception as e:
        logger.error(f"❌ خطأ في إنشاء النسخة الاحتياطية: {e}")
        return None


def create_daily_backup() -> str:
    """إنشاء نسخة احتياطية يومية (تُستدعى عند بدء البوت)"""
    today = datetime.now().strftime("%Y%m%d")
    
    # التحقق إذا كانت هناك نسخة لهذا اليوم بالفعل
    existing_backups = list(BACKUP_DIR.glob(f"backup_daily_{today}*.db"))
    if existing_backups:
        logger.info(f"ℹ️ النسخة الاحتياطية اليومية موجودة بالفعل: {existing_backups[0]}")
        return str(existing_backups[0])
    
    return create_backup("daily")


def cleanup_old_backups(days_to_keep: int = 30):
    """
    حذف النسخ الاحتياطية القديمة
    
    Args:
        days_to_keep: عدد الأيام للاحتفاظ بالنسخ الاحتياطية
    """
    ensure_backup_dir()
    
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    deleted_count = 0
    
    for backup_file in BACKUP_DIR.glob("backup_auto_*.db"):
        try:
            # استخراج التاريخ من اسم الملف
            file_date_str = backup_file.stem.split("_")[2]  # backup_auto_YYYYMMDD_HHMMSS
            file_date = datetime.strptime(file_date_str, "%Y%m%d")
            
            if file_date < cutoff_date:
                backup_file.unlink()
                deleted_count += 1
                logger.info(f"🗑️ تم حذف نسخة قديمة: {backup_file.name}")
        except Exception as e:
            logger.warning(f"⚠️ خطأ في معالجة {backup_file}: {e}")
    
    if deleted_count > 0:
        logger.info(f"✅ تم حذف {deleted_count} نسخة احتياطية قديمة")


def get_latest_backup() -> str:
    """الحصول على أحدث نسخة احتياطية"""
    ensure_backup_dir()
    
    backups = sorted(BACKUP_DIR.glob("backup_*.db"), key=os.path.getmtime, reverse=True)
    if backups:
        return str(backups[0])
    return None


def restore_from_backup(backup_path: str) -> bool:
    """
    استعادة قاعدة البيانات من نسخة احتياطية
    
    Args:
        backup_path: مسار ملف النسخة الاحتياطية
    
    Returns:
        True إذا نجحت الاستعادة
    """
    backup_file = Path(backup_path)
    
    if not backup_file.exists():
        logger.error(f"❌ ملف النسخة الاحتياطية غير موجود: {backup_path}")
        return False
    
    try:
        # إنشاء نسخة من قاعدة البيانات الحالية قبل الاستعادة
        if DB_PATH.exists():
            create_backup("before_restore")
        
        # استعادة من النسخة الاحتياطية
        shutil.copy2(backup_file, DB_PATH)
        logger.info(f"✅ تم استعادة قاعدة البيانات من: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في استعادة قاعدة البيانات: {e}")
        return False


def list_backups() -> list:
    """عرض قائمة النسخ الاحتياطية المتوفرة"""
    ensure_backup_dir()
    
    backups = []
    for backup_file in sorted(BACKUP_DIR.glob("backup_*.db"), key=os.path.getmtime, reverse=True):
        stat = backup_file.stat()
        backups.append({
            "name": backup_file.name,
            "path": str(backup_file),
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        })
    
    return backups


def backup_before_action(action_name: str = "action") -> str:
    """إنشاء نسخة احتياطية قبل إجراء عملية مهمة"""
    return create_backup(f"before_{action_name}")


# ================================================
# تشغيل عند بدء البوت
# ================================================
def initialize_backup_system():
    """تهيئة نظام النسخ الاحتياطي عند بدء البوت"""
    logger.info("🔄 تهيئة نظام النسخ الاحتياطي...")
    
    # إنشاء مجلد النسخ الاحتياطية
    ensure_backup_dir()
    
    # إنشاء نسخة احتياطية يومية
    daily_backup = create_daily_backup()
    
    # تنظيف النسخ القديمة (أكثر من 30 يوم)
    cleanup_old_backups(days_to_keep=30)
    
    logger.info("✅ تم تهيئة نظام النسخ الاحتياطي بنجاح")
    return daily_backup

