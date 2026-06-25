# ================================================
# shared/report_constants.py
# 📋 ثوابت ونوعيات التقارير
# ================================================

from enum import Enum
from typing import Dict, List

# ========================================
# Report Types
# ========================================

class ReportType(Enum):
    """أنواع التقارير المدعومة"""
    GLOBAL = "global"                      # تقرير شامل
    PATIENT = "patient"                    # تقرير مريض
    HOSPITAL = "hospital"                  # تقرير مستشفى
    TRANSLATOR = "translator"              # تقرير مترجم
    HEALTHCARE = "healthcare"              # تقرير الرعاية الصحية
    RESIDENCY = "residency"                # تقرير الإقامة
    EXECUTIVE = "executive"                # تقرير تنفيذي


class ExportFormat(Enum):
    """صيغ التصدير المدعومة"""
    PDF = "pdf"
    EXCEL = "xlsx"
    CSV = "csv"


# ========================================
# Report Sections (أقسام التقرير)
# ========================================

class ReportSection(Enum):
    """أقسام التقرير المتاحة"""
    COVER_PAGE = "cover_page"              # صفحة الغلاف
    EXECUTIVE_SUMMARY = "executive_summary"  # ملخص تنفيذي
    KEY_METRICS = "key_metrics"            # المؤشرات الرئيسية
    STATISTICS = "statistics"              # الإحصائيات
    TABLES = "tables"                      # الجداول
    CHARTS = "charts"                      # الرسوم البيانية
    TIMELINE = "timeline"                  # التسلسل الزمني
    DETAILS = "details"                    # التفاصيل
    RECOMMENDATIONS = "recommendations"    # التوصيات
    NOTES = "notes"                        # ملاحظات
    CONCLUSION = "conclusion"              # الخاتمة


# ========================================
# Filter Types
# ========================================

class FilterType(Enum):
    """أنواع الفلاتر"""
    DATE_RANGE = "date_range"
    HOSPITAL = "hospital"
    DEPARTMENT = "department"
    DOCTOR = "doctor"
    TRANSLATOR = "translator"
    PATIENT = "patient"
    MEDICAL_ACTION = "medical_action"
    STATUS = "status"


# ========================================
# Chart Types
# ========================================

class ChartType(Enum):
    """أنواع الرسوم البيانية"""
    BAR = "bar"                    # رسم بياني عمودي
    HORIZONTAL_BAR = "horizontal"  # رسم بياني أفقي
    PIE = "pie"                    # رسم بياني دائري
    LINE = "line"                  # رسم بياني خطي
    AREA = "area"                  # رسم بياني مساحي
    SCATTER = "scatter"            # رسم بياني نقطي


# ========================================
# Presets
# ========================================

class DateRangePreset(Enum):
    """Presets للفترات الزمنية"""
    LAST_WEEK = "last_week"
    LAST_MONTH = "last_month"
    LAST_3_MONTHS = "last_3_months"
    LAST_6_MONTHS = "last_6_months"
    THIS_YEAR = "this_year"
    LAST_YEAR = "last_year"
    ALL_TIME = "all_time"


# ========================================
# Default Settings
# ========================================

REPORT_CONFIG = {
    # الألوان
    "colors": {
        "primary": "#1565C0",
        "accent": "#0288D1",
        "success": "#2E7D32",
        "warning": "#F57F17",
        "danger": "#C62828",
        "light_bg": "#F0F4F8",
        "card_bg": "#FAFCFF",
        "grid": "#D0D9E8",
        "text_dark": "#1A237E",
        "text_gray": "#546E7A",
    },
    
    # الخطوط
    "fonts": {
        "family": "DejaVu Sans",
        "size_title": 28,
        "size_heading": 20,
        "size_subheading": 14,
        "size_body": 12,
        "size_small": 10,
    },
    
    # حجم الصفحة
    "page": {
        "width": 210,  # A4 mm
        "height": 297,
        "margin_top": 20,
        "margin_bottom": 15,
        "margin_left": 20,
        "margin_right": 20,
    },
    
    # إعدادات الجداول
    "tables": {
        "header_height": 30,
        "row_height": 25,
        "max_rows_per_page": 25,
    },
    
    # إعدادات الرسوم البيانية
    "charts": {
        "width": 8,  # inches
        "height": 5,
        "dpi": 100,
    },
}

# ========================================
# Sections Required by Report Type
# ========================================

REPORT_SECTIONS_MAP: Dict[ReportType, List[ReportSection]] = {
    ReportType.GLOBAL: [
        ReportSection.COVER_PAGE,
        ReportSection.EXECUTIVE_SUMMARY,
        ReportSection.KEY_METRICS,
        ReportSection.TABLES,
        ReportSection.CHARTS,
        ReportSection.TIMELINE,
        ReportSection.CONCLUSION,
    ],
    
    ReportType.PATIENT: [
        ReportSection.COVER_PAGE,
        ReportSection.EXECUTIVE_SUMMARY,
        ReportSection.KEY_METRICS,
        ReportSection.TABLES,
        ReportSection.CHARTS,
        ReportSection.TIMELINE,
        ReportSection.DETAILS,
        ReportSection.NOTES,
        ReportSection.CONCLUSION,
    ],
    
    ReportType.HOSPITAL: [
        ReportSection.COVER_PAGE,
        ReportSection.EXECUTIVE_SUMMARY,
        ReportSection.KEY_METRICS,
        ReportSection.STATISTICS,
        ReportSection.TABLES,
        ReportSection.CHARTS,
        ReportSection.RECOMMENDATIONS,
        ReportSection.CONCLUSION,
    ],
    
    ReportType.TRANSLATOR: [
        ReportSection.COVER_PAGE,
        ReportSection.EXECUTIVE_SUMMARY,
        ReportSection.STATISTICS,
        ReportSection.TABLES,
        ReportSection.CHARTS,
        ReportSection.CONCLUSION,
    ],
    
    ReportType.EXECUTIVE: [
        ReportSection.COVER_PAGE,
        ReportSection.EXECUTIVE_SUMMARY,
        ReportSection.KEY_METRICS,
        ReportSection.CHARTS,
        ReportSection.RECOMMENDATIONS,
        ReportSection.CONCLUSION,
    ],
}
