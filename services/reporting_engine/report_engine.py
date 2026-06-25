# ================================================
# services/reporting_engine/report_engine.py
# 🎯 محرك التقارير الرئيسي
# ================================================

import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime

from shared.report_constants import ReportType, REPORT_SECTIONS_MAP
from services.reporting_engine.report_data import ReportData
from services.reporting_engine.filters import CompositeFilter
from .report_data_collector import ReportDataCollector
from .report_aggregator import ReportAggregator
from .report_stats_calculator import ReportStatsCalculator

logger = logging.getLogger(__name__)


class ReportEngine:
    """
    محرك التقارير الرئيسي (Facade Pattern)
    
    يتولى:
    1. جمع البيانات من قاعدة البيانات
    2. تجميع وتحليل البيانات
    3. حساب الإحصائيات
    4. بناء بنية ReportData
    """
    
    def __init__(self):
        self.data_collector = ReportDataCollector()
        self.aggregator = ReportAggregator()
        self.stats_calculator = ReportStatsCalculator()
        self.logger = logger
    
    def build_report(
        self,
        report_type: ReportType,
        filters: CompositeFilter,
        title: str = "",
        subtitle: str = "",
        **kwargs
    ) -> ReportData:
        """
        بناء تقرير كامل
        
        Args:
            report_type: نوع التقرير
            filters: الفلاتر المركبة
            title: عنوان التقرير
            subtitle: عنوان فرعي
            **kwargs: معاملات إضافية (patient_id, hospital_id, etc.)
            
        Returns:
            ReportData object
        """
        start_time = time.time()
        
        logger.info("=" * 60)
        logger.info(f"🚀 بدء بناء التقرير: {report_type.value}")
        logger.info("=" * 60)
        
        try:
            # 1. جمع البيانات
            logger.info("📊 المرحلة 1: جمع البيانات")
            raw_data = self.data_collector.collect(report_type, filters, **kwargs)
            
            if not raw_data or not raw_data.get("reports"):
                logger.warning("⚠️ لا توجد بيانات للتقرير")
                return self._create_empty_report(report_type, title, subtitle, filters)
            
            # 2. تجميع البيانات
            logger.info("📈 المرحلة 2: تجميع البيانات")
            aggregated = self.aggregator.aggregate(raw_data, report_type.value)
            
            # 3. حساب الإحصائيات
            logger.info("📉 المرحلة 3: حساب الإحصائيات")
            stats = self.stats_calculator.calculate(aggregated, report_type.value)
            
            # 4. تجهيز بيانات الرسوم البيانية
            logger.info("📊 المرحلة 4: تجهيز الرسوم البيانية")
            charts_data = self.aggregator.prepare_charts_data(aggregated)
            
            # 5. بناء ReportData
            logger.info("🔧 المرحلة 5: بناء بنية التقرير")
            report_data = self._build_report_data(
                report_type=report_type,
                title=title,
                subtitle=subtitle,
                filters=filters,
                raw_data=raw_data,
                aggregated=aggregated,
                stats=stats,
                charts_data=charts_data,
                kwargs=kwargs,
            )
            
            # تسجيل وقت الإنشاء
            generation_time = time.time() - start_time
            report_data._generation_time = generation_time
            
            logger.info("=" * 60)
            logger.info(f"✅ تم بناء التقرير بنجاح في {generation_time:.2f} ثانية")
            logger.info(f"📊 إحصائيات التقرير: {report_data.get_generation_stats()}")
            logger.info("=" * 60)
            
            return report_data
        
        except Exception as e:
            logger.error(f"❌ خطأ في بناء التقرير: {e}", exc_info=True)
            return self._create_empty_report(report_type, title, subtitle, filters)
    
    def _build_report_data(
        self,
        report_type: ReportType,
        title: str,
        subtitle: str,
        filters: CompositeFilter,
        raw_data: Dict[str, Any],
        aggregated: Dict[str, Any],
        stats: Dict[str, Any],
        charts_data: Dict[str, Any],
        kwargs: Dict[str, Any],
    ) -> ReportData:
        """بناء بنية ReportData"""
        
        # إنشاء ReportData
        report_data = ReportData(
            report_type=report_type,
            title=title or f"تقرير {report_type.value}",
            subtitle=subtitle,
            created_at=datetime.now(),
            created_by="ReportEngine",
            statistics=stats.get("statistics", {}),
            filters_applied=filters.to_dict(),
        )
        
        # تعيين الملخص
        summary_stats = stats.get("summary", {})
        
        # إضافة المؤشرات الرئيسية
        from services.reporting_engine.report_data import MetricItem
        
        report_data.key_metrics = [
            MetricItem(
                label="إجمالي السجلات",
                value=str(summary_stats.get("total_records", 0)),
                icon="📋",
                color="#1565C0",
            ),
            MetricItem(
                label="عدد المستشفيات",
                value=str(summary_stats.get("total_hospitals", 0)),
                icon="🏥",
                color="#0288D1",
            ),
            MetricItem(
                label="عدد الأقسام",
                value=str(summary_stats.get("total_departments", 0)),
                icon="🏢",
                color="#2E7D32",
            ),
            MetricItem(
                label="عدد الإجراءات",
                value=str(summary_stats.get("total_medical_actions", 0)),
                icon="💉",
                color="#F57F17",
            ),
        ]
        
        # إضافة الجداول
        from services.reporting_engine.report_data import TableData
        
        # جدول المستشفيات
        if aggregated.get("hospitals"):
            report_data.add_table(TableData(
                title="توزيع المستشفيات",
                headers=["المستشفى", "عدد السجلات"],
                rows=[[name, count] for name, count in aggregated["hospitals"].items()],
            ))
        
        # جدول الأقسام
        if aggregated.get("departments"):
            report_data.add_table(TableData(
                title="توزيع الأقسام",
                headers=["القسم", "عدد السجلات"],
                rows=[[name, count] for name, count in aggregated["departments"].items()],
            ))
        
        # جدول الإجراءات
        if aggregated.get("medical_actions"):
            report_data.add_table(TableData(
                title="توزيع الإجراءات",
                headers=["الإجراء", "عدد السجلات"],
                rows=[[name, count] for name, count in aggregated["medical_actions"].items()],
            ))
        
        # إضافة التسلسل الزمني
        from services.reporting_engine.report_data import TimelineItem
        
        for date_str, count in aggregated.get("by_date", {}).items():
            report_data.add_timeline_item(TimelineItem(
                date=date_str,
                title=f"{count} سجل",
                description="عدد السجلات في هذا اليوم",
                metadata={"count": count},
            ))

        # إضافة الرسوم البيانية بناءً على البيانات المجمعة
        from services.reporting_engine.report_data import ChartData

        # رسم بياني عمودي لتوزيع المستشفيات
        if aggregated.get("hospitals"):
            labels = list(aggregated["hospitals"].keys())
            values = list(aggregated["hospitals"].values())
            report_data.add_chart(ChartData(
                title="توزيع المستشفيات",
                type="bar",
                data={"labels": labels, "values": values},
            ))

        # رسم دائري للإجراءات الطبية
        if aggregated.get("medical_actions"):
            labels = list(aggregated["medical_actions"].keys())
            values = list(aggregated["medical_actions"].values())
            report_data.add_chart(ChartData(
                title="نسب الإجراءات الطبية",
                type="pie",
                data={"labels": labels, "values": values},
            ))

        # رسم خطي للتطور الزمني
        if aggregated.get("by_date"):
            # ترتيب زمني
            dates = sorted(aggregated["by_date"].keys())
            values = [aggregated["by_date"][d] for d in dates]
            report_data.add_chart(ChartData(
                title="التطور الزمني للسجلات",
                type="line",
                data={"x": dates, "y": values},
            ))
        
        # تعيين الخاتمة
        total_records = summary_stats.get("total_records", 0)
        report_data.conclusion = (
            f"تم تحليل {total_records} سجل طبي عبر {summary_stats.get('total_hospitals', 0)} "
            f"مستشفى و {summary_stats.get('total_departments', 0)} قسم."
        )
        
        logger.info(f"✅ تم بناء ReportData بنجاح")
        return report_data
    
    def _create_empty_report(
        self,
        report_type: ReportType,
        title: str,
        subtitle: str,
        filters: CompositeFilter,
    ) -> ReportData:
        """إنشاء تقرير فارغ"""
        logger.warning("⚠️ إنشاء تقرير فارغ")
        
        return ReportData(
            report_type=report_type,
            title=title or f"تقرير {report_type.value}",
            subtitle=subtitle or "لا توجد بيانات للتقرير المطلوب",
            created_at=datetime.now(),
            created_by="ReportEngine",
            conclusion="لا توجد بيانات متطابقة مع الفلاتر المختارة.",
            filters_applied=filters.to_dict(),
        )
