# ================================================
# db/online_hosting_config.py
# 🔹 إعدادات قاعدة البيانات للاستضافة الإلكترونية
# ================================================

import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# ================================================
# إعدادات قاعدة البيانات للاستضافة الإلكترونية
# ================================================

class OnlineHostingConfig:
    """
    إعدادات قاعدة البيانات المخصصة للاستضافة الإلكترونية
    
    يدعم:
    - Google Cloud Run
    - Google App Engine
    - أي منصة استضافة أخرى
    """
    
    # ================================================
    # إعدادات المسار
    # ================================================
    
    # مسار قاعدة البيانات داخل الـ Container
    # للاستضافة الإلكترونية: استخدم مسار مطلق داخل /app
    DATABASE_PATH = os.getenv(
        "DATABASE_PATH", 
        "/app/db/medical_reports.db"  # مسار افتراضي للاستضافة
    )
    
    # مسار النسخ الاحتياطية المحلية (داخل Container)
    BACKUP_DIR = os.getenv("BACKUP_DIR", "/app/db/backups")
    
    # ================================================
    # إعدادات Google Cloud Storage (للنسخ الاحتياطية)
    # ================================================
    
    # معرف المشروع في Google Cloud
    GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "lunar-standard-477302-a6")
    
    # اسم الـ Bucket في Cloud Storage
    GCS_BUCKET_NAME = os.getenv(
        "GCS_BUCKET_NAME", 
        f"{GCP_PROJECT_ID}-sqlite-backups"
    )
    
    # مسار قاعدة البيانات في Cloud Storage (النسخة المستمرة)
    GCS_PERSISTENT_PATH = os.getenv(
        "GCS_PERSISTENT_PATH",
        "persistent/medical_reports.db"
    )
    
    # مسار النسخ الاحتياطية في Cloud Storage
    GCS_BACKUP_PATH = os.getenv(
        "GCS_BACKUP_PATH",
        "backups"
    )
    
    # المنطقة الجغرافية للـ Bucket
    GCS_LOCATION = os.getenv("GCS_LOCATION", "asia-south1")
    
    # ================================================
    # إعدادات النسخ الاحتياطي التلقائي
    # ================================================
    
    # تفعيل النسخ الاحتياطي التلقائي (كل N دقيقة)
    AUTO_BACKUP_ENABLED = os.getenv("AUTO_BACKUP_ENABLED", "true").lower() == "true"
    
    # الفترة الزمنية للنسخ الاحتياطي (بالدقائق)
    AUTO_BACKUP_INTERVAL = int(os.getenv("AUTO_BACKUP_INTERVAL", "10"))
    
    # عدد النسخ الاحتياطية المحفوظة (في Cloud Storage)
    MAX_BACKUP_COPIES = int(os.getenv("MAX_BACKUP_COPIES", "30"))
    
    # ================================================
    # إعدادات SQLite للاستضافة
    # ================================================
    
    # إعدادات الاتصال بقاعدة البيانات
    SQLITE_TIMEOUT = int(os.getenv("SQLITE_TIMEOUT", "30"))  # ثواني
    SQLITE_POOL_SIZE = int(os.getenv("SQLITE_POOL_SIZE", "20"))
    SQLITE_MAX_OVERFLOW = int(os.getenv("SQLITE_MAX_OVERFLOW", "10"))
    SQLITE_POOL_RECYCLE = int(os.getenv("SQLITE_POOL_RECYCLE", "3600"))  # ثانية
    
    # تفعيل WAL Mode (للأداء الأفضل في الاستضافة)
    ENABLE_WAL_MODE = os.getenv("ENABLE_WAL_MODE", "true").lower() == "true"
    
    # إعدادات PRAGMA لتحسين الأداء
    SQLITE_CACHE_SIZE = int(os.getenv("SQLITE_CACHE_SIZE", "-64000"))  # 64MB
    SQLITE_SYNCHRONOUS = os.getenv("SQLITE_SYNCHRONOUS", "NORMAL")
    SQLITE_TEMP_STORE = os.getenv("SQLITE_TEMP_STORE", "MEMORY")
    
    # ================================================
    # إعدادات الاستعادة التلقائية
    # ================================================
    
    # تحميل قاعدة البيانات من Cloud Storage عند البدء
    AUTO_RESTORE_ON_STARTUP = os.getenv(
        "AUTO_RESTORE_ON_STARTUP", 
        "true"
    ).lower() == "true"
    
    # حفظ قاعدة البيانات في Cloud Storage عند الإغلاق
    AUTO_SAVE_ON_SHUTDOWN = os.getenv(
        "AUTO_SAVE_ON_SHUTDOWN",
        "true"
    ).lower() == "true"
    
    # ================================================
    # إعدادات الأمان
    # ================================================
    
    # تشفير قاعدة البيانات (إذا كان مطلوباً)
    ENCRYPT_DATABASE = os.getenv("ENCRYPT_DATABASE", "false").lower() == "true"
    
    # ================================================
    # إعدادات المراقبة والصحة
    # ================================================
    
    # تفعيل فحص صحة قاعدة البيانات
    HEALTH_CHECK_ENABLED = os.getenv("HEALTH_CHECK_ENABLED", "true").lower() == "true"
    
    # فترة فحص الصحة (بالثواني)
    HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "60"))
    
    # ================================================
    # دوال مساعدة
    # ================================================
    
    @classmethod
    def get_database_url(cls) -> str:
        """الحصول على رابط قاعدة البيانات"""
        return f"sqlite:///{cls.DATABASE_PATH}"
    
    @classmethod
    def get_config_dict(cls) -> Dict[str, Any]:
        """الحصول على جميع الإعدادات كقاموس"""
        return {
            "database_path": cls.DATABASE_PATH,
            "backup_dir": cls.BACKUP_DIR,
            "gcp_project_id": cls.GCP_PROJECT_ID,
            "gcs_bucket_name": cls.GCS_BUCKET_NAME,
            "gcs_persistent_path": cls.GCS_PERSISTENT_PATH,
            "gcs_backup_path": cls.GCS_BACKUP_PATH,
            "gcs_location": cls.GCS_LOCATION,
            "auto_backup_enabled": cls.AUTO_BACKUP_ENABLED,
            "auto_backup_interval": cls.AUTO_BACKUP_INTERVAL,
            "max_backup_copies": cls.MAX_BACKUP_COPIES,
            "sqlite_timeout": cls.SQLITE_TIMEOUT,
            "sqlite_pool_size": cls.SQLITE_POOL_SIZE,
            "sqlite_max_overflow": cls.SQLITE_MAX_OVERFLOW,
            "sqlite_pool_recycle": cls.SQLITE_POOL_RECYCLE,
            "enable_wal_mode": cls.ENABLE_WAL_MODE,
            "sqlite_cache_size": cls.SQLITE_CACHE_SIZE,
            "sqlite_synchronous": cls.SQLITE_SYNCHRONOUS,
            "sqlite_temp_store": cls.SQLITE_TEMP_STORE,
            "auto_restore_on_startup": cls.AUTO_RESTORE_ON_STARTUP,
            "auto_save_on_shutdown": cls.AUTO_SAVE_ON_SHUTDOWN,
            "encrypt_database": cls.ENCRYPT_DATABASE,
            "health_check_enabled": cls.HEALTH_CHECK_ENABLED,
            "health_check_interval": cls.HEALTH_CHECK_INTERVAL,
        }
    
    @classmethod
    def print_config(cls):
        """طباعة جميع الإعدادات (للتشخيص)"""
        logger.info("=" * 60)
        logger.info("🔧 إعدادات قاعدة البيانات للاستضافة الإلكترونية")
        logger.info("=" * 60)
        
        config = cls.get_config_dict()
        for key, value in config.items():
            logger.info(f"  {key}: {value}")
        
        logger.info("=" * 60)
    
    @classmethod
    def validate_config(cls) -> bool:
        """التحقق من صحة الإعدادات"""
        errors = []
        
        # التحقق من المسارات
        if not cls.DATABASE_PATH:
            errors.append("DATABASE_PATH غير محدد")
        
        # التحقق من إعدادات Cloud Storage
        if cls.AUTO_RESTORE_ON_STARTUP or cls.AUTO_SAVE_ON_SHUTDOWN:
            if not cls.GCP_PROJECT_ID:
                errors.append("GCP_PROJECT_ID مطلوب للنسخ الاحتياطي")
            if not cls.GCS_BUCKET_NAME:
                errors.append("GCS_BUCKET_NAME مطلوب للنسخ الاحتياطي")
        
        # التحقق من الفترات الزمنية
        if cls.AUTO_BACKUP_INTERVAL <= 0:
            errors.append("AUTO_BACKUP_INTERVAL يجب أن يكون أكبر من 0")
        
        if errors:
            for error in errors:
                logger.error(f"❌ {error}")
            return False
        
        logger.info("✅ جميع الإعدادات صحيحة")
        return True


