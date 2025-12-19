# ================================================
# db/example_usage_online_hosting.py
# 🔹 مثال على استخدام إعدادات الاستضافة الإلكترونية
# ================================================

"""
هذا ملف مثال يوضح كيفية استخدام db/online_hosting_config.py
في التطبيق الخاص بك.
"""

from db.online_hosting_config import (
    OnlineHostingConfig,
    init_online_hosting_config
)
import logging

logger = logging.getLogger(__name__)


# ================================================
# مثال 1: تهيئة الإعدادات عند بدء التطبيق
# ================================================

def example_init():
    """مثال على تهيئة الإعدادات"""
    logger.info("تهيئة إعدادات الاستضافة الإلكترونية...")
    init_online_hosting_config()
    logger.info("✅ تم التهيئة بنجاح")


# ================================================
# مثال 2: استخدام الإعدادات في db/session.py
# ================================================

def example_database_session():
    """مثال على استخدام الإعدادات في جلسة قاعدة البيانات"""
    from sqlalchemy import create_engine
    
    # استخدام المسار من الإعدادات
    database_url = OnlineHostingConfig.get_database_url()
    
    # إنشاء محرك قاعدة البيانات مع الإعدادات
    engine = create_engine(
        database_url,
        connect_args={
            "check_same_thread": False,
            "timeout": OnlineHostingConfig.SQLITE_TIMEOUT,
            "isolation_level": None
        },
        pool_pre_ping=True,
        pool_recycle=OnlineHostingConfig.SQLITE_POOL_RECYCLE,
        pool_size=OnlineHostingConfig.SQLITE_POOL_SIZE,
        max_overflow=OnlineHostingConfig.SQLITE_MAX_OVERFLOW
    )
    
    logger.info(f"✅ تم إنشاء محرك قاعدة البيانات: {database_url}")
    return engine


# ================================================
# مثال 3: استخدام الإعدادات مع النسخ الاحتياطي
# ================================================

def example_backup_config():
    """مثال على استخدام إعدادات النسخ الاحتياطي"""
    if OnlineHostingConfig.AUTO_BACKUP_ENABLED:
        logger.info(f"✅ النسخ الاحتياطي التلقائي مفعّل")
        logger.info(f"   الفترة: كل {OnlineHostingConfig.AUTO_BACKUP_INTERVAL} دقيقة")
        logger.info(f"   عدد النسخ المحفوظة: {OnlineHostingConfig.MAX_BACKUP_COPIES}")
    else:
        logger.info("⚠️ النسخ الاحتياطي التلقائي معطّل")


# ================================================
# مثال 4: استخدام إعدادات Cloud Storage
# ================================================

def example_cloud_storage_config():
    """مثال على استخدام إعدادات Cloud Storage"""
    logger.info("إعدادات Cloud Storage:")
    logger.info(f"   المشروع: {OnlineHostingConfig.GCP_PROJECT_ID}")
    logger.info(f"   Bucket: {OnlineHostingConfig.GCS_BUCKET_NAME}")
    logger.info(f"   المسار المستمر: {OnlineHostingConfig.GCS_PERSISTENT_PATH}")
    logger.info(f"   مسار النسخ الاحتياطية: {OnlineHostingConfig.GCS_BACKUP_PATH}")


# ================================================
# مثال 5: الحصول على جميع الإعدادات
# ================================================

def example_get_all_config():
    """مثال على الحصول على جميع الإعدادات"""
    config = OnlineHostingConfig.get_config_dict()
    
    logger.info("جميع الإعدادات:")
    for key, value in config.items():
        logger.info(f"   {key}: {value}")


# ================================================
# مثال 6: التحقق من صحة الإعدادات
# ================================================

def example_validate_config():
    """مثال على التحقق من صحة الإعدادات"""
    is_valid = OnlineHostingConfig.validate_config()
    
    if is_valid:
        logger.info("✅ جميع الإعدادات صحيحة")
    else:
        logger.error("❌ هناك أخطاء في الإعدادات")


# ================================================
# مثال 7: استخدام في app.py
# ================================================

