# ================================================
# db/persistent_storage.py
# 🔹 استعادة قاعدة البيانات من Google Cloud Storage عند البدء
# ================================================

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ================================================
# Database Path
# ================================================

DATABASE_PATH = os.getenv("DATABASE_PATH", "db/medical_reports.db")

# ================================================
# Restore Database from GCS
# ================================================

def restore_database_on_startup() -> bool:
    """
    استعادة قاعدة البيانات من Google Cloud Storage عند بدء البوت
    
    Returns:
        True إذا تمت الاستعادة بنجاح، False إذا لم تكن هناك نسخة احتياطية
    """
    try:
        # التحقق من وجود قاعدة بيانات محلية
        db_exists = os.path.exists(DATABASE_PATH) and os.path.getsize(DATABASE_PATH) > 0
        
        # إذا كانت قاعدة البيانات موجودة وليست فارغة، لا نحتاج للاستعادة
        if db_exists:
            db_size = os.path.getsize(DATABASE_PATH) / 1024
            logger.info(f"✅ Database already exists locally: {db_size:.2f} KB")
            logger.info("   Skipping GCS restore (local database found)")
            return False
        
        # محاولة الاستعادة من GCS
        logger.info("🔄 Attempting to restore database from GCS...")
        
        try:
            from services.sqlite_backup import get_backup_service
            
            backup_service = get_backup_service()
            
            # التحقق من وجود bucket
            if not backup_service.bucket:
                logger.warning("⚠️ GCS bucket not available - skipping restore")
                return False
            
            # محاولة استعادة النسخة الدائمة
            persistent_blob_name = "persistent/medical_reports.db"
            blob = backup_service.bucket.blob(persistent_blob_name)
            
            if blob.exists():
                logger.info(f"📥 Found persistent database in GCS: {persistent_blob_name}")
                
                # إنشاء مجلد قاعدة البيانات إذا لم يكن موجوداً
                db_dir = os.path.dirname(DATABASE_PATH)
                if db_dir:
                    os.makedirs(db_dir, exist_ok=True)
                
                # تحميل قاعدة البيانات
                blob.download_to_filename(DATABASE_PATH)
                
                if os.path.exists(DATABASE_PATH):
                    db_size = os.path.getsize(DATABASE_PATH) / 1024
                    logger.info(f"✅ Database restored from GCS: {db_size:.2f} KB")
                    logger.info(f"   📁 Source: gs://{backup_service.bucket.name}/{persistent_blob_name}")
                    return True
                else:
                    logger.error("❌ Database file not created after download")
                    return False
            else:
                logger.info("ℹ️ No persistent database found in GCS - starting fresh")
                return False
                
        except ImportError as import_error:
            logger.warning(f"⚠️ Could not import backup service: {import_error}")
            logger.info("   Starting with fresh database")
            return False
        except Exception as gcs_error:
            logger.warning(f"⚠️ GCS restore failed: {gcs_error}")
            logger.info("   Starting with fresh database")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error in restore_database_on_startup: {e}")
        logger.info("   Starting with fresh database")
        return False


def restore_from_latest_backup() -> bool:
    """
    استعادة قاعدة البيانات من آخر نسخة احتياطية في GCS
    
    Returns:
        True إذا تمت الاستعادة بنجاح
    """
    try:
        logger.info("🔄 Attempting to restore from latest backup in GCS...")
        
        from services.sqlite_backup import get_backup_service
        
        backup_service = get_backup_service()
        
        if not backup_service.bucket:
            logger.error("❌ GCS bucket not available")
            return False
        
        # محاولة استعادة النسخة الدائمة أولاً
        persistent_blob_name = "persistent/medical_reports.db"
        blob = backup_service.bucket.blob(persistent_blob_name)
        
        if blob.exists():
            # إنشاء نسخة احتياطية من قاعدة البيانات الحالية
            if os.path.exists(DATABASE_PATH):
                backup_current = f"{DATABASE_PATH}.before_restore"
                import shutil
                shutil.copy2(DATABASE_PATH, backup_current)
                logger.info(f"   💾 Current database backed up to: {backup_current}")
            
            # تحميل قاعدة البيانات
            db_dir = os.path.dirname(DATABASE_PATH)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            
            blob.download_to_filename(DATABASE_PATH)
            
            if os.path.exists(DATABASE_PATH):
                db_size = os.path.getsize(DATABASE_PATH) / 1024
                logger.info(f"✅ Database restored from latest backup: {db_size:.2f} KB")
                return True
        
        logger.warning("⚠️ No backup found in GCS")
        return False
        
    except Exception as e:
        logger.error(f"❌ Error restoring from latest backup: {e}")
        return False




