# ================================================
# shared/logging_config.py
# 📋 إعدادات Logging الشاملة
# ================================================

import logging
import logging.handlers
import os
from datetime import datetime

# مجلد السجلات
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# اسم ملف السجل
LOG_FILE = os.path.join(LOG_DIR, f"reports_{datetime.now().strftime('%Y%m%d')}.log")

# ========================================
# Formatters
# ========================================

DETAILED_FORMATTER = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

SIMPLE_FORMATTER = logging.Formatter(
    '%(levelname)s - %(message)s'
)

# ========================================
# Logger Configuration
# ========================================

def setup_logging():
    """إعداد نظام Logging الشامل"""
    
    # الـ Root Logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # إزالة المعالجات القديمة
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Handler للملف (تفصيلي)
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(DETAILED_FORMATTER)
    root_logger.addHandler(file_handler)
    
    # Handler للـ Console (بسيط)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(SIMPLE_FORMATTER)
    root_logger.addHandler(console_handler)
    
    # إعدادات لـ Loggers المحددة
    
    # Report Engine Logger
    report_engine_logger = logging.getLogger('services.reporting_engine')
    report_engine_logger.setLevel(logging.DEBUG)
    
    # PDF Generation Logger
    pdf_logger = logging.getLogger('services.pdf_generation')
    pdf_logger.setLevel(logging.DEBUG)
    
    # Database Logger
    db_logger = logging.getLogger('db')
    db_logger.setLevel(logging.INFO)
    
    # Telegram Logger
    telegram_logger = logging.getLogger('telegram')
    telegram_logger.setLevel(logging.WARNING)
    
    # SQLAlchemy Logger
    sqlalchemy_logger = logging.getLogger('sqlalchemy')
    sqlalchemy_logger.setLevel(logging.WARNING)
    
    root_logger.info("=" * 80)
    root_logger.info("🚀 نظام Logging جاهز")
    root_logger.info("=" * 80)


# ========================================
# Logging Utilities
# ========================================

class ReportLogger:
    """Utility class لـ Logging المتعلق بالتقارير"""
    
    @staticmethod
    def log_filter_application(filters_applied: dict):
        """تسجيل الفلاتر المطبقة"""
        logger = logging.getLogger('services.reporting_engine')
        
        if filters_applied:
            logger.info("🔍 الفلاتر المطبقة:")
            for filter_name, filter_config in filters_applied.items():
                logger.info(f"   - {filter_name}: {filter_config}")
        else:
            logger.info("⚠️ لا توجد فلاتر مطبقة")
    
    @staticmethod
    def log_data_fetch_complete(records_count: int, duration: float):
        """تسجيل انتهاء جلب البيانات"""
        logger = logging.getLogger('services.reporting_engine')
        logger.info(f"✅ تم جلب {records_count} سجل في {duration:.2f} ثانية")
    
    @staticmethod
    def log_statistics_calculation(stats: dict):
        """تسجيل الإحصائيات المحسوبة"""
        logger = logging.getLogger('services.reporting_engine')
        logger.info("📊 الإحصائيات المحسوبة:")
        
        summary = stats.get('summary', {})
        for key, value in summary.items():
            logger.info(f"   - {key}: {value}")
    
    @staticmethod
    def log_pdf_generation_start(report_type: str):
        """تسجيل بدء إنشاء PDF"""
        logger = logging.getLogger('services.pdf_generation')
        logger.info(f"🔨 بدء إنشاء PDF للتقرير: {report_type}")
    
    @staticmethod
    def log_pdf_generation_complete(filename: str, file_size: int):
        """تسجيل انتهاء إنشاء PDF"""
        logger = logging.getLogger('services.pdf_generation')
        logger.info(f"✅ تم إنشاء PDF بنجاح: {filename} ({file_size / 1024:.2f} KB)")
    
    @staticmethod
    def log_export_start(format: str):
        """تسجيل بدء التصدير"""
        logger = logging.getLogger('services.reporting_engine')
        logger.info(f"📤 بدء التصدير إلى صيغة: {format}")
    
    @staticmethod
    def log_export_complete(format: str, duration: float):
        """تسجيل انتهاء التصدير"""
        logger = logging.getLogger('services.reporting_engine')
        logger.info(f"✅ تم التصدير إلى {format} في {duration:.2f} ثانية")


# استدعاء الإعداد عند استيراد الملف
setup_logging()