# ================================================
# متغيرات البيئة المطلوبة للاستضافة
# ================================================

REQUIRED_ENV_VARS = [
    "DATABASE_PATH",  # مسار قاعدة البيانات
]

OPTIONAL_ENV_VARS = [
    "GCP_PROJECT_ID",  # معرف مشروع Google Cloud
    "GCS_BUCKET_NAME",  # اسم Bucket في Cloud Storage
    "AUTO_BACKUP_ENABLED",  # تفعيل النسخ الاحتياطي التلقائي
    "AUTO_BACKUP_INTERVAL",  # فترة النسخ الاحتياطي (دقائق)
    "AUTO_RESTORE_ON_STARTUP",  # استعادة تلقائية عند البدء
    "AUTO_SAVE_ON_SHUTDOWN",  # حفظ تلقائي عند الإغلاق
]


# ================================================
# دالة التهيئة
# ================================================

def init_online_hosting_config():
    """
    تهيئة إعدادات الاستضافة الإلكترونية
    يجب استدعاؤها عند بدء التطبيق
    """
    logger.info("🔧 تهيئة إعدادات قاعدة البيانات للاستضافة الإلكترونية...")
    
    # التحقق من صحة الإعدادات
    if not OnlineHostingConfig.validate_config():
        logger.warning("⚠️ بعض الإعدادات غير صحيحة، سيتم استخدام القيم الافتراضية")
    
    # طباعة الإعدادات (للتشخيص)
    OnlineHostingConfig.print_config()
    
    # إنشاء مجلد النسخ الاحتياطية إذا لم يكن موجوداً
    try:
        import os
        os.makedirs(OnlineHostingConfig.BACKUP_DIR, exist_ok=True)
        logger.info(f"✅ مجلد النسخ الاحتياطية جاهز: {OnlineHostingConfig.BACKUP_DIR}")
    except Exception as e:
        logger.warning(f"⚠️ لا يمكن إنشاء مجلد النسخ الاحتياطية: {e}")
    
    logger.info("✅ تم تهيئة إعدادات الاستضافة الإلكترونية بنجاح")


# ================================================
# تصدير
# ================================================

__all__ = [
    'OnlineHostingConfig',
    'REQUIRED_ENV_VARS',
    'OPTIONAL_ENV_VARS',
    'init_online_hosting_config',
]