def example_integration_with_app():
    """
    مثال على التكامل مع app.py
    
    أضف هذا الكود في بداية دالة main() في app.py:
    """
    code_example = """
    # في app.py
    from db.online_hosting_config import init_online_hosting_config
    
    async def main():
        # تهيئة إعدادات الاستضافة الإلكترونية
        init_online_hosting_config()
        
        # باقي الكود...
        logger.info("Starting Medical Reports Bot...")
        # ...
    """
    logger.info("مثال التكامل مع app.py:")
    logger.info(code_example)


# ================================================
# مثال 8: استخدام في db/session.py
# ================================================

def example_integration_with_session():
    """
    مثال على التكامل مع db/session.py
    
    استبدل الإعدادات الثابتة في db/session.py بهذا:
    """
    code_example = """
    # في db/session.py
    from db.online_hosting_config import OnlineHostingConfig
    
    # استخدام المسار من الإعدادات
    DATABASE_PATH = OnlineHostingConfig.DATABASE_PATH
    DATABASE_URL = OnlineHostingConfig.get_database_url()
    
    # استخدام إعدادات SQLite
    engine = create_engine(
        DATABASE_URL,
        connect_args={
            "check_same_thread": False,
            "timeout": OnlineHostingConfig.SQLITE_TIMEOUT,
            "isolation_level": None
        },
        pool_pre_ping=True,
        pool_recycle=OnlineHostingConfig.SQLITE_POOL_RECYCLE,
        pool_size=OnlineHostingConfig.SQLITE_POOL_SIZE,
        max_overflow=OnlineHostingConfig.SQLITE_MAX_OVERFLOW
    )
    """
    logger.info("مثال التكامل مع db/session.py:")
    logger.info(code_example)


# ================================================
# مثال 9: استخدام مع النسخ الاحتياطي التلقائي
# ================================================

def example_auto_backup_integration():
    """
    مثال على التكامل مع نظام النسخ الاحتياطي التلقائي
    
    في services/scheduler.py:
    """
    code_example = """
    # في services/scheduler.py
    from db.online_hosting_config import OnlineHostingConfig
    from db.persistent_storage import save_database_to_cloud
    
    def setup_auto_backup():
        if OnlineHostingConfig.AUTO_BACKUP_ENABLED:
            interval_minutes = OnlineHostingConfig.AUTO_BACKUP_INTERVAL
            
            scheduler.add_job(
                save_database_to_cloud,
                'interval',
                minutes=interval_minutes,
                id='auto_backup',
                replace_existing=True
            )
            logger.info(f"✅ النسخ الاحتياطي التلقائي مفعّل (كل {interval_minutes} دقيقة)")
    """
    logger.info("مثال التكامل مع النسخ الاحتياطي التلقائي:")
    logger.info(code_example)


# ================================================
# مثال 10: استخدام مع الاستعادة التلقائية
# ================================================

def example_auto_restore_integration():
    """
    مثال على التكامل مع الاستعادة التلقائية
    
    في db/session.py أو app.py:
    """
    code_example = """
    # في db/session.py أو app.py
    from db.online_hosting_config import OnlineHostingConfig
    from db.persistent_storage import restore_database_on_startup
    
    # عند بدء التطبيق
    if OnlineHostingConfig.AUTO_RESTORE_ON_STARTUP:
        if restore_database_on_startup():
            logger.info("✅ تم استعادة قاعدة البيانات من Cloud Storage")
        else:
            logger.info("ℹ️ لا توجد نسخة احتياطية، سيتم إنشاء قاعدة بيانات جديدة")
    """
    logger.info("مثال التكامل مع الاستعادة التلقائية:")
    logger.info(code_example)


# ================================================
# تشغيل جميع الأمثلة
# ================================================

if __name__ == "__main__":
    # إعداد logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("=" * 60)
    logger.info("أمثلة على استخدام إعدادات الاستضافة الإلكترونية")
    logger.info("=" * 60)
    
    # تشغيل الأمثلة
    example_init()
    example_validate_config()
    example_backup_config()
    example_cloud_storage_config()
    example_get_all_config()
    
    logger.info("=" * 60)
    logger.info("✅ انتهت الأمثلة")
    logger.info("=" * 60)

