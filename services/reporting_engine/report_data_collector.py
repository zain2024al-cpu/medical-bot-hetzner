# ================================================
# services/reporting_engine/report_data_collector.py
# 📊 جمع البيانات من قاعدة البيانات
# ================================================

import logging
from typing import List, Dict, Any
from sqlalchemy import func

from db.session import SessionLocal
from db.models import Report, Patient, Hospital, Department, Doctor
from .filters import CompositeFilter
from shared.report_constants import ReportType

logger = logging.getLogger(__name__)


class ReportDataCollector:
    """جمع البيانات الخام من قاعدة البيانات"""
    
    def __init__(self):
        self.session = None
    
    def _get_session(self):
        """الحصول على session"""
        if self.session is None:
            self.session = SessionLocal()
        return self.session
    
    def collect(
        self,
        report_type: ReportType,
        filters: CompositeFilter,
        **kwargs
    ) -> Dict[str, Any]:
        """
        جمع البيانات بناءً على نوع التقرير والفلاتر
        
        Args:
            report_type: نوع التقرير
            filters: الفلاتر المركبة
            **kwargs: معاملات إضافية
            
        Returns:
            dict with raw data
        """
        logger.info(f"🔍 جمع البيانات للتقرير: {report_type.value}")
        
        db = self._get_session()
        
        try:
            # بناء الاستعلام الأساسي
            query = db.query(Report)
            
            # تطبيق الفلاتر
            query = filters.apply(query)
            
            # جلب البيانات
            reports = query.all()
            
            logger.info(f"✅ تم جمع {len(reports)} تقرير")
            
            # تجميع البيانات حسب نوع التقرير
            if report_type == ReportType.GLOBAL:
                return self._collect_global_data(reports)
            elif report_type == ReportType.PATIENT:
                return self._collect_patient_data(reports, kwargs.get("patient_id"))
            elif report_type == ReportType.HOSPITAL:
                return self._collect_hospital_data(reports, kwargs.get("hospital_id"))
            elif report_type == ReportType.TRANSLATOR:
                return self._collect_translator_data(reports, kwargs.get("translator_id"))
            else:
                return self._collect_generic_data(reports)
        
        except Exception as e:
            logger.error(f"❌ خطأ في جمع البيانات: {e}")
            return {}
        
        finally:
            if self.session:
                self.session.close()
                self.session = None
    
    def _collect_global_data(self, reports: List[Report]) -> Dict[str, Any]:
        """جمع البيانات لتقرير عام/شامل"""
        logger.info("📊 جمع بيانات التقرير الشامل")
        
        return {
            "reports": reports,
            "raw_reports": [self._serialize_report(r) for r in reports],
            "patient_ids": list(set(r.patient_id for r in reports if r.patient_id)),
            "hospital_ids": list(set(r.hospital_id for r in reports if r.hospital_id)),
            "department_ids": list(set(r.department_id for r in reports if r.department_id)),
            "medical_actions": list(set(r.medical_action for r in reports if r.medical_action)),
        }
    
    def _collect_patient_data(self, reports: List[Report], patient_id: int) -> Dict[str, Any]:
        """جمع البيانات لتقرير مريض"""
        logger.info(f"👤 جمع بيانات تقرير المريض: {patient_id}")
        
        return {
            "reports": reports,
            "raw_reports": [self._serialize_report(r) for r in reports],
            "patient_id": patient_id,
            "hospital_ids": list(set(r.hospital_id for r in reports if r.hospital_id)),
            "department_ids": list(set(r.department_id for r in reports if r.department_id)),
            "medical_actions": list(set(r.medical_action for r in reports if r.medical_action)),
        }
    
    def _collect_hospital_data(self, reports: List[Report], hospital_id: int) -> Dict[str, Any]:
        """جمع البيانات لتقرير مستشفى"""
        logger.info(f"🏥 جمع بيانات تقرير المستشفى: {hospital_id}")
        
        return {
            "reports": reports,
            "raw_reports": [self._serialize_report(r) for r in reports],
            "hospital_id": hospital_id,
            "patient_ids": list(set(r.patient_id for r in reports if r.patient_id)),
            "department_ids": list(set(r.department_id for r in reports if r.department_id)),
        }
    
    def _collect_translator_data(self, reports: List[Report], translator_id: int) -> Dict[str, Any]:
        """جمع البيانات لتقرير مترجم"""
        logger.info(f"👨‍💼 جمع بيانات تقرير المترجم: {translator_id}")
        
        return {
            "reports": reports,
            "raw_reports": [self._serialize_report(r) for r in reports],
            "translator_id": translator_id,
            "patient_ids": list(set(r.patient_id for r in reports if r.patient_id)),
            "hospital_ids": list(set(r.hospital_id for r in reports if r.hospital_id)),
        }
    
    def _collect_generic_data(self, reports: List[Report]) -> Dict[str, Any]:
        """جمع بيانات عامة"""
        logger.info("📋 جمع بيانات عامة")
        
        return {
            "reports": reports,
            "raw_reports": [self._serialize_report(r) for r in reports],
        }
    
    @staticmethod
    def _serialize_report(report: Report) -> Dict[str, Any]:
        """تحويل تقرير إلى قاموس"""
        return {
            "id": report.id,
            "patient_name": report.patient_name,
            "patient_id": report.patient_id,
            "hospital_name": report.hospital_name,
            "hospital_id": report.hospital_id,
            "department": report.department,
            "department_id": report.department_id,
            "doctor_name": report.doctor_name,
            "doctor_id": report.doctor_id,
            "translator_name": report.translator_name,
            "translator_id": report.translator_id,
            "medical_action": report.medical_action,
            "report_date": report.report_date.isoformat() if report.report_date else None,
            "visit_date": report.visit_date.isoformat() if report.visit_date else None,
            "complaint_text": report.complaint_text,
            "doctor_decision": report.doctor_decision,
            "diagnosis": report.diagnosis,
            "treatment_plan": report.treatment_plan,
            "notes": report.notes,
        }
