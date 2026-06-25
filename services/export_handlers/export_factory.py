# ================================================
# services/export_handlers/export_factory.py
# 💾 مصنع التصدير (معمارية Plugin)
# ================================================

import logging
from typing import Optional
import io

from shared.report_constants import ExportFormat
from services.reporting_engine.report_data import ReportData

logger = logging.getLogger(__name__)


class ExportFactory:
    """
    مصنع التصدير - يدعم صيغ متعددة
    
    معمارية Plugin تسمح بإضافة صيغ جديدة بسهولة
    """
    
    _exporters = {}
    
    @classmethod
    def register_exporter(cls, format: ExportFormat, exporter_class):
        """تسجيل معالج تصدير جديد"""
        cls._exporters[format.value] = exporter_class
        logger.info(f"✅ تسجيل معالج تصدير: {format.value}")
    
    @classmethod
    def export(
        cls,
        report_data: ReportData,
        format: ExportFormat,
        filename: str = "",
    ) -> Optional[io.BytesIO]:
        """
        تصدير التقرير بصيغة معينة
        
        Args:
            report_data: بيانات التقرير
            format: صيغة التصدير
            filename: اسم الملف
            
        Returns:
            BytesIO object or None
        """
        
        logger.info(f"📤 تصدير التقرير بصيغة: {format.value}")
        
        exporter_class = cls._exporters.get(format.value)
        
        if not exporter_class:
            logger.error(f"❌ معالج تصدير غير مدعوم: {format.value}")
            return None
        
        try:
            exporter = exporter_class()
            return exporter.export(report_data, filename)
        except Exception as e:
            logger.error(f"❌ خطأ في التصدير: {e}", exc_info=True)
            return None
    
    @classmethod
    def get_supported_formats(cls) -> list:
        """الحصول على الصيغ المدعومة"""
        return list(cls._exporters.keys())


# ========================================
# PDF Exporter (مدعوم حالياً)
# ========================================

class PDFExporter:
    """معالج تصدير PDF"""
    
    def export(self, report_data: ReportData, filename: str = "") -> Optional[io.BytesIO]:
        """تصدير إلى PDF"""
        logger.info("📤 تصدير إلى PDF")
        
        from services.pdf_generation.pdf_builder import PDFBuilder
        
        try:
            builder = PDFBuilder()
            pdf_buffer = builder.build_from_report_data(report_data)
            logger.info("✅ تم التصدير إلى PDF بنجاح")
            return pdf_buffer
        except Exception as e:
            logger.error(f"❌ خطأ في تصدير PDF: {e}")
            return None


# ========================================
# Excel Exporter (جاهز للتطبيق)
# ========================================

class ExcelExporter:
    """معالج تصدير Excel"""
    
    def export(self, report_data: ReportData, filename: str = "") -> Optional[io.BytesIO]:
        """تصدير إلى Excel"""
        logger.info("📤 تصدير إلى Excel")
        logger.warning("⚠️ Excel Exporter قيد التطوير")
        return None


# ========================================
# CSV Exporter (جاهز للتطبيق)
# ========================================

class CSVExporter:
    """معالج تصدير CSV"""
    
    def export(self, report_data: ReportData, filename: str = "") -> Optional[io.BytesIO]:
        """تصدير إلى CSV"""
        logger.info("📤 تصدير إلى CSV")
        logger.warning("⚠️ CSV Exporter قيد التطوير")
        return None


# تسجيل المصدرين
ExportFactory.register_exporter(ExportFormat.PDF, PDFExporter)
ExportFactory.register_exporter(ExportFormat.EXCEL, ExcelExporter)
ExportFactory.register_exporter(ExportFormat.CSV, CSVExporter)
