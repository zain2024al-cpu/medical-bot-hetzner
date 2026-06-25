# ================================================
# services/reporting_engine/report_aggregator.py
# 📈 تجميع وتحليل البيانات
# ================================================

import logging
from typing import Dict, List, Any
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)


class ReportAggregator:
    """تجميع وتحليل البيانات الخام"""
    
    def aggregate(self, raw_data: Dict[str, Any], report_type: str) -> Dict[str, Any]:
        """
        تجميع البيانات الخام
        
        Args:
            raw_data: البيانات الخام من ReportDataCollector
            report_type: نوع التقرير
            
        Returns:
            dict with aggregated data
        """
        logger.info(f"📊 تجميع البيانات: {report_type}")
        
        reports = raw_data.get("reports", [])
        
        aggregated = {
            "total_records": len(reports),
            "hospitals": self._aggregate_by_field(reports, "hospital_name"),
            "departments": self._aggregate_by_field(reports, "department"),
            "medical_actions": self._aggregate_by_field(reports, "medical_action"),
            "doctors": self._aggregate_by_field(reports, "doctor_name"),
            "translators": self._aggregate_by_field(reports, "translator_name"),
            "by_date": self._aggregate_by_date(reports),
            "raw_reports": raw_data.get("raw_reports", []),
        }
        
        logger.info(f"✅ تم تجميع البيانات بنجاح")
        return aggregated
    
    @staticmethod
    def _aggregate_by_field(reports: List[Any], field: str) -> Dict[str, int]:
        """تجميع السجلات حسب حقل معين"""
        aggregation = defaultdict(int)
        
        for report in reports:
            value = getattr(report, field, None)
            if value:
                aggregation[value] += 1
        
        return dict(sorted(aggregation.items(), key=lambda x: x[1], reverse=True))
    
    @staticmethod
    def _aggregate_by_date(reports: List[Any]) -> Dict[str, int]:
        """تجميع السجلات حسب التاريخ"""
        date_aggregation = defaultdict(int)
        
        for report in reports:
            if report.report_date:
                date_key = report.report_date.strftime("%Y-%m-%d")
                date_aggregation[date_key] += 1
        
        return dict(sorted(date_aggregation.items()))
    
    def prepare_charts_data(self, aggregated: Dict[str, Any]) -> Dict[str, Any]:
        """
        تجهيز بيانات الرسوم البيانية
        
        Args:
            aggregated: البيانات المجمعة
            
        Returns:
            dict with chart data
        """
        logger.info("📊 تجهيز بيانات الرسوم البيانية")
        
        charts_data = {
            "hospitals": {
                "labels": list(aggregated["hospitals"].keys()),
                "values": list(aggregated["hospitals"].values()),
            },
            "departments": {
                "labels": list(aggregated["departments"].keys()),
                "values": list(aggregated["departments"].values()),
            },
            "medical_actions": {
                "labels": list(aggregated["medical_actions"].keys()),
                "values": list(aggregated["medical_actions"].values()),
            },
            "timeline": {
                "dates": list(aggregated["by_date"].keys()),
                "values": list(aggregated["by_date"].values()),
            },
        }
        
        return charts_data
