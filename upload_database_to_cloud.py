# ================================================
# رفع قاعدة البيانات المحلية إلى Cloud Storage
# ================================================

import os
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    logger.info("="*60)
    logger.info("📤 رفع قاعدة البيانات المحلية إلى Cloud Storage")
    logger.info("="*60)
    
    # 1. التحقق من وجود قاعدة البيانات المحلية
    DATABASE_PATH = os.getenv("DATABASE_PATH", "db/medical_reports.db")
    
    if not os.path.exists(DATABASE_PATH):
        logger.error(f"❌ قاعدة البيانات غير موجودة: {DATABASE_PATH}")
        logger.error("   تأكد من وجود قاعدة البيانات المحلية")
        return False
    
    # معلومات قاعدة البيانات
    db_size = os.path.getsize(DATABASE_PATH) / (1024 * 1024)  # MB
    logger.info(f"✅ قاعدة البيانات موجودة: {DATABASE_PATH}")
    logger.info(f"   الحجم: {db_size:.2f} MB")
    
    # 2. محاولة الرفع إلى Cloud Storage
    try:
        from db.persistent_storage import get_storage_manager
        
        logger.info("\n🔄 جاري رفع قاعدة البيانات إلى Cloud Storage...")
        
        manager = get_storage_manager()
        
        if not manager.bucket:
            logger.error("❌ Google Cloud Storage غير متاح")
            logger.error("   يجب إضافة GOOGLE_APPLICATION_CREDENTIALS")
            logger.info("\n💡 الحل البديل:")
            logger.info("   1. استخدم services/sqlite_backup.py")
            logger.info("   2. أو رفع قاعدة البيانات يدوياً")
            return False
        
        # رفع قاعدة البيانات
        success = manager.upload_database()
        
        if success:
            logger.info("\n✅ تم رفع قاعدة البيانات بنجاح!")
            logger.info("   📁 الموقع: persistent/medical_reports.db")
            logger.info("\n💡 الخطوات التالية:")
            logger.info("   1. اذهب إلى Railway")
            logger.info("   2. اضغط 'Deploy' لإعادة النشر")
            logger.info("   3. قاعدة البيانات ستُستعاد تلقائياً")
            return True
        else:
            logger.error("\n❌ فشل رفع قاعدة البيانات")
            return False
            
    except ImportError:
        logger.warning("⚠️ Google Cloud Storage غير متاح محلياً")
        logger.info("\n💡 الحل البديل:")
        logger.info("   1. استخدم services/sqlite_backup.py")
        logger.info("   2. أو رفع قاعدة البيانات يدوياً إلى Railway")
        return False
    except Exception as e:
        logger.error(f"❌ خطأ في رفع قاعدة البيانات: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        exit(1)

