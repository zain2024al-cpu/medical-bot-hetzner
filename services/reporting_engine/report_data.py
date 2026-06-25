# ================================================
# services/reporting_engine/report_data.py
# 📊 بنية بيانات التقرير المرنة
# ================================================

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from shared.report_constants import ReportType, ReportSection

# ========================================
# Data Models for Report Components
# ========================================

@dataclass
class MetricItem:
    """عنصر مؤشر رئيسي"""
    label: str
    value: str
    unit: str = ""
    icon: str = ""
    color: str = "#1565C0"
    description: str = ""


@dataclass
class TableData:
    """بيانات جدول"""
    title: str
    headers: List[str]
    rows: List[List[Any]]
    footer: Optional[List[Any]] = None
    description: str = ""
    footnote: str = ""


@dataclass
class ChartData:
    """بيانات رسم بياني"""
    title: str
    type: str  # "bar", "pie", "line", etc.
    data: Dict[str, Any]
    description: str = ""
    footnote: str = ""


@dataclass
class TimelineItem:
    """عنصر في التسلسل الزمني"""
    date: str
    title: str
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DetailRow:
    """صف تفصيلي"""
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)


# ========================================
# Main ReportData Class (المرن)
# ========================================

@dataclass
class ReportData:
    """
    بنية بيانات التقرير الموحدة والمرنة
    
    كل قسم اختياري ويمكن تجاهله أو استخدامه حسب نوع التقرير
    """
    
    # ===== Metadata =====
    report_type: ReportType
    title: str
    subtitle: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    created_by: str = "System"
    period: str = ""
    
    # ===== Cover Page Data =====
    cover_page: Optional[Dict[str, Any]] = None
    # {
    #     "title": "",
    #     "subtitle": "",
    #     "metadata": {},
    #     "logo_path": ""
    # }
    
    # ===== Executive Summary =====
    executive_summary: Optional[str] = None
    
    # ===== Key Metrics =====
    key_metrics: List[MetricItem] = field(default_factory=list)
    
    # ===== Statistics =====
    statistics: Dict[str, Any] = field(default_factory=dict)
    # {
    #     "total_cases": 0,
    #     "total_patients": 0,
    #     "total_hospitals": 0,
    #     "averages": {},
    #     "distributions": {}
    # }
    
    # ===== Tables =====
    tables: List[TableData] = field(default_factory=list)
    
    # ===== Charts =====
    charts: List[ChartData] = field(default_factory=list)
    
    # ===== Timeline =====
    timeline: List[TimelineItem] = field(default_factory=list)
    timeline_chart_data: Optional[ChartData] = None
    
    # ===== Details =====
    detailed_rows: List[DetailRow] = field(default_factory=list)
    detailed_headers: List[str] = field(default_factory=list)
    
    # ===== Additional Sections =====
    recommendations: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    conclusion: str = ""
    
    # ===== Filters Used =====
    filters_applied: Dict[str, Any] = field(default_factory=dict)
    
    # ===== Metadata for Export =====
    export_metadata: Dict[str, Any] = field(default_factory=dict)
    # {
    #     "filename_prefix": "",
    #     "filename_suffix": "",
    #     "tags": [],
    #     "keywords": []
    # }
    
    # ===== Internal Tracking =====
    _generation_time: float = 0.0
    _sections_generated: List[ReportSection] = field(default_factory=list)
    
    # ========================================
    # Utility Methods
    # ========================================
    
    def has_section(self, section: ReportSection) -> bool:
        """هل القسم موجود وله بيانات؟"""
        if section == ReportSection.COVER_PAGE:
            return self.cover_page is not None
        elif section == ReportSection.EXECUTIVE_SUMMARY:
            return self.executive_summary is not None
        elif section == ReportSection.KEY_METRICS:
            return len(self.key_metrics) > 0
        elif section == ReportSection.STATISTICS:
            return len(self.statistics) > 0
        elif section == ReportSection.TABLES:
            return len(self.tables) > 0
        elif section == ReportSection.CHARTS:
            return len(self.charts) > 0
        elif section == ReportSection.TIMELINE:
            return len(self.timeline) > 0
        elif section == ReportSection.DETAILS:
            return len(self.detailed_rows) > 0
        elif section == ReportSection.RECOMMENDATIONS:
            return len(self.recommendations) > 0
        elif section == ReportSection.NOTES:
            return len(self.notes) > 0
        elif section == ReportSection.CONCLUSION:
            return len(self.conclusion) > 0
        return False
    
    def add_metric(self, metric: MetricItem):
        """إضافة مؤشر رئيسي"""
        self.key_metrics.append(metric)
    
    def add_table(self, table: TableData):
        """إضافة جدول"""
        self.tables.append(table)
    
    def add_chart(self, chart: ChartData):
        """إضافة رسم بياني"""
        self.charts.append(chart)
    
    def add_timeline_item(self, item: TimelineItem):
        """إضافة عنصر زمني"""
        self.timeline.append(item)
    
    def add_detail_row(self, row: DetailRow):
        """إضافة صف تفصيلي"""
        self.detailed_rows.append(row)
    
    def set_section_generated(self, section: ReportSection):
        """تسجيل أن القسم تم إنشاؤه"""
        if section not in self._sections_generated:
            self._sections_generated.append(section)
    
    def get_generation_stats(self) -> Dict[str, Any]:
        """الحصول على إحصائيات الإنشاء"""
        return {
            "report_type": self.report_type.value,
            "total_tables": len(self.tables),
            "total_charts": len(self.charts),
            "total_metrics": len(self.key_metrics),
            "total_timeline_items": len(self.timeline),
            "total_details": len(self.detailed_rows),
            "sections_generated": len(self._sections_generated),
            "generation_time": self._generation_time,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """تحويل إلى قاموس (للتصدير والـ Logging)"""
        return {
            "report_type": self.report_type.value,
            "title": self.title,
            "subtitle": self.subtitle,
            "created_at": self.created_at.isoformat(),
            "period": self.period,
            "sections_generated": len(self._sections_generated),
            "stats": self.get_generation_stats(),
        }
