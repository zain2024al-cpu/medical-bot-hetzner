# ================================================
# services/reporting_engine/report_stats_calculator.py
# 📉 حساب الإحصائيات والمؤشرات
# ================================================

import logging
from typing import Dict, List, Any
from statistics import mean, median, stdev

logger = logging.getLogger(__name__)


class ReportStatsCalculator:
    """حساب الإحصائيات والمؤشرات الرئيسية"""
    
    def calculate(self, aggregated: Dict[str, Any], report_type: str) -> Dict[str, Any]:
        """
        حساب الإحصائيات
        
        Args:
            aggregated: البيانات المجمعة
            report_type: نوع التقرير
            
        Returns:
            dict with statistics
        """
        logger.info(f"📉 حساب الإحصائيات: {report_type}")
        
        return {
            "summary": self._calculate_summary(aggregated),
            "statistics": self._calculate_statistics(aggregated),
            "trends": self._calculate_trends(aggregated),
        }
    
    @staticmethod
    def _calculate_summary(aggregated: Dict[str, Any]) -> Dict[str, Any]:
        """حساب الملخص الإحصائي"""
        logger.info("📊 حساب الملخص")
        
        hospitals = aggregated.get("hospitals", {})
        departments = aggregated.get("departments", {})
        medical_actions = aggregated.get("medical_actions", {})
        reports = aggregated.get("raw_reports", [])
        
        return {
            "total_records": aggregated.get("total_records", 0),
            "total_hospitals": len(hospitals),
            "total_departments": len(departments),
            "total_medical_actions": len(medical_actions),
            "total_unique_patients": len(set(r.get("patient_id") for r in reports if r.get("patient_id"))),
            "total_unique_doctors": len(set(r.get("doctor_name") for r in reports if r.get("doctor_name"))),
            "total_unique_translators": len(set(r.get("translator_name") for r in reports if r.get("translator_name"))),
        }
    
    @staticmethod
    def _calculate_statistics(aggregated: Dict[str, Any]) -> Dict[str, Any]:
        """حساب الإحصائيات التفصيلية"""
        logger.info("📈 حساب الإحصائيات التفصيلية")
        
        hospitals = aggregated.get("hospitals", {})
        departments = aggregated.get("departments", {})
        medical_actions = aggregated.get("medical_actions", {})
        
        def calc_stats(data_dict):
            if not data_dict:
                return {"min": 0, "max": 0, "avg": 0, "median": 0}
            
            values = list(data_dict.values())
            return {
                "min": min(values),
                "max": max(values),
                "avg": round(mean(values), 2) if values else 0,
                "median": round(median(values), 2) if values else 0,
            }
        
        return {
            "hospitals": calc_stats(hospitals),
            "departments": calc_stats(departments),
            "medical_actions": calc_stats(medical_actions),
        }
    
    @staticmethod
    def _calculate_trends(aggregated: Dict[str, Any]) -> Dict[str, Any]:
        """حساب الاتجاهات"""
        logger.info("📉 حساب الاتجاهات")
        
        by_date = aggregated.get("by_date", {})
        
        if len(by_date) < 2:
            return {"trend": "no_data", "direction": "flat"}
        
        dates = list(by_date.keys())
        values = list(by_date.values())
        
        # حساب الاتجاه (صاعد/هابط/مستقر)
        if values[-1] > values[0]:
            trend = "upward"
        elif values[-1] < values[0]:
            trend = "downward"
        else:
            trend = "flat"
        
        # حساب نسبة التغير
        if values[0] != 0:
            percentage_change = round(((values[-1] - values[0]) / values[0]) * 100, 2)
        else:
            percentage_change = 0
        
        return {
            "trend": trend,
            "percentage_change": percentage_change,
            "start_value": values[0],
            "end_value": values[-1],
        }
